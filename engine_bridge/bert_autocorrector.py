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
        # Cambiar estructura para incluir contexto
        self.learned_corrections = defaultdict(lambda: {"corrections": [], "count": 0})        
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
        
        # Agregar contexto para feedback
        self.current_context = []  # Palabras anteriores
        self.last_context = []     # Contexto de la última palabra
        self.last_raw_word = ""
        self.last_corrected_word = ""
        self.pending_feedback = False
        
    def load_learned_corrections(self):
        try:
            if os.path.exists(self.learning_file):
                with open(self.learning_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Cargar correcciones con nueva estructura
                    corrections_data = data.get('corrections', {})
                    for word, word_data in corrections_data.items():
                        if isinstance(word_data, dict) and "corrections" in word_data:
                            # Nueva estructura con contexto
                            self.learned_corrections[word] = word_data
                        else:
                            # Migrar estructura antigua
                            self.learned_corrections[word] = {
                                "corrections": [{"correct_word": word_data.get("word", ""), "context": "", "count": word_data.get("count", 1)}],
                                "count": word_data.get("count", 1)
                            }
                    
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
    
    def learn_correction(self, wrong_word, correct_word, context=None):
        if not wrong_word or not correct_word or wrong_word == correct_word:
            return
        
        wrong_key = wrong_word.lower()
        correct_lower = correct_word.lower()
        
        # Obtener contexto relevante (2-3 palabras anteriores)
        context_key = ""
        if context and len(context) > 0:
            # Tomar las últimas 2-3 palabras como contexto
            context_words = context[-3:] if len(context) >= 3 else context
            context_key = " ".join(context_words).lower()
        
        # Buscar si ya existe una corrección con el mismo contexto
        existing_correction = None
        for correction in self.learned_corrections[wrong_key]["corrections"]:
            if correction["context"] == context_key:
                existing_correction = correction
                break
        
        if existing_correction:
            # Actualizar corrección existente
            existing_correction["correct_word"] = correct_lower
            existing_correction["count"] += 1
        else:
            # Agregar nueva corrección con contexto
            self.learned_corrections[wrong_key]["corrections"].append({
                "correct_word": correct_lower,
                "context": context_key,
                "count": 1
            })
        
        self.learned_corrections[wrong_key]["count"] += 1
        
        # Mantener patrones de secuencia
        if len(wrong_word) > 2 and len(correct_word) > 1:
            pattern = f"{wrong_word.lower()}->{correct_word.lower()}"
            if context_key:
                pattern += f"[{context_key}]"
            self.sequence_patterns[pattern] += 1
        
        self.save_learned_corrections()
        context_info = f" (contexto: {context_key})" if context_key else ""
        print(f"🧠 Aprendido: '{wrong_word}' -> '{correct_word}'{context_info}")

    def evaluate_corrections_with_bert(self, word, corrections, context):
        try:
            # Crear contexto para BERT
            context_words = context[-3:] if len(context) >= 3 else context
            context_text = " ".join(context_words + ["[MASK]"])
            
            # Obtener sugerencias de BERT
            bert_suggestions = self.nlp(context_text, top_k=10)
            bert_words = [s['token_str'].lower() for s in bert_suggestions]
            
            # Evaluar cada corrección aprendida
            best_correction = None
            best_score = -1
            
            for correction in corrections:
                correct_word = correction["correct_word"]
                score = 0
                
                # Puntuación por frecuencia de uso
                score += correction["count"] * 0.3
                
                # Puntuación si BERT sugiere esta palabra
                if correct_word in bert_words:
                    bert_rank = bert_words.index(correct_word)
                    score += (10 - bert_rank) * 0.7  # Más puntos para rankings más altos
                
                # Puntuación por similitud con sugerencias de BERT
                for bert_word in bert_words[:5]:  # Top 5 de BERT
                    similarity = 1 - (Levenshtein.distance(correct_word, bert_word) / max(len(correct_word), len(bert_word)))
                    if similarity > 0.8:
                        score += similarity * 0.4
                
                if score > best_score:
                    best_score = score
                    best_correction = correction
            
            return best_correction["correct_word"] if best_correction else corrections[0]["correct_word"]
            
        except Exception as e:
            print(f"Error evaluando correcciones con BERT: {e}")
            # Fallback: corrección más frecuente
            return max(corrections, key=lambda x: x["count"])["correct_word"]    
    
    def get_learned_suggestion(self, word, context=None):
        word_key = word.lower()
        
        if word_key not in self.learned_corrections:
            return None
        
        corrections = self.learned_corrections[word_key]["corrections"]
        if not corrections:
            return None
        
        # Obtener contexto actual
        context_key = ""
        if context and len(context) > 0:
            context_words = context[-3:] if len(context) >= 3 else context
            context_key = " ".join(context_words).lower()
        
        # Buscar corrección exacta por contexto
        for correction in corrections:
            if correction["context"] == context_key:
                return correction["correct_word"]
        
        # Si no hay contexto exacto, usar BERT para evaluar la mejor opción
        if self.model_loaded and len(corrections) > 1 and context:
            return self.evaluate_corrections_with_bert(word, corrections, context)
        
        # Fallback: usar la corrección más frecuente
        best_correction = max(corrections, key=lambda x: x["count"])
        return best_correction["correct_word"]
    
    def simple_correct(self, word, context=None):
        if not word or len(word) < 2:
            return word
            
        word_lower = word.lower()
        
        # Buscar sugerencia aprendida con contexto
        learned_suggestion = self.get_learned_suggestion(word, context)
        if learned_suggestion:
            return learned_suggestion.capitalize() if word[0].isupper() else learned_suggestion
        
        # Si la palabra está en el diccionario, no corregir
        if word_lower in self.spell:
            return word
        
        # Usar corrección básica del diccionario
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
        return self.simple_correct(raw_word, self.current_context)
    
    def finish_word(self):
        if not self.word_buffer:
            return ""
        
        raw_word = ''.join(self.word_buffer)
        corrected = self.simple_correct(raw_word, self.current_context)
        
        # Guardar contexto y palabra para feedback
        self.last_context = self.current_context.copy()
        self.last_raw_word = raw_word
        self.last_corrected_word = corrected
        self.pending_feedback = True
        
        # Actualizar contexto para próxima palabra
        self.current_context.append(corrected.lower())
        if len(self.current_context) > 5:  # Mantener solo últimas 5 palabras
            self.current_context.pop(0)
        
        self.word_buffer = []
        return corrected
    
    def provide_feedback(self, correct_word):
        if self.pending_feedback and self.last_raw_word:
            # Usar el contexto guardado del momento de la corrección
            self.learn_correction(self.last_raw_word, correct_word, self.last_context)
            
            # Actualizar el contexto actual con la palabra corregida
            if len(self.current_context) > 0:
                self.current_context[-1] = correct_word.lower()
            
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