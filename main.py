import cv2
import mediapipe as mp
import joblib
import numpy as np
import time
import threading
import sys
import os
from engine_bridge.hand_tracker import create_hand_landmarker
from engine_bridge.autocorrector.autocorrector_core import AutoCorrector
from utils.hand_landmarks_visualizer import draw_landmarks, draw_connections
from utils.hand_tracking_config import CAMERA_WIDTH, CAMERA_HEIGHT
from utils.draw_unicode import draw_unicode_text
from collections import deque
from api.services.translation_service import translate_text, LANG_MAP
from engine_bridge.text_to_speech import bridge_tts

if os.name == 'nt':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
        os.system('chcp 65001 > nul')
    except:
        pass

MODEL_MODE = "rf"
AUTO_TRANSLATE_TO = None

MODEL_PATH = 'models/forest_model_u.pkl'
svm_model = joblib.load(MODEL_PATH)
autocorrector = AutoCorrector()

lstm_model = None
lstm_buffer = None
LABEL_MAP_LSTM = {0: 'j', 1: 'll', 2: 'rr', 3: 'z', 4: 'ny'}

if MODEL_MODE in ("lstm", "both"):
    try:
        import tensorflow as tf
        LSTM_PATH = 'models/lstm_model.h5'
        SEQUENCE_LENGTH = 30
        FEATURES_PER_FRAME = 63
        lstm_model = tf.keras.models.load_model(LSTM_PATH)
        lstm_buffer = deque(maxlen=SEQUENCE_LENGTH)
        print("✅ Modelo LSTM cargado correctamente")
    except ImportError:
        print("⚠️ TensorFlow no disponible. Usando solo Random Forest.")
        MODEL_MODE = "rf"
    except Exception as e:
        print(f"⚠️ Error cargando modelo LSTM: {e}. Usando solo Random Forest.")
        MODEL_MODE = "rf"

phrase_active = False
last_prediction = None
last_time = 0
last_letter_time = 0
letra_actual = ""
completed_sentence = ""
sentence_completed = False
word_finalized = False
translated_sentence = ""
translated_lang = ""

COOLDOWN_TIME = 1.0
PAUSE_THRESHOLD = 2.0
PHRASE_TIMEOUT = 5.0

TTS_ENABLED = True
TTS_AUTO_PLAY = True

def extract_features(landmarks):
    return np.array([[lm.x, lm.y, lm.z] for lm in landmarks]).flatten().reshape(1, -1)

def draw_interface(frame):
    global translated_sentence, translated_lang, completed_sentence, sentence_completed
    frame_height, frame_width = frame.shape[:2]
    raw_word = ''.join(autocorrector.word_buffer)
    corrected_word = autocorrector.get_current_word_corrected()
    if sentence_completed and completed_sentence:
        sentence_text = completed_sentence
    else:
        sentence_text = autocorrector.get_sentence_string()
    words = autocorrector.get_sentence_words()
    stats = autocorrector.get_learning_stats()
    sentence_stats = autocorrector.get_successful_sentences_stats()

    panel_height = 420
    cv2.rectangle(frame, (10, 10), (frame_width - 10, panel_height), (250, 250, 250), -1)
    cv2.rectangle(frame, (10, 10), (frame_width - 10, panel_height), (80, 80, 80), 3)

    frame = draw_unicode_text(frame, " BRIDGE - Sistema de Traducción LSP", (20, 35), font_size=28, color=(50, 50, 50))

    frame = draw_unicode_text(frame, "- Detección:", (20, 75), font_size=20, color=(80, 80, 80))
    frame = draw_unicode_text(frame, f"Detectando: {raw_word if raw_word else ''}", (40, 100), font_size=22, color=(120, 120, 120))
    frame = draw_unicode_text(frame, f"Corrigiendo: {corrected_word if corrected_word else ''}", (40, 125), font_size=22, color=(0, 140, 0))

    if sentence_completed and completed_sentence:
        frame = draw_unicode_text(frame, "- Frase Completada:", (20, 165), font_size=20, color=(0, 150, 0))
        frase_display = sentence_text
        frame = draw_unicode_text(frame, frase_display, (40, 190), font_size=26, color=(0, 100, 0))
    else:
        frame = draw_unicode_text(frame, "- Frase Actual:", (20, 165), font_size=20, color=(80, 80, 80))
        frase_display = sentence_text if sentence_text else ""
        frame = draw_unicode_text(frame, frase_display, (40, 190), font_size=26, color=(0, 50, 200))

    if AUTO_TRANSLATE_TO is not None or translated_sentence:
        frame = draw_unicode_text(frame, "- Traducción:", (20, 235), font_size=20, color=(80, 80, 80))

        if translated_sentence and AUTO_TRANSLATE_TO:
            lang_names = {
                "ar": "العربية", "bg": "Български", "cs": "Čeština", "da": "Dansk",
                "de": "Deutsch", "el": "Ελληνικά", "en": "English", "et": "Eesti",
                "fi": "Suomi", "fr": "Français", "he": "עברית", "hu": "Magyar",
                "id": "Bahasa Indonesia", "it": "Italiano", "ja": "日本語", "ko": "한국어",
                "lt": "Lietuvių", "lv": "Latviešu", "nb": "Norsk", "nl": "Nederlands",
                "pl": "Polski", "pt": "Português", "ro": "Română", "ru": "Русский",
                "sk": "Slovenčina", "sl": "Slovenščina", "sv": "Svenska", "th": "ไทย",
                "tr": "Türkçe", "uk": "Українська", "vi": "Tiếng Việt",
                "zh": "中文", "zh-hans": "中文简体", "zh-hant": "中文繁體"
            }
            lang_display = lang_names.get(translated_lang, translated_lang.upper())
            translation_text = f"({lang_display}): {translated_sentence}"
            frame = draw_unicode_text(frame, translation_text, (40, 260), font_size=24, color=(0, 100, 255))
        elif translated_sentence:
            lang_names = {
                "ar": "العربية", "bg": "Български", "cs": "Čeština", "da": "Dansk",
                "de": "Deutsch", "el": "Ελληνικά", "en": "English", "et": "Eesti",
                "fi": "Suomi", "fr": "Français", "he": "עברית", "hu": "Magyar",
                "id": "Bahasa Indonesia", "it": "Italiano", "ja": "日本語", "ko": "한국어",
                "lt": "Lietuvių", "lv": "Latviešu", "nb": "Norsk", "nl": "Nederlands",
                "pl": "Polski", "pt": "Português", "ro": "Română", "ru": "Русский",
                "sk": "Slovenčina", "sl": "Slovenščina", "sv": "Svenska", "th": "ไทย",
                "tr": "Türkçe", "uk": "Українська", "vi": "Tiếng Việt",
                "zh": "中文", "zh-hans": "中文简体", "zh-hant": "中文繁體"
            }
            lang_display = lang_names.get(translated_lang, translated_lang.upper())
            translation_text = f"({lang_display}): {translated_sentence}"
            frame = draw_unicode_text(frame, translation_text, (40, 260), font_size=24, color=(0, 100, 255))
        elif AUTO_TRANSLATE_TO:
            lang_names = {
                "ar": "العربية", "bg": "Български", "cs": "Čeština", "da": "Dansk",
                "de": "Deutsch", "el": "Ελληνικά", "en": "English", "et": "Eesti",
                "fi": "Suomi", "fr": "Français", "he": "عברית", "hu": "Magyar",
                "id": "Bahasa Indonesia", "it": "Italiano", "ja": "日本語", "ko": "한국어",
                "lt": "Lietuvių", "lv": "Latviešu", "nb": "Norsk", "nl": "Nederlands",
                "pl": "Polski", "pt": "Português", "ro": "Română", "ru": "Русский",
                "sk": "Slovenčina", "sl": "Slovenščina", "sv": "Svenska", "th": "ไทย",
                "tr": "Türkçe", "uk": "Українська", "vi": "Tiếng Việt",
                "zh": "中文", "zh-hans": "中文简体", "zh-hant": "中文繁體"
            }
            lang_display = lang_names.get(AUTO_TRANSLATE_TO, AUTO_TRANSLATE_TO.upper())
            translation_text = f"({lang_display}): Esperando frase..."
            frame = draw_unicode_text(frame, translation_text, (40, 260), font_size=22, color=(150, 150, 150))
        else:
            frame = draw_unicode_text(frame, "Desactivada", (40, 260), font_size=22, color=(200, 100, 100))

    controls_y = panel_height + 20
    cv2.putText(frame, "DETECCIÓN AUTOMÁTICA LSP", (20, controls_y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    model_status = f"Modelo: {MODEL_MODE.upper()}"
    translate_status = f"Auto-traduccion: {AUTO_TRANSLATE_TO.upper() if AUTO_TRANSLATE_TO else 'OFF'}"
    stats_text = f"{model_status} | {translate_status}"
    cv2.putText(frame, stats_text, (20, controls_y + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    if letra_actual:
        letter_size = 120
        letter_x = frame_width - letter_size - 20
        letter_y = frame_height - letter_size - 20

        cv2.rectangle(frame, (letter_x + 5, letter_y + 5), (letter_x + letter_size + 5, letter_y + letter_size + 5), (100, 100, 100), -1)
        cv2.rectangle(frame, (letter_x, letter_y), (letter_x + letter_size, letter_y + letter_size), (255, 255, 255), -1)
        cv2.rectangle(frame, (letter_x, letter_y), (letter_x + letter_size, letter_y + letter_size), (0, 0, 0), 3)

        cv2.putText(frame, letra_actual, (letter_x + 25, letter_y + 80), cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 0, 0), 4)

    return frame

def clear_completed_sentence():
    global completed_sentence, sentence_completed, translated_sentence, translated_lang
    completed_sentence = ""
    sentence_completed = False
    translated_sentence = ""
    translated_lang = ""
    print("🔄 Frase anterior limpiada - empezando nueva frase")

def complete_sentence():
    global completed_sentence, sentence_completed, phrase_active, translated_sentence, translated_lang
    final_sentence = autocorrector.end_sentence()
    if final_sentence.strip():
        completed_sentence = final_sentence
        sentence_completed = True
        phrase_active = False
        print(f"✅ Frase completada: {final_sentence}")

        if TTS_ENABLED and TTS_AUTO_PLAY:
            if AUTO_TRANSLATE_TO and translated_sentence:
                bridge_tts.speak_sentence_completion(translated_sentence, AUTO_TRANSLATE_TO)
                print(f"🔊 Reproduciendo traducción en {AUTO_TRANSLATE_TO}")
            else:
                bridge_tts.speak_sentence_completion(final_sentence, 'es')
                print(f"🔊 Reproduciendo frase en español")

        if AUTO_TRANSLATE_TO:
            translated = translate_text(final_sentence, AUTO_TRANSLATE_TO)
            if translated:
                translated_sentence = translated
                translated_lang = AUTO_TRANSLATE_TO
                lang_names = {
                    "ar": "العربية", "bg": "Български", "cs": "Čeština", "da": "Dansk",
                    "de": "Deutsch", "el": "Ελληνικά", "en": "English", "et": "Eesti",
                    "fi": "Suomi", "fr": "Français", "he": "עברית", "hu": "Magyar",
                    "id": "Bahasa Indonesia", "it": "Italiano", "ja": "日本語", "ko": "한국어",
                    "lt": "Lietuvių", "lv": "Latviešu", "nb": "Norsk", "nl": "Nederlands",
                    "pl": "Polski", "pt": "Português", "ro": "Română", "ru": "Русский",
                    "sk": "Slovenčina", "sl": "Slovenščina", "sv": "Svenska", "th": "ไทy",
                    "tr": "Türkçe", "uk": "Українська", "vi": "Tiếng Việt",
                    "zh": "中文", "zh-hans": "中文简体", "zh-hant": "中文繁體"
                }
                print(f"✅ Traducción automática ({lang_names.get(AUTO_TRANSLATE_TO, AUTO_TRANSLATE_TO)}): {translated}")

                if TTS_ENABLED and TTS_AUTO_PLAY:
                    bridge_tts.speak_sentence_completion(translated, AUTO_TRANSLATE_TO)
                    print(f"🔊 Reproduciendo traducción en {AUTO_TRANSLATE_TO}")

    return final_sentence

def main():
    global last_prediction, last_time, last_letter_time, letra_actual
    global word_finalized, phrase_active, sentence_completed

    print("🎥 Intentando acceder a la cámara...")
    
    # Intentar diferentes índices de cámara
    camera_found = False
    cap = None
    
    for camera_index in range(3):  # Probar cámaras 0, 1, 2
        print(f"   Probando cámara {camera_index}...")
        cap = cv2.VideoCapture(camera_index)
        if cap.isOpened():
            # Configurar propiedades antes de probar lectura
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Test if we can actually read from it
            for attempt in range(3):  # Intentar leer 3 veces
                ret, test_frame = cap.read()
                if ret and test_frame is not None and test_frame.size > 0:
                    print(f"✅ Cámara {camera_index} disponible")
                    camera_found = True
                    break
            
            if camera_found:
                break
            else:
                print(f"❌ Cámara {camera_index} no puede leer frames válidos")
                cap.release()
        else:
            print(f"❌ Cámara {camera_index} no disponible")
            if cap:
                cap.release()
    
    if not camera_found:
        print("❌ Error: No se encontró ninguna cámara disponible")
        print("💡 Posibles soluciones:")
        print("   - Cierra Flutter app y otras aplicaciones que usen la cámara")
        print("   - Verifica que la cámara esté conectada")
        print("   - Desconecta y reconecta la cámara")
        return
    
    # Ya configurado en el bucle de detección, no configurar de nuevo
    # cap.set(3, CAMERA_WIDTH) - Ya configurado arriba
    # cap.set(4, CAMERA_HEIGHT) - Ya configurado arriba
    
    # Configurar buffer para evitar lag (ya hecho en detección)
    print("✅ Cámara inicializada correctamente")
    print("🤖 Cargando detector de manos...")
    
    hand_landmarker = create_hand_landmarker(running_mode="VIDEO")
    
    print("🖼️ Creando ventana de visualización...")
    cv2.namedWindow("Sign Language Recognition - Auto Corrector", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Sign Language Recognition - Auto Corrector", 1000, 700)

    print(f"🚀 Sistema iniciado (Modo: {MODEL_MODE.upper()})")
    print("📹 Ventana de cámara debe aparecer ahora...")
    print("📺 Si no ves la ventana, presiona ALT+TAB")
    print("⌨️ Presiona Q para salir")
    
    if AUTO_TRANSLATE_TO:
        lang_names = {
            "ar": "العربية", "bg": "Български", "cs": "Čeština", "da": "Dansk",
            "de": "Deutsch", "el": "Ελληνικά", "en": "English", "et": "Eesti",
            "fi": "Suomi", "fr": "Français", "he": "עברית", "hu": "Magyar",
            "id": "Bahasa Indonesia", "it": "Italiano", "ja": "日本語", "ko": "한국어",
            "lt": "Lietuvių", "lv": "Latviešu", "nb": "Norsk", "nl": "Nederlands",
            "pl": "Polski", "pt": "Português", "ro": "Română", "ru": "Русский",
            "sk": "Slovenčina", "sl": "Slovenščina", "sv": "Svenska", "th": "ไทย",
            "tr": "Türkçe", "uk": "Українська", "vi": "Tiếng Việt",
            "zh": "中文", "zh-hans": "中文简体", "zh-hant": "中文繁體"
        }
        print(f"🌐 Traducción automática activada a: {lang_names.get(AUTO_TRANSLATE_TO, AUTO_TRANSLATE_TO.upper())}")
        print("📡 Usando DeepL directamente")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Error: No se puede leer de la cámara")
            break
        
        # Verificar que el frame sea válido
        if frame is None or frame.size == 0:
            print("⚠️ Frame inválido, intentando siguiente...")
            continue

        try:
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            timestamp = int(cap.get(cv2.CAP_PROP_POS_MSEC))
            results = hand_landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)
        except Exception as e:
            print(f"⚠️ Error procesando frame: {e}")
            continue

        current_time = time.time()
        detected = False

        if MODEL_MODE in ("lstm", "both") and lstm_model and lstm_buffer and results.hand_world_landmarks:
            for landmarks in results.hand_world_landmarks:
                frame_features = [coord for point in landmarks for coord in (point.x, point.y, point.z)]
                lstm_buffer.append(frame_features)

        if (MODEL_MODE in ("lstm", "both") and lstm_model and lstm_buffer and
            len(lstm_buffer) == lstm_buffer.maxlen):
            seq = np.array(lstm_buffer)
            pred = lstm_model.predict(np.expand_dims(seq, axis=0), verbose=0)
            pred_label = np.argmax(pred)
            prob = float(pred[0][pred_label])

            if prob > 0.85:
                letra_lstm = LABEL_MAP_LSTM.get(pred_label, None)
                if letra_lstm and letra_lstm != last_prediction and (current_time - last_time) > COOLDOWN_TIME:
                    if sentence_completed:
                        clear_completed_sentence()
                    letra_actual = letra_lstm.upper()
                    autocorrector.add_letter(letra_actual.lower())
                    last_prediction = letra_lstm
                    last_time = current_time
                    last_letter_time = current_time
                    phrase_active = True
                    word_finalized = False
                    detected = True
                    prediction_type = "lstm"
                    print(f"🔁 LSTM Letra: {letra_actual}")

        if MODEL_MODE in ("rf", "both") and results.hand_landmarks and not detected:
            for idx, lm in enumerate(results.hand_landmarks):
                draw_landmarks(frame, lm, frame.shape[1], frame.shape[0])
                draw_connections(frame, lm, frame.shape[1], frame.shape[0])
                features = extract_features(results.hand_world_landmarks[idx])
                prediction = svm_model.predict(features)[0]

                if prediction != last_prediction and (current_time - last_time) > COOLDOWN_TIME:
                    if sentence_completed:
                        clear_completed_sentence()
                    letra_actual = prediction.upper()
                    autocorrector.add_letter(letra_actual.lower())
                    last_prediction = prediction
                    last_time = current_time
                    last_letter_time = current_time
                    phrase_active = True
                    word_finalized = False
                    detected = True
                    print(f"✅ Letra: {letra_actual}")

        if (phrase_active and autocorrector.sentence_words and
            (current_time - last_letter_time > PHRASE_TIMEOUT)):
            print("⏰ No se detectaron señas por 5 segundos. Fin de frase automático.")
            complete_sentence()

        if (not detected and autocorrector.word_buffer and
            current_time - last_letter_time > PAUSE_THRESHOLD and not word_finalized):
            word = autocorrector.finish_word()
            if word.strip():
                print(f"📝 Palabra: {word}")
            word_finalized = True
            letra_actual = ""

        frame = draw_interface(frame)
        
        try:
            cv2.imshow("Sign Language Recognition - Auto Corrector", frame)
            # Asegurar que la ventana sea visible
            cv2.moveWindow("Sign Language Recognition - Auto Corrector", 100, 100)
        except Exception as e:
            print(f"⚠️ Error mostrando frame: {e}")
            continue

        key = cv2.waitKey(5) & 0xFF
        if key == ord("q"):
            if TTS_ENABLED:
                bridge_tts.stop_current_audio()
            break

    print("🔄 Cerrando sistema...")
    cap.release()
    cv2.destroyAllWindows()
    print("✅ Cámara liberada correctamente")

    if TTS_ENABLED:
        bridge_tts.stop_current_audio()

    stats = autocorrector.get_successful_sentences_stats()
    health = autocorrector.get_correction_health_report()
    print(f"\n📊 Frases exitosas: {stats.get('total', 0)} | Correcciones: {health['total_corrections']} | Tasa éxito: {health['feedback_stats']['success_rate']}%")

if __name__ == "__main__":
    print("🚀 Iniciando Bridge Main.py - Laboratorio de Pruebas")
    print("📚 Para usar la API, ejecuta: python -m uvicorn api.api_main:app --reload --host 0.0.0.0 --port 8000")
    print("🔬 Este es el entorno de laboratorio para pruebas locales")
    print("")
    main()