import cv2
import mediapipe as mp
import joblib
import numpy as np
import time
import threading
from engine_bridge.hand_tracker import create_hand_landmarker
from engine_bridge.autocorrector.autocorrector_core import AutoCorrector
from utils.hand_landmarks_visualizer import draw_landmarks, draw_connections
from utils.hand_tracking_config import CAMERA_WIDTH, CAMERA_HEIGHT
from utils.bridge_utils import save_landmark_to_json
from tensorflow.keras.models import load_model
from collections import deque

# === MODELO Y OBJETOS GLOBALES ===
MODEL_MODE = "rf"  # Opciones: "lstm", "rf", "both"

MODEL_PATH = 'models/forest_model_u.pkl'
svm_model = joblib.load(MODEL_PATH)
autocorrector = AutoCorrector()

LSTM_PATH = 'models/lstm_model.h5'
SEQUENCE_LENGTH = 30
FEATURES_PER_FRAME = 63
LABEL_MAP_LSTM = {0: 'j', 1: 'll', 2: 'rr', 3: 'z', 4: 'ny'} 
lstm_model = load_model(LSTM_PATH)
lstm_buffer = deque(maxlen=SEQUENCE_LENGTH)

# === ESTADOS Y VARIABLES DE CONTROL ===
last_prediction = None
last_time = 0
last_letter_time = 0
letra_actual = ""
sentence = ""
word_finalized = False
feedback_mode = False

# === CONSTANTES ===
COOLDOWN_TIME = 1.0
PAUSE_THRESHOLD = 3.0

# === FUNCIONES AUXILIARES ===

def extract_features(landmarks):
    return np.array([[lm.x, lm.y, lm.z] for lm in landmarks]).flatten().reshape(1, -1)

def draw_interface(frame):
    frame_height, frame_width = frame.shape[:2]
    raw_word = ''.join(autocorrector.word_buffer)
    corrected_word = autocorrector.get_current_word_corrected()
    sentence_text = autocorrector.get_sentence_string()
    words = autocorrector.get_sentence_words()
    stats = autocorrector.get_learning_stats()
    sentence_stats = autocorrector.get_successful_sentences_stats()

    # Panel superior
    cv2.rectangle(frame, (10, 10), (frame_width - 10, 300), (240, 240, 240), -1)
    cv2.rectangle(frame, (10, 10), (frame_width - 10, 300), (100, 100, 100), 2)
    cv2.putText(frame, f"Detectando: {raw_word}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2)
    cv2.putText(frame, f"Corrigiendo: {corrected_word}", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 150, 0), 2)
    cv2.putText(frame, f"Frase: {sentence_text}", (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 200), 2)

    # Palabras enumeradas
    if words:
        words_text = " | ".join([f"{i+1}.{word}" for i, word in words])
        cv2.putText(frame, f"Palabras: {words_text}", (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 0, 150), 2)

    # Feedback
    if feedback_mode:
        cv2.rectangle(frame, (10, 170), (frame_width - 10, 220), (255, 255, 0), -1)
        cv2.putText(frame, "FEEDBACK: Escribe número de palabra + corrección", (20, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        cv2.putText(frame, "Ej: '2 hola' para corregir palabra 2 a 'hola'", (20, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)

    cv2.putText(frame, "3s=palabra | 'f'=feedback | 'e'=fin frase | 'd'=eliminar | 'r'=reset", (20, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (80, 80, 80), 1)
    cv2.putText(frame, f"Aprendidas: {stats['total_corrections']} correcciones | {sentence_stats.get('total', 0)} frases", (20, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 100, 0), 1)

    # Letra en grande
    if letra_actual:
        text_y = frame_height - 100
        cv2.rectangle(frame, (10, text_y - 40), (100, text_y + 10), (255, 255, 255), -1)
        cv2.rectangle(frame, (10, text_y - 40), (100, text_y + 10), (0, 0, 0), 2)
        cv2.putText(frame, letra_actual, (25, text_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)

# === FUNCIONES INTERACTIVAS ===

def handle_feedback_input():
    global feedback_mode
    print("\n🔄 MODO FEEDBACK AVANZADO")
    words = autocorrector.get_sentence_words()

    if not words:
        print("❌ No hay palabras para corregir")
        feedback_mode = False
        return

    for i, word in words:
        print(f"  {i+1}. {word}")
    print("• Número + palabra: '2 hola' | 'd2' para eliminar | 'c' para cancelar")
    user_input = input("Tu comando: ").strip()

    if user_input.lower() == 'c':
        print("❌ Feedback cancelado")
    elif user_input.lower().startswith('d'):
        try:
            idx = int(user_input[1:]) - 1
            if autocorrector.remove_word(idx):
                print("✅ Palabra eliminada")
            else:
                print("❌ Índice inválido")
        except:
            print("❌ Formato incorrecto")
    else:
        try:
            idx, correction = user_input.split(' ', 1)
            idx = int(idx) - 1
            if autocorrector.provide_feedback_for_word(idx, correction):
                print("✅ Corrección aplicada")
            else:
                print("❌ Índice inválido")
        except:
            print("❌ Formato incorrecto")
    feedback_mode = False

def handle_word_deletion():
    words = autocorrector.get_sentence_words()
    if not words:
        print("❌ No hay palabras para eliminar")
        return

    for i, word in words:
        print(f"  {i+1}. {word}")
    user_input = input("¿Qué palabra quieres eliminar? (1, 2...) o 'c': ").strip()

    if user_input.lower() == 'c':
        print("❌ Cancelado")
    else:
        try:
            idx = int(user_input) - 1
            if autocorrector.remove_word(idx):
                print("✅ Eliminado")
            else:
                print("❌ Índice inválido")
        except:
            print("❌ Formato inválido")

def handle_sentence_confirmation():
    if not autocorrector.sentence_feedback_requested:
        print("❌ No hay frase pendiente")
        return
    record = autocorrector.pending_sentence_confirmation
    print(f"Original: '{record['original_sentence']}'\nCorregida: '{record['corrected_sentence']}'\nCoherencia: {record['semantic_coherence']:.2f}\nCorrecciones: {record['correction_ratio_advanced']:.2f}")
    print("¿Calidad? (1=Perfecta, 5=Muy mala)")
    try:
        feedback = int(input("Tu evaluación (1-5): ").strip())
        if autocorrector.confirm_sentence_quality(feedback >= 3, feedback):
            print("✅ Evaluación registrada")
    except:
        print("❌ Entrada inválida")

# === BUCLE PRINCIPAL ===

def main():
    global last_prediction, last_time, last_letter_time, letra_actual, sentence, word_finalized, feedback_mode

    cap = cv2.VideoCapture(0)
    cap.set(3, CAMERA_WIDTH)
    cap.set(4, CAMERA_HEIGHT)
    hand_landmarker = create_hand_landmarker(running_mode="VIDEO")
    cv2.namedWindow("Sign Language Recognition - Auto Corrector")

    print("🚀 Sistema iniciado")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        timestamp = int(cap.get(cv2.CAP_PROP_POS_MSEC))
        results = hand_landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)

        current_time = time.time()
        detected = False
        prediction_type = None

        # === Recolección para LSTM ===
        if results.hand_world_landmarks:
            for landmarks in results.hand_world_landmarks:
                frame_features = [coord for point in landmarks for coord in (point.x, point.y, point.z)]
                lstm_buffer.append(frame_features)

        # === PREDICCIÓN CON LSTM ===
        if MODEL_MODE in ("lstm", "both") and len(lstm_buffer) == SEQUENCE_LENGTH and not feedback_mode:
            seq = np.array(lstm_buffer)
            pred = lstm_model.predict(np.expand_dims(seq, axis=0), verbose=0)
            pred_label = np.argmax(pred)
            prob = float(pred[0][pred_label])

            if prob > 0.85:
                letra_lstm = LABEL_MAP_LSTM.get(pred_label, None)
                if letra_lstm and letra_lstm != last_prediction and (current_time - last_time) > COOLDOWN_TIME:
                    letra_actual = letra_lstm.upper()
                    autocorrector.add_letter(letra_actual.lower())
                    last_prediction = letra_lstm
                    last_time = current_time
                    last_letter_time = current_time
                    word_finalized = False
                    detected = True
                    prediction_type = "lstm"
                    print(f"🔁 LSTM Letra: {letra_actual}")

        # === PREDICCIÓN CON RANDOM FOREST ===
        if MODEL_MODE in ("rf", "both") and results.hand_landmarks and not feedback_mode and not detected:
            for idx, lm in enumerate(results.hand_landmarks):
                draw_landmarks(frame, lm, frame.shape[1], frame.shape[0])
                draw_connections(frame, lm, frame.shape[1], frame.shape[0])
                features = extract_features(results.hand_world_landmarks[idx])
                prediction = svm_model.predict(features)[0]

                if prediction != last_prediction and (current_time - last_time) > COOLDOWN_TIME:
                    letra_actual = prediction.upper()
                    autocorrector.add_letter(letra_actual.lower())
                    last_prediction = prediction
                    last_time = current_time
                    last_letter_time = current_time
                    word_finalized = False
                    detected = True
                    print(f"✅ Letra: {letra_actual}")

        if (not detected and autocorrector.word_buffer and 
            current_time - last_letter_time > PAUSE_THRESHOLD and not word_finalized and not feedback_mode):
            word = autocorrector.finish_word()
            if word.strip():
                sentence += " " + word if sentence else word
                print(f"📝 Palabra: {word} | Frase: {sentence}")
            word_finalized = True
            letra_actual = ""

        sentence = autocorrector.get_sentence_string()
        draw_interface(frame)
        cv2.imshow("Sign Language Recognition - Auto Corrector", frame)

        key = cv2.waitKey(5) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("r"):
            autocorrector.clear_buffer()
            autocorrector.end_sentence()
            sentence, letra_actual, last_prediction = "", "", None
            word_finalized, feedback_mode = False, False
            print("🔄 Sistema reiniciado")
        elif key == ord("e"):
            if autocorrector.sentence_words:
                print(f"✅ Final: {autocorrector.end_sentence()}")
                sentence, letra_actual, word_finalized = "", "", False
            else:
                print("❌ Nada que finalizar")
        elif key == ord("d") and not feedback_mode:
            threading.Thread(target=handle_word_deletion, daemon=True).start()
        elif key == ord("f") and not feedback_mode:
            feedback_mode = True
            threading.Thread(target=handle_feedback_input, daemon=True).start()
        elif key == ord("c") and not feedback_mode:
            threading.Thread(target=handle_sentence_confirmation, daemon=True).start()
        elif key == ord(" "):
            if autocorrector.word_buffer and not feedback_mode:
                word = autocorrector.finish_word()
                sentence += " " + word if sentence else word
                print(f"📝 Palabra forzada: {word}")
                word_finalized, letra_actual = True, ""

    cap.release()
    cv2.destroyAllWindows()

    # Reporte al cerrar
    stats = autocorrector.get_successful_sentences_stats()
    health = autocorrector.get_correction_health_report()
    print(f"\n📊 Frases exitosas: {stats.get('total', 0)} | Correcciones: {health['total_corrections']} | Tasa éxito: {health['feedback_stats']['success_rate']}%")

if __name__ == "__main__":
    main()