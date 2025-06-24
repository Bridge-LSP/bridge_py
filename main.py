import cv2
import mediapipe as mp
from engine_bridge.hand_tracker import create_hand_landmarker
from utils.hand_landmarks_visualizer import draw_landmarks, draw_connections, draw_handedness_label
from utils.hand_tracking_config import CAMERA_WIDTH, CAMERA_HEIGHT
from utils.bridge_utils import save_landmark_to_json
from engine_bridge.bert_autocorrector import AutoCorrector
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
    
    cv2.rectangle(frame, (10, 10), (frame_width - 10, 250), (240, 240, 240), -1)
    cv2.rectangle(frame, (10, 10), (frame_width - 10, 250), (100, 100, 100), 2)
    
    raw_word = ''.join(autocorrector.word_buffer)
    cv2.putText(frame, f"Detectando: {raw_word}", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2)
    
    corrected_word = autocorrector.get_current_word_corrected()
    cv2.putText(frame, f"Corrigiendo: {corrected_word}", (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 150, 0), 2)
    
    cv2.putText(frame, f"Frase: {sentence}", (20, 110),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 200), 2)
    
    if feedback_mode:
        cv2.rectangle(frame, (10, 150), (frame_width - 10, 200), (255, 255, 0), -1)
        cv2.putText(frame, f"FEEDBACK: ¿Era '{current_word_for_feedback}' correcto?", (20, 175),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        cv2.putText(frame, "Escribe la palabra correcta y presiona ENTER", (20, 195),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    
    instruction_y = 220 if feedback_mode else 140
    cv2.putText(frame, "Pausa 3s = palabra | 'r' = nueva frase | 'f' = feedback | 'q' = salir", 
                (20, instruction_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 80, 80), 1)
    
    stats = autocorrector.get_learning_stats()
    cv2.putText(frame, f"Aprendidas: {stats['total_corrections']} correcciones", 
                (20, instruction_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 100, 0), 1)
    
    if letra_actual:
        text_y = frame_height - 100
        cv2.rectangle(frame, (10, text_y - 40), (100, text_y + 10), (255, 255, 255), -1)
        cv2.rectangle(frame, (10, text_y - 40), (100, text_y + 10), (0, 0, 0), 2)
        cv2.putText(frame, letra_actual, (25, text_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)

def handle_feedback_input():
    global feedback_mode, current_word_for_feedback
    
    print(f"\n🔄 MODO RETROALIMENTACIÓN")
    print(f"Palabra detectada: '{current_word_for_feedback}'")
    print("¿Es correcta esta palabra? (y/n) o escribe la palabra correcta:")
    
    user_input = input("Tu respuesta: ").strip().lower()
    
    if user_input == 'y' or user_input == 'yes' or user_input == 'si':
        print("✅ Palabra confirmada como correcta")
    elif user_input == 'n' or user_input == 'no':
        correct_word = input("Escribe la palabra correcta: ").strip()
        if correct_word:
            if autocorrector.provide_feedback(correct_word):
                print(f"🧠 ¡Aprendido! '{autocorrector.last_raw_word}' -> '{correct_word}'")
            else:
                print("⚠️ No se pudo procesar la retroalimentación")
    else:
        if autocorrector.provide_feedback(user_input):
            print(f"🧠 ¡Aprendido! '{autocorrector.last_raw_word}' -> '{user_input}'")
        else:
            print("⚠️ No se pudo procesar la retroalimentación")
    
    feedback_mode = False
    current_word_for_feedback = ""

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

        draw_interface(frame)
        cv2.imshow("Sign Language Recognition - Auto Corrector", frame)

        key = cv2.waitKey(5) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("r"):
            autocorrector.clear_buffer()
            sentence = ""
            letra_actual = ""
            last_prediction = None
            word_finalized = False
            feedback_mode = False
            print("🔄 Nueva frase iniciada")
        elif key == ord("f") and not feedback_mode:
            if autocorrector.last_corrected_word:
                feedback_mode = True
                current_word_for_feedback = autocorrector.last_corrected_word
                print(f"\n🔄 Activando retroalimentación para: '{current_word_for_feedback}'")
                import threading
                feedback_thread = threading.Thread(target=handle_feedback_input)
                feedback_thread.daemon = True
                feedback_thread.start()
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

if __name__ == "__main__":
    main()