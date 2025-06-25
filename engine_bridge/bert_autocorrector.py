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
        
        # ✅ NUEVO: Sistema de feedback granular
        self.sentence_words = []  # Historial de palabras de la frase
        self.words_feedback = []  # Info para feedback de cada palabra
        
        # ✅ NUEVO: Sistema de frases exitosas mejorado
        self.successful_sentences_file = "dataset_bridge/successful_sentences.json"
        self.successful_sentences = []
        self.weighted_corrections_file = "dataset_bridge/weighted_corrections.json"
        self.weighted_corrections = defaultdict(float)  # ✅ NUEVO: Correcciones ponderadas
        self.load_successful_sentences()
        self.load_weighted_corrections()
        
        # ✅ NUEVO: Sistema de confirmación de calidad
        self.pending_sentence_confirmation = None
        self.sentence_feedback_requested = False
        
        # ✅ NUEVO: Métricas avanzadas de corrección
        self.session_quality_metrics = {
            "semantic_coherence": 0.0,
            "correction_precision": 0.0,
            "user_satisfaction": 0.0
        }
        
        # ✅ NUEVO: Sistema de limpieza de correcciones ineficaces
        self.correction_feedback_file = "dataset_bridge/correction_feedback.json"
        self.correction_feedback = defaultdict(lambda: {"positive": 0, "negative": 0, "error_count": 0})
        self.load_correction_feedback()
        
        # ✅ NUEVO: Análisis gramatical con spaCy
        self.pos_analysis_enabled = False
        self.nlp_pos = None
        self._init_pos_tagger()
        
        # ✅ NUEVO: Tracking de correcciones fallidas
        self.failed_corrections = defaultdict(int)
        self.correction_blacklist = set()  # Correcciones que han fallado mucho
        
        # ✅ NUEVO: Inicializar atributos de sesión
        self.session_start_time = None
        self.corrections_made_in_session = 0

    def _init_pos_tagger(self):
        """✅ NUEVO: Inicializar POS tagger para análisis gramatical"""
        try:
            # ✅ ARREGLO: Hacer importación completamente opcional
            try:
                import spacy
            except ImportError:
                print("⚠️ spaCy no instalado. Análisis gramatical deshabilitado")
                print("   💡 Para habilitarlo: pip install spacy")
                print("   💡 Luego instala modelo: python -m spacy download es_core_news_sm")
                return
            
            # Intentar cargar modelo en español
            try:
                self.nlp_pos = spacy.load("es_core_news_sm")
                self.pos_analysis_enabled = True
                print("✅ Análisis gramatical habilitado con spaCy (español)")
            except OSError:
                try:
                    # Fallback a modelo en inglés
                    self.nlp_pos = spacy.load("en_core_web_sm")
                    self.pos_analysis_enabled = True
                    print("⚠️ Usando modelo en inglés para análisis gramatical")
                    print("   💡 Para español: python -m spacy download es_core_news_sm")
                except OSError:
                    print("⚠️ spaCy instalado pero sin modelos disponibles")
                    print("   💡 Instala un modelo: python -m spacy download es_core_news_sm")
                    print("   💡 O modelo en inglés: python -m spacy download en_core_web_sm")
                    self.pos_analysis_enabled = False
                    self.nlp_pos = None
        except Exception as e:
            print(f"⚠️ Error inicializando análisis gramatical: {e}")
            self.pos_analysis_enabled = False
            self.nlp_pos = None

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
    
    def learn_correction(self, wrong_word, correct_word, context=None, original_context=None, word_position=-1, full_sentence_context=None):
        if not wrong_word or not correct_word or wrong_word == correct_word:
            return
        
        wrong_key = wrong_word.lower()
        correct_lower = correct_word.lower()
        
        # ✅ MEJORAR: Capturar contexto completo incluyendo la palabra actual
        context_data = {
            "original_context": "",      # Frase completa original
            "corrected_context": "",     # Frase con correcciones previas
            "position_in_sentence": word_position
        }
        
        # ✅ NUEVO: Usar contexto completo de la frase si está disponible
        if full_sentence_context:
            original_full = full_sentence_context.get("original_sentence", [])
            corrected_full = full_sentence_context.get("corrected_sentence", [])
            
            # Construir contexto completo
            if original_full:
                context_data["original_context"] = " ".join(original_full).lower()
            if corrected_full:
                context_data["corrected_context"] = " ".join(corrected_full).lower()
        else:
            # Fallback al método anterior
            if context and len(context) > 0:
                context_words = context if len(context) <= 5 else context[-5:]
                context_data["corrected_context"] = " ".join(context_words).lower()
            
            if original_context and len(original_context) > 0:
                original_words = original_context if len(original_context) <= 5 else original_context[-5:]
                context_data["original_context"] = " ".join(original_words).lower()
        
        # Buscar si ya existe una corrección similar
        existing_correction = None
        for correction in self.learned_corrections[wrong_key]["corrections"]:
            if (correction.get("corrected_context", correction.get("context", "")) == context_data["corrected_context"]):
                existing_correction = correction
                break
        
        if existing_correction:
            # Actualizar corrección existente
            existing_correction["correct_word"] = correct_lower
            existing_correction["count"] += 1
            # ✅ NUEVO: Actualizar con información completa
            existing_correction.update(context_data)
        else:
            # ✅ NUEVO: Estructura mejorada con más información
            correction_data = {
                "correct_word": correct_lower,
                "count": 1,
                **context_data
            }
            # Mantener compatibilidad con versión anterior
            correction_data["context"] = context_data["corrected_context"]
            
            self.learned_corrections[wrong_key]["corrections"].append(correction_data)
        
        self.learned_corrections[wrong_key]["count"] += 1
        
        # ✅ MEJORAR: Patrones más informativos
        pattern = f"{wrong_word.lower()}->{correct_word.lower()}"
        if context_data["original_context"]:
            pattern += f"[orig:{context_data['original_context']}]"
        if context_data["corrected_context"] and context_data["corrected_context"] != context_data["original_context"]:
            pattern += f"[corr:{context_data['corrected_context']}]"
        
        self.sequence_patterns[pattern] += 1
        
        self.save_learned_corrections()
        
        # Log mejorado
        context_info = ""
        if context_data["original_context"] and context_data["corrected_context"]:
            if context_data["original_context"] != context_data["corrected_context"]:
                context_info = f" (original: '{context_data['original_context']}' → corregido: '{context_data['corrected_context']}')"
            else:
                context_info = f" (contexto: '{context_data['corrected_context']}')"
        elif context_data["corrected_context"]:
            context_info = f" (contexto: '{context_data['corrected_context']}')"
            
        print(f"🧠 Aprendido: '{wrong_word}' → '{correct_word}'{context_info}")

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
        
        # ✅ NUEVO: Iniciar sesión si es la primera palabra
        if not self.session_start_time:
            self.session_start_time = time.time()
            self.corrections_made_in_session = 0
        
        raw_word = ''.join(self.word_buffer)
        
        # ✅ ARREGLO: Capturar contexto ANTES de agregar la palabra actual
        full_context = self.current_context.copy()  # Contexto completo previo
        
        corrected = self.simple_correct(raw_word, full_context)
        
        # ✅ NUEVO: Guardar contexto original de palabras detectadas
        if not hasattr(self, 'original_sentence_context'):
            self.original_sentence_context = []
        
        # ✅ GUARDAR información completa para feedback posterior
        word_info = {
            "raw_word": raw_word,
            "corrected_word": corrected,
            "context": full_context.copy(),
            "original_context": self.original_sentence_context.copy()  # ✅ NUEVO
        }
        self.words_feedback.append(word_info)
        self.sentence_words.append(corrected)
        
        # ✅ NUEVO: Actualizar contexto original con palabra detectada
        self.original_sentence_context.append(raw_word.lower())
        
        # Guardar contexto COMPLETO para feedback
        self.last_context = full_context
        self.last_original_context = self.original_sentence_context.copy()  # ✅ NUEVO
        self.last_raw_word = raw_word
        self.last_corrected_word = corrected
        self.pending_feedback = True
        
        # Actualizar contexto para próxima palabra
        self.current_context.append(corrected.lower())
        if len(self.current_context) > 10:
            self.current_context.pop(0)
        
        self.word_buffer = []
        return corrected
    
    def provide_feedback_for_word(self, word_position: int, correct_word: str):
        """✅ MEJORADO: Contar correcciones en sesión"""
        if 0 <= word_position < len(self.words_feedback):
            word_info = self.words_feedback[word_position]
            
            # ✅ NUEVO: Construir contexto completo de la frase
            original_sentence = []
            corrected_sentence = []
            
            # Construir frase original completa
            for i, feedback_info in enumerate(self.words_feedback):
                original_sentence.append(feedback_info["raw_word"])
                if i == word_position:
                    corrected_sentence.append(correct_word)  # Usar la corrección nueva
                else:
                    corrected_sentence.append(self.sentence_words[i])  # Usar palabra actual
            
            full_sentence_context = {
                "original_sentence": original_sentence,
                "corrected_sentence": corrected_sentence
            }
            
            # ✅ MEJORADO: Pasar contexto completo de frase
            self.learn_correction(
                word_info["raw_word"], 
                correct_word, 
                word_info["context"],  # Contexto previo (para compatibilidad)
                word_info.get("original_context", []),  # Contexto original previo
                word_position,  # Posición en la frase
                full_sentence_context  # ✅ NUEVO: Contexto completo
            )
            
            # Actualizar la frase
            old_word = self.sentence_words[word_position]
            self.sentence_words[word_position] = correct_word
            
            # ✅ MEJORAR: Actualizar contexto en palabras posteriores
            for i in range(word_position + 1, len(self.words_feedback)):
                # Actualizar contexto corregido en feedback info
                if len(self.words_feedback[i]["context"]) > word_position:
                    self.words_feedback[i]["context"][word_position] = correct_word.lower()
            
            # ✅ NUEVO: Actualizar contexto actual si es necesario
            if word_position < len(self.current_context):
                self.current_context[word_position] = correct_word.lower()
            
            print(f"🧠 Feedback aplicado a palabra {word_position + 1}: '{word_info['raw_word']}' → '{correct_word}'")
            print(f"📝 Frase actualizada: {self.get_sentence_string()}")
            print(f"🔍 Contexto original: {' '.join(original_sentence)}")
            print(f"🔍 Contexto corregido: {' '.join(corrected_sentence)}")
            return True
        return False
    
    def load_successful_sentences(self):
        """✅ NUEVO: Cargar frases exitosas guardadas"""
        try:
            if os.path.exists(self.successful_sentences_file):
                with open(self.successful_sentences_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.successful_sentences = data.get('sentences', [])
                print(f"📚 Cargadas {len(self.successful_sentences)} frases exitosas")
        except Exception as e:
            print(f"⚠️ Error cargando frases exitosas: {e}")
    
    def save_successful_sentences(self):
        """✅ NUEVO: Guardar frases exitosas"""
        try:
            os.makedirs(os.path.dirname(self.successful_sentences_file), exist_ok=True)
            data = {
                'sentences': self.successful_sentences,
                'total_sentences': len(self.successful_sentences),
                'last_updated': time.time(),
                'version': '1.0'
            }
            with open(self.successful_sentences_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Error guardando frases exitosas: {e}")
    
    def load_weighted_corrections(self):
        """✅ NUEVO: Cargar correcciones ponderadas por éxito"""
        try:
            if os.path.exists(self.weighted_corrections_file):
                with open(self.weighted_corrections_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.weighted_corrections = defaultdict(float, data.get('weights', {}))
                print(f"📊 Cargadas {len(self.weighted_corrections)} correcciones ponderadas")
        except Exception as e:
            print(f"⚠️ Error cargando correcciones ponderadas: {e}")

    def save_weighted_corrections(self):
        """✅ NUEVO: Guardar correcciones ponderadas"""
        try:
            os.makedirs(os.path.dirname(self.weighted_corrections_file), exist_ok=True)
            data = {
                'weights': dict(self.weighted_corrections),
                'last_updated': time.time(),
                'total_weights': len(self.weighted_corrections)
            }
            with open(self.weighted_corrections_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Error guardando correcciones ponderadas: {e}")

    def load_correction_feedback(self):
        """✅ NUEVO: Cargar feedback de correcciones"""
        try:
            if os.path.exists(self.correction_feedback_file):
                with open(self.correction_feedback_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    feedback_data = data.get('feedback', {})
                    for key, value in feedback_data.items():
                        self.correction_feedback[key] = value
                    
                    # Cargar lista negra de correcciones
                    self.correction_blacklist = set(data.get('blacklist', []))
                print(f"📊 Cargado feedback de {len(self.correction_feedback)} correcciones")
        except Exception as e:
            print(f"⚠️ Error cargando feedback de correcciones: {e}")

    def save_correction_feedback(self):
        """✅ NUEVO: Guardar feedback de correcciones"""
        try:
            os.makedirs(os.path.dirname(self.correction_feedback_file), exist_ok=True)
            data = {
                'feedback': dict(self.correction_feedback),
                'blacklist': list(self.correction_blacklist),
                'last_updated': time.time(),
                'stats': {
                    'total_tracked': len(self.correction_feedback),
                    'blacklisted': len(self.correction_blacklist)
                }
            }
            with open(self.correction_feedback_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Error guardando feedback de correcciones: {e}")

    def analyze_grammatical_context(self, sentence: str) -> dict:
        """✅ MEJORADO: Análisis gramatical con mejor manejo de errores"""
        if not self.pos_analysis_enabled or not self.nlp_pos or not sentence:
            return {}
        
        try:
            doc = self.nlp_pos(sentence)
            analysis = {
                "pos_tags": [],
                "grammar_patterns": {},
                "word_types": {"NOUN": [], "VERB": [], "ADJ": [], "ADV": [], "OTHER": []}
            }
            
            for token in doc:
                pos_info = {
                    "text": token.text,
                    "pos": token.pos_,
                    "tag": token.tag_,
                    "dep": token.dep_,
                    "lemma": token.lemma_
                }
                analysis["pos_tags"].append(pos_info)
                
                # Agrupar por tipos gramaticales
                if token.pos_ in ["NOUN", "PROPN"]:
                    analysis["word_types"]["NOUN"].append(token.text.lower())
                elif token.pos_ == "VERB":
                    analysis["word_types"]["VERB"].append(token.text.lower())
                elif token.pos_ == "ADJ":
                    analysis["word_types"]["ADJ"].append(token.text.lower())
                elif token.pos_ == "ADV":
                    analysis["word_types"]["ADV"].append(token.text.lower())
                else:
                    analysis["word_types"]["OTHER"].append(token.text.lower())
            
            # Identificar patrones gramaticales comunes
            pos_sequence = " ".join([token.pos_ for token in doc])
            analysis["grammar_patterns"]["sequence"] = pos_sequence
            
            return analysis
            
        except Exception as e:
            print(f"⚠️ Error en análisis gramatical: {e}")
            # ✅ NUEVO: Desactivar si hay errores recurrentes
            self.pos_analysis_enabled = False
            return {}

    def evaluate_corrections_with_bert_weighted(self, word, corrections, context):
        """✅ MEJORADO: Evaluación de BERT combinada con pesos de éxito"""
        try:
            # Crear contexto para BERT
            context_words = context[-3:] if len(context) >= 3 else context
            context_text = " ".join(context_words + ["[MASK]"])
            
            # Obtener sugerencias de BERT
            bert_suggestions = self.nlp(context_text, top_k=10)
            bert_words = [s['token_str'].lower() for s in bert_suggestions]
            
            # Evaluar cada corrección combinando BERT y pesos históricos
            best_correction = None
            best_score = -1
            
            for correction in corrections:
                correct_word = correction["correct_word"]
                score = 0
                
                # ✅ NUEVO: Peso histórico de éxito (40% de influencia)
                score += correction.get("weighted_score", correction["count"]) * 0.4
                
                # Puntuación de BERT (40% de influencia)
                if correct_word in bert_words:
                    bert_rank = bert_words.index(correct_word)
                    score += (10 - bert_rank) * 0.4
                
                # Similitud con BERT (20% de influencia)
                for bert_word in bert_words[:5]:
                    similarity = 1 - (Levenshtein.distance(correct_word, bert_word) / max(len(correct_word), len(bert_word)))
                    if similarity > 0.8:
                        score += similarity * 0.2
                        break
                
                if score > best_score:
                    best_score = score
                    best_correction = correction
            
            return best_correction["correct_word"] if best_correction else corrections[0]["correct_word"]
            
        except Exception as e:
            print(f"Error en evaluación BERT ponderada: {e}")
            # Fallback: usar corrección con mayor peso
            return max(corrections, key=lambda x: x.get("weighted_score", x["count"]))["correct_word"]

    def get_learned_suggestion_weighted(self, word, context=None):
        """✅ MEJORADO: Incluir filtro de correcciones blacklisted"""
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
        
        # ✅ NUEVO: Aplicar pesos de éxito y filtrar blacklisted
        weighted_corrections = []
        for correction in corrections:
            correction_key = f"{word_key}->{correction['correct_word']}"
            
            # ✅ NUEVO: Filtrar correcciones en blacklist
            if correction_key in self.correction_blacklist:
                continue
            
            base_score = correction["count"]
            weight_bonus = self.weighted_corrections.get(correction_key, 0.0)
            
            # ✅ NUEVO: Aplicar penalización por feedback negativo
            feedback = self.correction_feedback.get(correction_key, {"positive": 0, "negative": 0, "error_count": 0})
            negative_penalty = feedback["negative"] * 0.3
            error_penalty = feedback["error_count"] * 0.5
            
            final_score = base_score + (weight_bonus * 2) - negative_penalty - error_penalty
            
            # Solo incluir si el score es positivo
            if final_score > 0:
                weighted_corrections.append({
                    **correction,
                    "weighted_score": final_score,
                    "feedback_score": feedback["positive"] - feedback["negative"]
                })
        
        if not weighted_corrections:
            return None
        
        # Buscar corrección exacta por contexto (con peso)
        for correction in weighted_corrections:
            if correction["context"] == context_key:
                return correction["correct_word"]
        
        # Si no hay contexto exacto, usar la corrección con mayor peso
        if len(weighted_corrections) > 1:
            if self.model_loaded and context:
                return self.evaluate_corrections_with_bert_weighted(word, weighted_corrections, context)
            else:
                best_correction = max(weighted_corrections, key=lambda x: x["weighted_score"])
                return best_correction["correct_word"]
        
        return weighted_corrections[0]["correct_word"] if weighted_corrections else None

    def record_correction_feedback(self, correction_key: str, success: bool, error_type: str = None):
        """✅ NUEVO: Registrar feedback de una corrección"""
        if success:
            self.correction_feedback[correction_key]["positive"] += 1
        else:
            self.correction_feedback[correction_key]["negative"] += 1
            if error_type:
                self.correction_feedback[correction_key]["error_count"] += 1
        
        # ✅ NUEVO: Agregar a blacklist si hay muchos errores
        feedback = self.correction_feedback[correction_key]
        error_ratio = feedback["negative"] / max(1, feedback["positive"] + feedback["negative"])
        
        if (feedback["error_count"] >= 3 and error_ratio > 0.7):
            self.correction_blacklist.add(correction_key)
            print(f"⚠️ Corrección '{correction_key}' agregada a blacklist por bajo rendimiento")
        
        self.save_correction_feedback()

    def confirm_sentence_quality(self, is_correct: bool, user_satisfaction: int = 3):
        """✅ MEJORADO: Registrar feedback individual de correcciones"""
        if not self.pending_sentence_confirmation:
            print("❌ No hay frase pendiente de confirmación")
            return False
        
        record = self.pending_sentence_confirmation
        record["user_confirmed"] = is_correct
        record["user_satisfaction"] = user_satisfaction
        record["confirmation_timestamp"] = time.time()
        
        # ✅ NUEVO: Registrar feedback para cada corrección individual
        for detail in record["words_details"]:
            if detail["was_corrected"]:
                correction_key = f"{detail['original'].lower()}->{detail['corrected'].lower()}"
                
                if is_correct and user_satisfaction >= 3:
                    # Corrección exitosa
                    self.record_correction_feedback(correction_key, True)
                    weight_increment = user_satisfaction * 0.2
                    self.weighted_corrections[correction_key] += weight_increment
                else:
                    # Corrección fallida
                    error_type = "user_dissatisfaction" if user_satisfaction < 3 else "incorrect_sentence"
                    self.record_correction_feedback(correction_key, False, error_type)
        
        if is_correct and user_satisfaction >= 3:
            self.save_weighted_corrections()
            
            record["context_quality"] = self._get_final_quality_rating(
                record["semantic_coherence"], 
                record["correction_ratio_advanced"], 
                user_satisfaction
            )
            
            self.successful_sentences.append(record)
            self.save_successful_sentences()
            
            print(f"✅ Frase confirmada y guardada con calidad: {record['context_quality']}")
            print(f"📈 Pesos actualizados para {sum(1 for d in record['words_details'] if d['was_corrected'])} correcciones")
        else:
            print(f"❌ Frase no guardada - feedback negativo registrado")
        
        self.pending_sentence_confirmation = None
        self.sentence_feedback_requested = False
        return True

    def clean_ineffective_corrections(self) -> dict:
        """✅ NUEVO: Limpiar correcciones que han demostrado ser ineficaces"""
        cleaned_count = 0
        total_before = len(self.learned_corrections)
        
        keys_to_remove = []
        
        for word_key, word_data in self.learned_corrections.items():
            corrections_to_keep = []
            
            for correction in word_data["corrections"]:
                correction_key = f"{word_key}->{correction['correct_word']}"
                
                # Verificar si está en blacklist o tiene mal rendimiento
                if correction_key in self.correction_blacklist:
                    cleaned_count += 1
                    continue
                
                feedback = self.correction_feedback.get(correction_key, {"positive": 0, "negative": 0, "error_count": 0})
                total_feedback = feedback["positive"] + feedback["negative"]
                
                if total_feedback >= 5:  # Solo evaluar con suficiente feedback
                    success_rate = feedback["positive"] / total_feedback
                    if success_rate < 0.3:  # Menos del 30% de éxito
                        cleaned_count += 1
                        self.correction_blacklist.add(correction_key)
                        continue
                
                corrections_to_keep.append(correction)
            
            if corrections_to_keep:
                word_data["corrections"] = corrections_to_keep
                word_data["count"] = sum(c["count"] for c in corrections_to_keep)
            else:
                keys_to_remove.append(word_key)
        
        # Eliminar palabras sin correcciones válidas
        for key in keys_to_remove:
            del self.learned_corrections[key]
            cleaned_count += 1
        
        if cleaned_count > 0:
            self.save_learned_corrections()
            self.save_correction_feedback()
            print(f"🧹 Limpieza completada: {cleaned_count} correcciones ineficaces removidas")
        
        return {
            "cleaned_corrections": cleaned_count,
            "total_before": total_before,
            "total_after": len(self.learned_corrections),
            "blacklisted_corrections": len(self.correction_blacklist)
        }

    def get_bert_training_suggestions(self) -> dict:
        """✅ MEJORADO: Análisis gramatical opcional y mejor manejo"""
        if not self.successful_sentences:
            return {"message": "No hay suficientes datos para sugerencias"}
        
        high_quality_sentences = [s for s in self.successful_sentences 
                                if s.get("context_quality") in ["excellent", "good"] 
                                and s.get("user_confirmed", False)]
        
        if len(high_quality_sentences) < 5:
            return {"message": "Necesitas al menos 5 frases de alta calidad confirmadas"}
        
        # ✅ MEJORADO: Análisis gramatical completamente opcional
        training_data = []
        grammatical_analysis = {
            "error_patterns": defaultdict(list),
            "pos_corrections": {"NOUN": [], "VERB": [], "ADJ": [], "ADV": [], "OTHER": []},
            "common_mistakes": defaultdict(int),
            "context_patterns": defaultdict(list),
            "analysis_enabled": self.pos_analysis_enabled
        }
        
        for sentence in high_quality_sentences:
            # ✅ MEJORADO: Análisis gramatical solo si está disponible
            grammar_info = {}
            if self.pos_analysis_enabled and self.nlp_pos:
                grammar_info = self.analyze_grammatical_context(sentence["corrected_sentence"])
            
            for detail in sentence["words_details"]:
                if detail["was_corrected"]:
                    original_word = detail["original"]
                    corrected_word = detail["corrected"]
                    
                    # Crear ejemplo de entrenamiento contextual
                    context_words = sentence["original_sentence"].split()
                    masked_context = context_words.copy()
                    masked_context[detail["position"]] = "[MASK]"
                    
                    training_example = {
                        "input": " ".join(masked_context),
                        "target": corrected_word,
                        "context_quality": sentence["context_quality"],
                        "user_satisfaction": sentence.get("user_satisfaction", 3),
                        "original_word": original_word,
                        "correction_type": self._classify_correction_type(original_word, corrected_word)
                    }
                    
                    training_data.append(training_example)
                    
                    # ✅ MEJORADO: Análisis gramatical solo si está disponible
                    if self.pos_analysis_enabled and grammar_info and grammar_info.get("pos_tags"):
                        pos_tags = grammar_info.get("pos_tags", [])
                        if detail["position"] < len(pos_tags):
                            word_pos = pos_tags[detail["position"]]["pos"]
                            
                            # Clasificar por categoría gramatical
                            if word_pos in ["NOUN", "PROPN"]:
                                grammatical_analysis["pos_corrections"]["NOUN"].append(training_example)
                            elif word_pos == "VERB":
                                grammatical_analysis["pos_corrections"]["VERB"].append(training_example)
                            elif word_pos == "ADJ":
                                grammatical_analysis["pos_corrections"]["ADJ"].append(training_example)
                            elif word_pos == "ADV":
                                grammatical_analysis["pos_corrections"]["ADV"].append(training_example)
                            else:
                                grammatical_analysis["pos_corrections"]["OTHER"].append(training_example)
                        
                        # Patrones de error comunes
                        error_pattern = f"{word_pos}:{original_word}->{corrected_word}"
                        grammatical_analysis["error_patterns"][word_pos].append({
                            "original": original_word,
                            "corrected": corrected_word,
                            "frequency": 1
                        })
                    
                    # Conteo de errores comunes (siempre disponible)
                    mistake_key = f"{original_word}->{corrected_word}"
                    grammatical_analysis["common_mistakes"][mistake_key] += 1
        
        # Análisis de patrones más frecuentes
        most_common_mistakes = dict(Counter(grammatical_analysis["common_mistakes"]).most_common(10))
        
        # Recomendaciones básicas
        recommendations = [
            "Fine-tune BERT con estos ejemplos contextuales",
            "Usar weighted sampling basado en user_satisfaction",
            "Aplicar data augmentation en ejemplos de alta calidad"
        ]
        
        # ✅ MEJORADO: Recomendaciones específicas solo si análisis gramatical está disponible
        if self.pos_analysis_enabled:
            for pos, corrections in grammatical_analysis["pos_corrections"].items():
                if len(corrections) >= 3:
                    recommendations.append(f"Entrenar específicamente para errores en {pos} ({len(corrections)} ejemplos)")
        else:
            recommendations.append("💡 Instala spaCy para análisis gramatical avanzado: pip install spacy")
        
        return {
            "training_examples": len(training_data),
            "high_quality_sentences": len(high_quality_sentences),
            "training_data": training_data[:50],
            "grammatical_analysis": {
                "analysis_enabled": self.pos_analysis_enabled,
                "pos_distribution": {k: len(v) for k, v in grammatical_analysis["pos_corrections"].items()},
                "most_common_mistakes": most_common_mistakes,
                "error_patterns_by_pos": {k: len(v) for k, v in grammatical_analysis["error_patterns"].items()}
            },
            "recommendations": recommendations,
            "cleanup_needed": len(self.correction_blacklist) > 0
        }

    def _classify_correction_type(self, original: str, corrected: str) -> str:
        """✅ NUEVO: Clasificar tipo de corrección"""
        if not original or not corrected:
            return "unknown"
        
        distance = Levenshtein.distance(original.lower(), corrected.lower())
        length_diff = abs(len(original) - len(corrected))
        
        if distance == 0:
            return "no_change"
        elif distance == 1 and length_diff == 0:
            return "substitution"
        elif distance == 1 and length_diff == 1:
            return "insertion" if len(corrected) > len(original) else "deletion"
        elif length_diff > 2:
            return "major_rewrite"
        else:
            return "minor_edit"

    def get_correction_health_report(self) -> dict:
        """✅ NUEVO: Reporte de salud del sistema de correcciones"""
        total_corrections = len(self.learned_corrections)
        blacklisted = len(self.correction_blacklist)
        
        # Análisis de feedback
        positive_feedback = sum(f["positive"] for f in self.correction_feedback.values())
        negative_feedback = sum(f["negative"] for f in self.correction_feedback.values())
        total_feedback = positive_feedback + negative_feedback
        
        success_rate = positive_feedback / total_feedback if total_feedback > 0 else 0
        
        # Correcciones con suficiente feedback para análisis
        reliable_corrections = sum(1 for f in self.correction_feedback.values() 
                                 if (f["positive"] + f["negative"]) >= 3)
        
        return {
            "total_corrections": total_corrections,
            "blacklisted_corrections": blacklisted,
            "blacklist_percentage": round(blacklisted / total_corrections * 100, 2) if total_corrections > 0 else 0,
            "feedback_stats": {
                "total_feedback_events": total_feedback,
                "positive_feedback": positive_feedback,
                "negative_feedback": negative_feedback,
                "success_rate": round(success_rate * 100, 2)
            },
            "reliability": {
                "corrections_with_feedback": len(self.correction_feedback),
                "reliable_corrections": reliable_corrections,
                "reliability_percentage": round(reliable_corrections / total_corrections * 100, 2) if total_corrections > 0 else 0
            },
            "recommendations": self._get_health_recommendations(success_rate, blacklisted, total_corrections)
        }

    def _get_health_recommendations(self, success_rate: float, blacklisted: int, total: int) -> list:
        """✅ NUEVO: Generar recomendaciones basadas en salud del sistema"""
        recommendations = []
        
        if success_rate < 0.7:
            recommendations.append("⚠️ Tasa de éxito baja - Revisar calidad de correcciones")
        
        if blacklisted / total > 0.1 if total > 0 else False:
            recommendations.append("🧹 Alto número de correcciones blacklisted - Ejecutar limpieza")
        
        if total < 10:
            recommendations.append("📚 Pocas correcciones aprendidas - Necesita más entrenamiento")
        
        if len(recommendations) == 0:
            recommendations.append("✅ Sistema funcionando correctamente")
        
        return recommendations
    
    def get_sentence_words(self):
        """✅ NUEVO: Obtener palabras de la frase actual"""
        return [(i, word) for i, word in enumerate(self.sentence_words)]
    
    def remove_word(self, word_position: int):
        """✅ NUEVO: Eliminar palabra de la frase"""
        if 0 <= word_position < len(self.sentence_words):
            removed_word = self.sentence_words.pop(word_position)
            self.words_feedback.pop(word_position)
            
            # Actualizar posiciones en words_feedback
            for i in range(word_position, len(self.words_feedback)):
                self.words_feedback[i]["position"] = i
            
            print(f"🗑️ Palabra eliminada: '{removed_word}' (posición {word_position + 1})")
            return True
        return False
    
    def get_sentence_string(self):
        """✅ NUEVO: Obtener frase como string"""
        return " ".join(self.sentence_words)
    
    def end_sentence(self):
        """✅ MEJORADO: Solicitar confirmación de calidad antes de guardar"""
        if not self.sentence_words:
            return ""
        
        sentence = self.get_sentence_string()
        
        # ✅ NUEVO: Construir información completa de la frase
        if self.words_feedback:
            original_sentence = " ".join([info["raw_word"] for info in self.words_feedback])
            corrected_sentence = sentence
            
            # ✅ MEJORADO: Métricas avanzadas de calidad
            session_duration = time.time() - (self.session_start_time or time.time())
            word_count = len(self.sentence_words)
            
            # ✅ NUEVO: Ratio de corrección mejorado con Levenshtein
            correction_ratio_advanced = self.calculate_levenshtein_ratio(original_sentence, corrected_sentence)
            
            # ✅ NUEVO: Evaluación de coherencia semántica
            semantic_coherence = self.evaluate_semantic_coherence_with_bert(corrected_sentence)
            
            # ✅ NUEVO: Crear registro mejorado
            sentence_record = {
                "id": f"sentence_{int(time.time())}_{len(self.successful_sentences)}",
                "timestamp": time.time(),
                "original_sentence": original_sentence,
                "corrected_sentence": corrected_sentence,
                "word_count": word_count,
                "corrections_made": self.corrections_made_in_session,
                "correction_ratio_simple": round(self.corrections_made_in_session / word_count if word_count > 0 else 0, 2),
                "correction_ratio_advanced": correction_ratio_advanced,  # ✅ NUEVO
                "semantic_coherence": semantic_coherence,  # ✅ NUEVO
                "session_duration_seconds": round(session_duration, 2),
                "words_details": [
                    {
                        "position": i,
                        "original": info["raw_word"],
                        "corrected": self.sentence_words[i],
                        "was_corrected": info["raw_word"].lower() != self.sentence_words[i].lower(),
                        "levenshtein_distance": Levenshtein.distance(info["raw_word"].lower(), self.sentence_words[i].lower())  # ✅ NUEVO
                    }
                    for i, info in enumerate(self.words_feedback)
                ],
                "difficulty_score": self._calculate_difficulty_score_advanced(original_sentence, corrected_sentence, semantic_coherence),
                "context_quality": self._assess_context_quality_advanced(semantic_coherence, correction_ratio_advanced),
                "requires_confirmation": True,  # ✅ NUEVO: Requiere confirmación del usuario
                "user_confirmed": False
            }
            
            # ✅ NUEVO: Guardar como pendiente de confirmación
            self.pending_sentence_confirmation = sentence_record
            self.sentence_feedback_requested = True
            
            print(f"📝 Frase completada: '{corrected_sentence}'")
            print(f"📊 Coherencia semántica: {semantic_coherence:.2f}")
            print(f"🔧 Ratio de corrección: {correction_ratio_advanced:.2f}")
            print(f"💡 IMPORTANTE: ¿Esta frase está correcta? Usa 'confirm_sentence()' para confirmar")
        
        # Resetear para nueva sesión (pero mantener pending confirmation)
        current_sentence = sentence
        self.sentence_words = []
        self.words_feedback = []
        self.current_context = []
        self.original_sentence_context = []
        self.pending_feedback = False
        self.session_start_time = None
        self.corrections_made_in_session = 0
        
        return current_sentence

    def calculate_levenshtein_ratio(self, original: str, corrected: str) -> float:
        """✅ NUEVO: Calcular ratio de corrección por palabra con distancia de edición"""
        if not original or not corrected:
            return 0.0
        
        original_words = original.lower().split()
        corrected_words = corrected.lower().split()
        
        total_ratio = 0.0
        word_count = max(len(original_words), len(corrected_words))
        
        for i in range(word_count):
            orig_word = original_words[i] if i < len(original_words) else ""
            corr_word = corrected_words[i] if i < len(corrected_words) else ""
            
            if orig_word and corr_word:
                distance = Levenshtein.distance(orig_word, corr_word)
                max_len = max(len(orig_word), len(corr_word))
                ratio = distance / max_len if max_len > 0 else 0.0
                total_ratio += ratio
            elif orig_word or corr_word:  # Palabra añadida o eliminada
                total_ratio += 1.0
        
        return round(total_ratio / word_count if word_count > 0 else 0.0, 3)

    def evaluate_semantic_coherence_with_bert(self, sentence: str) -> float:
        """✅ NUEVO: Evaluar coherencia semántica usando BERT"""
        if not self.model_loaded or not sentence:
            return 0.5  # Neutral si no hay BERT
        
        try:
            words = sentence.split()
            if len(words) < 2:
                return 0.8  # Frases muy cortas son generalmente coherentes
            
            total_score = 0.0
            evaluations = 0
            
            # Evaluar cada palabra en contexto usando BERT
            for i, word in enumerate(words):
                context_words = words.copy()
                context_words[i] = '[MASK]'
                context = ' '.join(context_words)
                
                try:
                    predictions = self.nlp(context, top_k=10)
                    # Buscar si la palabra original está en las predicciones
                    word_lower = word.lower()
                    for j, pred in enumerate(predictions):
                        if pred['token_str'].lower() == word_lower:
                            # Puntuación basada en la posición en predicciones (0-1)
                            score = max(0.1, 1.0 - (j / 10))
                            total_score += score
                            evaluations += 1
                            break
                    else:
                        # Si no está en top 10, dar puntuación baja pero no cero
                        total_score += 0.1
                        evaluations += 1
                except Exception:
                    evaluations += 1  # Contar pero no sumar puntuación
            
                coherence = total_score / evaluations if evaluations > 0 else 0.5
                return round(min(1.0, coherence), 3)
                    
        except Exception as e:
            print(f"⚠️ Error evaluando coherencia semántica: {e}")
            return 0.5

    def get_learning_stats(self) -> dict:
        """✅ NUEVO: Obtener estadísticas de aprendizaje"""
        total_corrections = len(self.learned_corrections)
        total_patterns = len(self.sequence_patterns)
        
        # Calcular correcciones por palabra
        corrections_per_word = {}
        for word, data in self.learned_corrections.items():
            corrections_per_word[word] = len(data.get("corrections", []))
        
        # Palabras más corregidas
        most_corrected = sorted(corrections_per_word.items(), 
                            key=lambda x: x[1], reverse=True)[:5]
        
        # Estadísticas de feedback
        feedback_stats = {
            "total_feedback": len(self.correction_feedback),
            "blacklisted": len(self.correction_blacklist),
            "weighted_corrections": len(self.weighted_corrections)
        }
        
        return {
            "total_corrections": total_corrections,
            "total_patterns": total_patterns,
            "corrections_per_word": corrections_per_word,
            "most_corrected_words": most_corrected,
            "feedback_stats": feedback_stats,
            "successful_sentences": len(self.successful_sentences),
            "pending_confirmation": self.pending_sentence_confirmation is not None,
            "session_active": self.session_start_time is not None
        }

    def _calculate_difficulty_score_advanced(self, original: str, corrected: str, semantic_coherence: float) -> str:
        """✅ NUEVO: Calcular puntuación de dificultad avanzada"""
        if not original or not corrected:
            return "unknown"
        
        # Factores de dificultad
        word_count = len(original.split())
        correction_ratio = self.calculate_levenshtein_ratio(original, corrected)
        
        # Calcular puntuación compuesta
        difficulty_score = 0.0
        
        # Factor de longitud (10% - frases más largas son más difíciles)
        if word_count <= 3:
            difficulty_score += 0.1
        elif word_count <= 6:
            difficulty_score += 0.3
        else:
            difficulty_score += 0.5
        
        # Factor de corrección (40% - más correcciones = más difícil)
        difficulty_score += correction_ratio * 0.4
        
        # Factor de coherencia semántica (50% - menos coherencia = más difícil)
        difficulty_score += (1.0 - semantic_coherence) * 0.5
        
        # Clasificar dificultad
        if difficulty_score <= 0.3:
            return "easy"
        elif difficulty_score <= 0.6:
            return "medium"
        elif difficulty_score <= 0.8:
            return "hard"
        else:
            return "very_hard"

    def _assess_context_quality_advanced(self, semantic_coherence: float, correction_ratio: float) -> str:
        """✅ NUEVO: Evaluar calidad del contexto avanzada"""
        # Calcular puntuación de calidad
        quality_score = semantic_coherence * 0.7 + (1.0 - correction_ratio) * 0.3
        
        if quality_score >= 0.8:
            return "excellent"
        elif quality_score >= 0.6:
            return "good"
        elif quality_score >= 0.4:
            return "fair"
        else:
            return "poor"

    def _get_final_quality_rating(self, semantic_coherence: float, correction_ratio: float, user_satisfaction: int) -> str:
        """✅ NUEVO: Obtener calificación final de calidad"""
        # Normalizar satisfacción del usuario (1-5 -> 0-1)
        user_score = (user_satisfaction - 1) / 4.0
        
        # Combinar métricas
        final_score = (semantic_coherence * 0.4 + 
                    (1.0 - correction_ratio) * 0.3 + 
                    user_score * 0.3)
        
        if final_score >= 0.8:
            return "excellent"
        elif final_score >= 0.6:
            return "good"
        elif final_score >= 0.4:
            return "acceptable"
        else:
            return "needs_improvement"

    def confirm_sentence(self, is_correct: bool = True, satisfaction: int = 4):
        """✅ NUEVO: Método simplificado para confirmar frase"""
        return self.confirm_sentence_quality(is_correct, satisfaction)

    def get_stats(self) -> dict:
        """✅ NUEVO: Alias para get_learning_stats para compatibilidad"""
        return self.get_learning_stats()

    def get_successful_sentences_stats(self) -> dict:
        """✅ NUEVO: Obtener estadísticas de frases exitosas"""
        if not self.successful_sentences:
            return {"total": 0}
        
        total_sentences = len(self.successful_sentences)
        
        # Calcular estadísticas básicas
        word_counts = [s.get("word_count", 0) for s in self.successful_sentences]
        correction_counts = [s.get("corrections_made", 0) for s in self.successful_sentences]
        
        # Distribución de calidad
        quality_distribution = {}
        for sentence in self.successful_sentences:
            quality = sentence.get("context_quality", "unknown")
            quality_distribution[quality] = quality_distribution.get(quality, 0) + 1
        
        # Métricas promedio
        avg_words = sum(word_counts) / total_sentences if total_sentences > 0 else 0
        avg_corrections = sum(correction_counts) / total_sentences if total_sentences > 0 else 0
        
        # Estadísticas de satisfacción del usuario
        satisfaction_scores = [s.get("user_satisfaction", 3) for s in self.successful_sentences if s.get("user_confirmed", False)]
        avg_satisfaction = sum(satisfaction_scores) / len(satisfaction_scores) if satisfaction_scores else 0
        
        return {
            "total": total_sentences,
            "avg_words_per_sentence": round(avg_words, 1),
            "avg_corrections_per_sentence": round(avg_corrections, 1),
            "quality_distribution": quality_distribution,
            "avg_user_satisfaction": round(avg_satisfaction, 1),
            "confirmed_sentences": len([s for s in self.successful_sentences if s.get("user_confirmed", False)]),
            "pending_confirmation": 1 if self.pending_sentence_confirmation else 0
        }

    def clear_buffer(self):
        """✅ NUEVO: Limpiar buffer de palabras"""
        self.word_buffer.clear()
        print("🧹 Buffer limpiado")