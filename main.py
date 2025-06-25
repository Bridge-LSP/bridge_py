import cv2
import mediapipe as mp
from engine_bridge.hand_tracker import create_hand_landmarker
from utils.hand_landmarks_visualizer import draw_landmarks, draw_connections, draw_handedness_label
from utils.hand_tracking_config import CAMERA_WIDTH, CAMERA_HEIGHT
from utils.bridge_utils import save_landmark_to_json
from engine_bridge.autocorrector.autocorrector_core import AutoCorrector
import joblib
import numpy as np
import time

MODEL_PATH = 'models/forest_model_u.pkl'
svm_model = joblib.load(MODEL_PATH)

current_word = ""
last_prediction = None
last_time = 0
COOLDOWN_TIME = 1.0 
letra_actual = ""
palabras_completadas = []
sentence = "" 

autocorrector = AutoCorrector()

PAUSE_THRESHOLD = 3.0 
last_letter_time = 0
word_finalized = False

feedback_mode = False
current_word_for_feedback = ""

def extract_features(landmarks):
    features = []
    for lm in landmarks:
        features.extend([lm.x, lm.y, lm.z])
    return np.array(features).reshape(1, -1)

def draw_interface(frame):
    frame_height, frame_width = frame.shape[:2]
    
    cv2.rectangle(frame, (10, 10), (frame_width - 10, 300), (240, 240, 240), -1)
    cv2.rectangle(frame, (10, 10), (frame_width - 10, 300), (100, 100, 100), 2)
    
    raw_word = ''.join(autocorrector.word_buffer)
    cv2.putText(frame, f"Detectando: {raw_word}", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2)
    
    corrected_word = autocorrector.get_current_word_corrected()
    cv2.putText(frame, f"Corrigiendo: {corrected_word}", (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 150, 0), 2)
    
    # ✅ Mostrar frase completa
    sentence = autocorrector.get_sentence_string()
    cv2.putText(frame, f"Frase: {sentence}", (20, 110),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 200), 2)
    
    # ✅ Mostrar palabras numeradas para feedback
    words = autocorrector.get_sentence_words()
    if words:
        y_offset = 140
        words_text = " | ".join([f"{i+1}.{word}" for i, word in words])
        cv2.putText(frame, f"Palabras: {words_text}", (20, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 0, 150), 2)
    
    if feedback_mode:
        cv2.rectangle(frame, (10, 170), (frame_width - 10, 220), (255, 255, 0), -1)
        cv2.putText(frame, f"FEEDBACK: Escribe número de palabra + corrección", (20, 190),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        cv2.putText(frame, f"Ejemplo: '2 hola' para corregir palabra 2 a 'hola'", (20, 210),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    
    instruction_y = 280 if feedback_mode else 240
    cv2.putText(frame, "3s=palabra | 'f'=feedback | 'e'=fin frase | 'd'=eliminar | 'r'=reset", 
                (20, instruction_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (80, 80, 80), 1)
    
    stats = autocorrector.get_learning_stats()
    sentence_stats = autocorrector.get_successful_sentences_stats()
    
    cv2.putText(frame, f"Aprendidas: {stats['total_corrections']} correcciones | {sentence_stats.get('total', 0)} frases", 
                (20, instruction_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 100, 0), 1)
    
    if letra_actual:
        text_y = frame_height - 100
        cv2.rectangle(frame, (10, text_y - 40), (100, text_y + 10), (255, 255, 255), -1)
        cv2.rectangle(frame, (10, text_y - 40), (100, text_y + 10), (0, 0, 0), 2)
        cv2.putText(frame, letra_actual, (25, text_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)

def handle_feedback_input():
    global feedback_mode
    
    print(f"\n🔄 MODO FEEDBACK AVANZADO")
    words = autocorrector.get_sentence_words()
    
    if not words:
        print("❌ No hay palabras para corregir")
        feedback_mode = False
        return
    
    print("📝 Palabras actuales:")
    for i, word in words:
        print(f"  {i+1}. {word}")
    
    print("\nOpciones:")
    print("• Número + palabra: '2 hola' (corregir palabra 2)")
    print("• 'd' + número: 'd2' (eliminar palabra 2)")  
    print("• 'c' (cancelar)")
    
    user_input = input("Tu comando: ").strip()
    
    if user_input.lower() == 'c':
        print("❌ Feedback cancelado")
    elif user_input.lower().startswith('d'):
        # Eliminar palabra
        try:
            word_num = int(user_input[1:]) - 1
            if autocorrector.remove_word(word_num):
                print("✅ Palabra eliminada")
            else:
                print("❌ Número de palabra inválido")
        except:
            print("❌ Formato inválido. Usa 'd1', 'd2', etc.")
    else:
        # Corregir palabra
        parts = user_input.split(' ', 1)
        if len(parts) == 2:
            try:
                word_num = int(parts[0]) - 1
                correct_word = parts[1]
                if autocorrector.provide_feedback_for_word(word_num, correct_word):
                    print("✅ Corrección aplicada")
                else:
                    print("❌ Número de palabra inválido")
            except:
                print("❌ Formato inválido. Usa '1 palabra', '2 casa', etc.")
        else:
            print("❌ Formato inválido")
    
    feedback_mode = False

def handle_word_deletion():
    """✅ NUEVO: Manejar eliminación interactiva de palabras"""
    global feedback_mode
    
    print(f"\n🗑️ MODO ELIMINACIÓN DE PALABRAS")
    words = autocorrector.get_sentence_words()
    
    if not words:
        print("❌ No hay palabras para eliminar")
        return
    
    print("📝 Palabras actuales:")
    for i, word in words:
        print(f"  {i+1}. {word}")
    
    print("\nOpciones:")
    print("• Número de palabra: '2' (eliminar palabra 2)")
    print("• 'c' (cancelar)")
    
    user_input = input("¿Qué palabra quieres eliminar?: ").strip()
    
    if user_input.lower() == 'c':
        print("❌ Eliminación cancelada")
    else:
        try:
            word_num = int(user_input) - 1
            if autocorrector.remove_word(word_num):
                print("✅ Palabra eliminada exitosamente")
                # Mostrar frase actualizada
                updated_sentence = autocorrector.get_sentence_string()
                print(f"📝 Frase actualizada: {updated_sentence}")
            else:
                print("❌ Número de palabra inválido")
        except ValueError:
            print("❌ Formato inválido. Usa un número (1, 2, 3...)")

def handle_sentence_confirmation():
    """✅ NUEVO: Manejar confirmación de calidad de frase"""
    if not autocorrector.sentence_feedback_requested:
        print("❌ No hay frase pendiente de confirmación")
        return
    
    record = autocorrector.pending_sentence_confirmation
    if not record:
        print("❌ Error: No se encontró información de la frase")
        return
    
    print(f"\n📝 CONFIRMACIÓN DE CALIDAD DE FRASE")
    print(f"📄 Original: '{record['original_sentence']}'")
    print(f"✅ Corregida: '{record['corrected_sentence']}'")
    print(f"📊 Coherencia semántica: {record['semantic_coherence']:.2f}")
    print(f"🔧 Ratio de corrección: {record['correction_ratio_advanced']:.2f}")
    print(f"⏱️ Duración: {record['session_duration_seconds']:.1f}s")
    
    print(f"\n¿La frase final está correcta?")
    print("1. Sí, perfecta")
    print("2. Sí, aceptable") 
    print("3. Regular")
    print("4. Mala")
    print("5. Muy mala")
    
    try:
        choice = input("Tu evaluación (1-5): ").strip()
        satisfaction = int(choice)
        
        if satisfaction < 1 or satisfaction > 5:
            print("❌ Opción inválida")
            return
        
        is_correct = satisfaction >= 3  # 3 o más se considera aceptable
        
        if autocorrector.confirm_sentence_quality(is_correct, satisfaction):
            if is_correct:
                print(f"✅ ¡Gracias! La frase se guardó para mejorar el sistema")
            else:
                print(f"📝 Entendido. La frase no se guardará y el sistema aprenderá")
        
    except ValueError:
        print("❌ Por favor ingresa un número del 1 al 5")

def main():
    global current_word, last_prediction, last_time, letra_actual
    global sentence, last_letter_time, word_finalized
    global feedback_mode, current_word_for_feedback

    hand_landmarker = create_hand_landmarker(running_mode="VIDEO")
    cap = cv2.VideoCapture(0)
    cap.set(3, CAMERA_WIDTH)
    cap.set(4, CAMERA_HEIGHT)

    cv2.namedWindow("Sign Language Recognition - Auto Corrector")

    print("🚀 Sistema iniciado con aprendizaje automático!")
    print("📝 Las palabras se completarán automáticamente después de 3 segundos de pausa")
    print("🧠 Presiona 'f' después de una palabra para dar retroalimentación")
    print("✨ Nuevas funciones: 'e' = fin frase, 'd' = eliminar palabra, 'c' = confirmar calidad")
    print("🧹 Comando 'h' = reporte de salud, 'x' = limpieza automática")
    print("💾 Las frases exitosas se guardan automáticamente para entrenar BERT")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
        timestamp_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))
        results = hand_landmarker.detect_for_video(mp_image, timestamp_ms)

        current_time = time.time()
        letter_detected = False

        if results.hand_landmarks and not feedback_mode:
            for idx, landmarks in enumerate(results.hand_landmarks):
                draw_landmarks(frame, landmarks, frame.shape[1], frame.shape[0])
                draw_connections(frame, landmarks, frame.shape[1], frame.shape[0])

                world_landmarks = results.hand_world_landmarks[idx]
                features = extract_features(world_landmarks)
                prediction = svm_model.predict(features)[0]

                if prediction != last_prediction and (current_time - last_time) > COOLDOWN_TIME:
                    letra_actual = prediction.upper()
                    last_prediction = prediction
                    last_time = current_time
                    last_letter_time = current_time
                    
                    autocorrector.add_letter(letra_actual.lower())
                    letter_detected = True
                    word_finalized = False
                    
                    print(f"✅ Letra detectada: {letra_actual}")

        if (not letter_detected and 
            autocorrector.word_buffer and 
            current_time - last_letter_time > PAUSE_THRESHOLD and 
            not word_finalized and not feedback_mode):
            
            corrected_word = autocorrector.finish_word()
            if corrected_word and corrected_word.strip():
                if sentence:
                    sentence += " " + corrected_word
                else:
                    sentence = corrected_word
                
                print(f"🔧 Palabra completada y corregida: {corrected_word}")
                print(f"📝 Frase actual: {sentence}")
                print("💡 Presiona 'f' si la corrección fue incorrecta")
            
            word_finalized = True
            letra_actual = ""

        # ✅ Actualizar sentence desde el autocorrector
        sentence = autocorrector.get_sentence_string()

        draw_interface(frame)
        cv2.imshow("Sign Language Recognition - Auto Corrector", frame)

        key = cv2.waitKey(5) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("h") and not feedback_mode:
            # ✅ NUEVO: Reporte de salud del sistema
            health_report = autocorrector.get_correction_health_report()
            print(f"\n📊 REPORTE DE SALUD DEL SISTEMA:")
            print(f"   📚 Total correcciones: {health_report['total_corrections']}")
            print(f"   ⚠️ Blacklisted: {health_report['blacklisted_corrections']} ({health_report['blacklist_percentage']}%)")
            print(f"   ✅ Tasa de éxito: {health_report['feedback_stats']['success_rate']}%")
            print(f"   📈 Confiabilidad: {health_report['reliability']['reliability_percentage']}%")
            for rec in health_report['recommendations']:
                print(f"   {rec}")
        elif key == ord("x") and not feedback_mode:
            # ✅ NUEVO: Limpieza automática
            print(f"\n🧹 Ejecutando limpieza automática...")
            cleanup_result = autocorrector.clean_ineffective_corrections()
            print(f"   Correcciones removidas: {cleanup_result['cleaned_corrections']}")
            print(f"   Total antes: {cleanup_result['total_before']}")
            print(f"   Total después: {cleanup_result['total_after']}")
        elif key == ord("r"):
            # Reset completo
            autocorrector.clear_buffer()
            autocorrector.end_sentence()
            sentence = ""
            letra_actual = ""
            last_prediction = None
            word_finalized = False
            feedback_mode = False
            print("🔄 Sistema reiniciado")
        elif key == ord("e"):
            # ✅ NUEVO: Finalizar frase
            if autocorrector.sentence_words:
                final_sentence = autocorrector.end_sentence()
                print(f"✅ Frase finalizada: '{final_sentence}'")
                sentence = ""
                letra_actual = ""
                word_finalized = False
            else:
                print("❌ No hay frase que finalizar")
        elif key == ord("d") and not feedback_mode:
            # ✅ NUEVO: Eliminar palabra interactivamente
            if autocorrector.sentence_words:
                print(f"\n🗑️ Activando eliminación de palabras")
                import threading
                deletion_thread = threading.Thread(target=handle_word_deletion)
                deletion_thread.daemon = True
                deletion_thread.start()
            else:
                print("❌ No hay palabras para eliminar")
        elif key == ord("f") and not feedback_mode:
            # Feedback avanzado
            if autocorrector.sentence_words:
                feedback_mode = True
                print(f"\n🔄 Activando feedback para frase actual")
                import threading
                feedback_thread = threading.Thread(target=handle_feedback_input)
                feedback_thread.daemon = True
                feedback_thread.start()
            else:
                print("❌ No hay palabras para dar feedback")
        elif key == ord("c") and not feedback_mode:
            # ✅ NUEVO: Confirmar calidad de frase
            if autocorrector.sentence_feedback_requested:
                print(f"\n📝 Activando confirmación de calidad")
                import threading
                confirmation_thread = threading.Thread(target=handle_sentence_confirmation)
                confirmation_thread.daemon = True
                confirmation_thread.start()
            else:
                print("❌ No hay frase pendiente de confirmación")
        elif key == ord(" "):
            if autocorrector.word_buffer and not feedback_mode:
                corrected_word = autocorrector.finish_word()
                if corrected_word and corrected_word.strip():
                    if sentence:
                        sentence += " " + corrected_word
                    else:
                        sentence = corrected_word
                    print(f"🔧 Palabra forzada: {corrected_word}")
                word_finalized = True
                letra_actual = ""

    cap.release()
    cv2.destroyAllWindows()
    
    # ✅ MEJORADO: Mostrar reporte de salud al salir
    sentence_stats = autocorrector.get_successful_sentences_stats()
    health_report = autocorrector.get_correction_health_report()
    
    if sentence_stats.get("total", 0) > 0:
        print(f"\n📊 RESUMEN DE SESIÓN:")
        print(f"   💾 Frases exitosas guardadas: {sentence_stats['total']}")
        print(f"   📝 Promedio de palabras: {sentence_stats.get('avg_words_per_sentence', 0)}")
        print(f"   🔧 Promedio de correcciones: {sentence_stats.get('avg_corrections_per_sentence', 0)}")
        print(f"   ⭐ Distribución de calidad: {sentence_stats.get('quality_distribution', {})}")
        
        bert_suggestions = autocorrector.get_bert_training_suggestions()
        if bert_suggestions.get("training_examples", 0) > 0:
            print(f"\n🤖 SUGERENCIAS PARA BERT:")
            print(f"   📚 Ejemplos de entrenamiento: {bert_suggestions['training_examples']}")
            print(f"   ✅ Frases de alta calidad: {bert_suggestions['high_quality_sentences']}")
            
            # ✅ MEJORADO: Mostrar análisis gramatical solo si está disponible
            if "grammatical_analysis" in bert_suggestions:
                grammar = bert_suggestions["grammatical_analysis"]
                if grammar.get("analysis_enabled", False):
                    print(f"   📝 Distribución POS: {grammar['pos_distribution']}")
                    print(f"   🔧 Errores más comunes: {len(grammar['most_common_mistakes'])}")
                else:
                    print(f"   ⚠️ Análisis gramatical deshabilitado (spaCy no disponible)")
        
        # ✅ NUEVO: Mostrar salud del sistema
        print(f"\n🏥 SALUD DEL SISTEMA:")
        print(f"   ✅ Tasa de éxito: {health_report['feedback_stats']['success_rate']}%")
        print(f"   ⚠️ Correcciones blacklisted: {health_report['blacklisted_corrections']}")
        print(f"   🔍 Análisis gramatical: {'Habilitado' if autocorrector.pos_analysis_enabled else 'Deshabilitado'}")

if __name__ == "__main__":
    main()