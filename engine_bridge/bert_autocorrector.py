from transformers import pipeline, AutoTokenizer, AutoModelForMaskedLM
from spellchecker import SpellChecker
import re
import Levenshtein
import threading
import queue
import time
import json
import os
from collections import defaultdict, Counter

class AutoCorrector:
    def __init__(self, learning_file="dataset_bridge/dataset_bert.json"):
        self.spell = SpellChecker(language='es')        
        self.learning_file = learning_file        
        self.learned_corrections = defaultdict(lambda: {"word": "", "count": 0})        
        self.sequence_patterns = defaultdict(int)        
        self.load_learned_corrections()
        
        try:
            print("🔄 Cargando modelo BERT en español...")
            model_name = "dccuchile/bert-base-spanish-wwm-uncased"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForMaskedLM.from_pretrained(model_name)
            self.nlp = pipeline('fill-mask', model=self.model, tokenizer=self.tokenizer)
            self.model_loaded = True
            print("✅ Modelo BERT cargado exitosamente")
        except Exception as e:
            print(f"⚠️ No se pudo cargar el modelo BERT: {e}")
            print("🔄 Usando solo corrección básica con diccionario")
            self.model_loaded = False
        
        self.word_buffer = []
        self.correction_queue = queue.Queue()
        self.processing = False
        
        self.last_raw_word = ""
        self.last_corrected_word = ""
        self.pending_feedback = False
        
    def load_learned_corrections(self):
        try:
            if os.path.exists(self.learning_file):
                with open(self.learning_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.learned_corrections = defaultdict(lambda: {"word": "", "count": 0}, data.get('corrections', {}))
                    self.sequence_patterns = defaultdict(int, data.get('patterns', {}))
                print(f"📚 Cargadas {len(self.learned_corrections)} correcciones aprendidas")
        except Exception as e:
            print(f"⚠️ Error cargando correcciones: {e}")
    
    def save_learned_corrections(self):
        try:
            os.makedirs(os.path.dirname(self.learning_file), exist_ok=True)
            data = {
                'corrections': dict(self.learned_corrections),
                'patterns': dict(self.sequence_patterns),
                'last_updated': time.time()
            }
            with open(self.learning_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Error guardando correcciones: {e}")
    
    def learn_correction(self, wrong_word, correct_word):
        if not wrong_word or not correct_word or wrong_word == correct_word:
            return
        
        wrong_key = wrong_word.lower()
        
        if self.learned_corrections[wrong_key]["word"] == correct_word.lower():
            self.learned_corrections[wrong_key]["count"] += 1
        else:
            self.learned_corrections[wrong_key] = {
                "word": correct_word.lower(),
                "count": 1
            }
        
        if len(wrong_word) > 2 and len(correct_word) > 1:
            pattern = f"{wrong_word.lower()}->{correct_word.lower()}"
            self.sequence_patterns[pattern] += 1
        
        self.save_learned_corrections()
        print(f"🧠 Aprendido: '{wrong_word}' -> '{correct_word}'")
    
    def get_learned_suggestion(self, word):
        """Obtener sugerencia basada en aprendizajes previos"""
        word_key = word.lower()
        
        # Buscar corrección exacta aprendida
        if word_key in self.learned_corrections:
            learned = self.learned_corrections[word_key]
            if learned["count"] > 0:
                return learned["word"]
        
        # Buscar correcciones similares
        best_match = None
        min_distance = float('inf')
        
        for learned_wrong, learned_data in self.learned_corrections.items():
            distance = Levenshtein.distance(word_key, learned_wrong)
            if distance < min_distance and distance <= len(word) // 3:  # Máximo 1/3 de diferencias
                min_distance = distance
                best_match = learned_data["word"]
        
        return best_match
        
    def simple_correct(self, word):
        if not word or len(word) < 2:
            return word
            
        word_lower = word.lower()
        
        learned_suggestion = self.get_learned_suggestion(word)
        if learned_suggestion:
            return learned_suggestion.capitalize() if word[0].isupper() else learned_suggestion
        
        if word_lower in self.spell:
            return word
        
        candidates = self.spell.candidates(word_lower)
        if candidates:
            best_candidate = min(candidates, 
                               key=lambda x: Levenshtein.distance(word_lower, x))
            return best_candidate.capitalize() if word[0].isupper() else best_candidate
        
        return word
    
    def advanced_correct(self, sentence):
        if not self.model_loaded:
            return sentence
            
        words = sentence.split()
        corrected_words = []
        
        for i, word in enumerate(words):
            learned_suggestion = self.get_learned_suggestion(word)
            if learned_suggestion:
                corrected_words.append(learned_suggestion)
                continue
            
            if word.lower() not in self.spell:
                context_words = words.copy()
                context_words[i] = '[MASK]'
                context = ' '.join(context_words)
                
                try:
                    suggestions = self.nlp(context, top_k=3)
                    
                    best_suggestion = word
                    min_distance = float('inf')
                    
                    for suggestion in suggestions:
                        suggested_word = suggestion['token_str']
                        distance = Levenshtein.distance(word.lower(), suggested_word.lower())
                        if distance < min_distance and distance <= len(word) // 2:
                            min_distance = distance
                            best_suggestion = suggested_word
                    
                    corrected_words.append(best_suggestion)
                except Exception as e:
                    print(f"Error en corrección avanzada: {e}")
                    corrected_words.append(self.simple_correct(word))
            else:
                corrected_words.append(word)
        
        return ' '.join(corrected_words)
    
    def add_letter(self, letter):
        self.word_buffer.append(letter)
    
    def get_current_word_corrected(self):
        if not self.word_buffer:
            return ""
        
        raw_word = ''.join(self.word_buffer)
        return self.simple_correct(raw_word)
    
    def finish_word(self):
        if not self.word_buffer:
            return ""
        
        raw_word = ''.join(self.word_buffer)
        corrected = self.simple_correct(raw_word)
        
        self.last_raw_word = raw_word
        self.last_corrected_word = corrected
        self.pending_feedback = True
        
        self.word_buffer = []
        return corrected
    
    def provide_feedback(self, correct_word):
        if self.pending_feedback and self.last_raw_word:
            self.learn_correction(self.last_raw_word, correct_word)
            self.pending_feedback = False
            return True
        return False
    
    def clear_buffer(self):
        self.word_buffer = []
        
    def get_learning_stats(self):
        total_corrections = len(self.learned_corrections)
        total_patterns = len(self.sequence_patterns)
        most_common = Counter({k: v["count"] for k, v in self.learned_corrections.items()}).most_common(5)
        
        return {
            "total_corrections": total_corrections,
            "total_patterns": total_patterns,
            "most_common": most_common
        }