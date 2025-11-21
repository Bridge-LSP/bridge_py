# 🔊 WebSocket TTS Integration Guide - Bridge LSP Backend

## 📋 Resumen Ejecutivo

El backend de Bridge LSP ahora envía **eventos de TTS automático** a través del WebSocket en tiempo real. El frontend debe:
1. Detectar cuando se completa una oración (`sentence.just_completed: true`)
2. Obtener el texto completado (`sentence.completed: "texto aquí"`)
3. Reproducir el audio usando el campo `tts.audio_base64`

---

## 🔗 Endpoint WebSocket

```
ws://localhost:8000/realtime/ws/detection/{session_id}
```

### Flujo de Conexión

1. **Inicializar sesión** (REST):
   ```http
   POST /session/init
   Content-Type: application/json
   
   {
     "preferences": {
       "tts_enabled": true,      // ✅ Debe ser true
       "tts_muted": false,        // ✅ Debe ser false
       "auto_translate": false,
       "word_pause_ms": 4000,
       "phrase_pause_ms": 8000
     }
   }
   ```

   **Respuesta:**
   ```json
   {
     "status": "success",
     "session_id": "uuid-here",
     "preferences": { ... },
     "created_at": "2025-11-21T..."
   }
   ```

2. **Conectar WebSocket:**
   ```javascript
   const ws = new WebSocket(`ws://localhost:8000/realtime/ws/detection/${sessionId}`);
   ```

3. **Enviar mensaje PLAY** (crítico):
   ```json
   {
     "type": "control",
     "action": "play"
   }
   ```

4. **Enviar frames:**
   ```json
   {
     "type": "frame",
     "frameBase64": "base64-encoded-jpeg-here"
   }
   ```

---

## 📦 Estructura de Mensajes del Backend

### Estado Completo (State Update)

El backend envía estados cada vez que procesa un frame:

```json
{
  "type": "state_update",
  "session_id": "uuid",
  "timestamp": 1763706662.123,
  
  "detection": {
    "letter": "h",              // Letra detectada actual
    "confidence": 0.95,          // Confianza del modelo
    "model": "rf"                // Modelo usado (rf/lstm)
  },
  
  "word": {
    "raw_buffer": "hola",        // Buffer de letras sin corregir
    "corrected": "hola",         // Palabra corregida por BERT
    "just_finished": false       // ⚡ TRUE cuando se completa palabra
  },
  
  "sentence": {
    "current": "hola mundo",     // Oración actual (en construcción)
    "completed": "hola mundo",   // ✅ ORACIÓN COMPLETADA (string)
    "just_completed": false      // ⚡ TRUE cuando se completa oración
  },
  
  "translation": {
    "enabled": false,
    "target_language": "en",
    "translated_sentence": "hello world",
    "just_translated": false     // ⚡ TRUE cuando se traduce
  },
  
  "timers": {
    "time_since_last_letter": 1.5,
    "word_timer_active": true,
    "phrase_timer_active": true
  },
  
  "tts": {
    "enabled": true,             // ✅ TTS habilitado globalmente
    "muted": false,              // ✅ TTS no silenciado
    "audio_available": true,     // ✅ Hay audio disponible
    "audio_base64": "UklGR...",  // ✅ Audio en base64 (MP3)
    "audio_mime_type": "audio/mpeg",
    "just_generated": true       // ⚡ TRUE cuando se genera nuevo audio
  },
  
  "processing_time_ms": 45.2
}
```

---

## 🎯 Implementación Frontend - TTS Automático

### 1. Detección de Oración Completada

```dart
void _handleWebSocketMessage(Map<String, dynamic> message) {
  if (message['type'] != 'state_update') return;
  
  // 🎯 CRÍTICO: Detectar cuando se completa una oración
  final sentence = message['sentence'] as Map<String, dynamic>?;
  final justCompleted = sentence?['just_completed'] as bool? ?? false;
  
  if (justCompleted) {
    final completedText = sentence?['completed'] as String? ?? '';
    
    if (completedText.isNotEmpty) {
      print('✅ Sentence completed: $completedText');
      
      // Opción 1: Usar audio del backend (recomendado)
      _playTTSFromBackend(message);
      
      // Opción 2: Generar audio localmente
      // _playTTSLocally(completedText);
    }
  }
}
```

### 2. Reproducir Audio del Backend (Recomendado)

```dart
Future<void> _playTTSFromBackend(Map<String, dynamic> message) async {
  final tts = message['tts'] as Map<String, dynamic>?;
  
  if (tts == null) return;
  
  final audioAvailable = tts['audio_available'] as bool? ?? false;
  final audioBase64 = tts['audio_base64'] as String?;
  final mimeType = tts['audio_mime_type'] as String? ?? 'audio/mpeg';
  
  if (!audioAvailable || audioBase64 == null || audioBase64.isEmpty) {
    print('⚠️  No TTS audio available from backend');
    return;
  }
  
  try {
    // Decodificar base64
    final audioBytes = base64Decode(audioBase64);
    
    // Guardar a archivo temporal
    final tempDir = await getTemporaryDirectory();
    final tempFile = File('${tempDir.path}/tts_${DateTime.now().millisecondsSinceEpoch}.mp3');
    await tempFile.writeAsBytes(audioBytes);
    
    // Reproducir con audioplayers (o tu reproductor preferido)
    final player = AudioPlayer();
    await player.play(DeviceFileSource(tempFile.path));
    
    print('🔊 TTS audio playing from backend');
    
    // Limpiar después de reproducir
    player.onPlayerComplete.listen((_) {
      tempFile.delete();
      player.dispose();
    });
    
  } catch (e) {
    print('❌ Error playing TTS audio: $e');
  }
}
```

### 3. Reproducir Audio Localmente (Alternativa)

```dart
import 'package:flutter_tts/flutter_tts.dart';

final FlutterTts _flutterTts = FlutterTts();

Future<void> _playTTSLocally(String text) async {
  try {
    await _flutterTts.setLanguage('es-ES');
    await _flutterTts.setSpeechRate(0.5);
    await _flutterTts.setVolume(1.0);
    await _flutterTts.setPitch(1.0);
    
    await _flutterTts.speak(text);
    
    print('🔊 TTS speaking locally: $text');
    
  } catch (e) {
    print('❌ Error with local TTS: $e');
  }
}
```

---

## 🔍 Debugging - Verificación de Estados

### Imprimir Todos los Eventos Relevantes

```dart
void _debugWebSocketState(Map<String, dynamic> message) {
  print('\n📨 WebSocket State Update:');
  
  // Detection
  final detection = message['detection'] as Map<String, dynamic>?;
  print('  🔤 Letter: ${detection?['letter']} (confidence: ${detection?['confidence']})');
  
  // Word
  final word = message['word'] as Map<String, dynamic>?;
  print('  📝 Word: raw="${word?['raw_buffer']}" corrected="${word?['corrected']}"');
  print('     just_finished: ${word?['just_finished']}');
  
  // Sentence
  final sentence = message['sentence'] as Map<String, dynamic>?;
  print('  📄 Sentence: current="${sentence?['current']}"');
  print('     completed: "${sentence?['completed']}"');
  print('     just_completed: ${sentence?['just_completed']} ⚡');
  
  // TTS
  final tts = message['tts'] as Map<String, dynamic>?;
  print('  🔊 TTS: enabled=${tts?['enabled']}, muted=${tts?['muted']}');
  print('     audio_available: ${tts?['audio_available']}');
  print('     just_generated: ${tts?['just_generated']} ⚡');
  
  // Translation
  final translation = message['translation'] as Map<String, dynamic>?;
  print('  🌍 Translation: "${translation?['translated_sentence']}"');
  print('     just_translated: ${translation?['just_translated']} ⚡');
  
  print('');
}
```

### Verificar que TTS está Habilitado

```dart
void _checkTTSConfiguration() async {
  // Durante inicialización de sesión
  final response = await http.post(
    Uri.parse('http://localhost:8000/session/init'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'preferences': {
        'tts_enabled': true,   // ✅ DEBE SER TRUE
        'tts_muted': false,    // ✅ DEBE SER FALSE
        'auto_translate': false,
        'word_pause_ms': 4000,
        'phrase_pause_ms': 8000,
      }
    }),
  );
  
  final data = jsonDecode(response.body);
  final prefs = data['preferences'] as Map<String, dynamic>;
  
  print('✅ Session initialized with TTS:');
  print('   tts_enabled: ${prefs['tts_enabled']}');
  print('   tts_muted: ${prefs['tts_muted']}');
  
  if (!prefs['tts_enabled'] || prefs['tts_muted']) {
    print('⚠️  WARNING: TTS is not properly enabled!');
  }
}
```

---

## 🐛 Troubleshooting

### Problema: "No escucho nada cuando termina la oración"

**Verificación 1: Campos just_completed**
```dart
// ✅ CORRECTO: Debe ser TRUE cuando se completa
sentence.just_completed: true

// ❌ INCORRECTO: Siempre FALSE
sentence.just_completed: false
```

**Verificación 2: Texto completado**
```dart
// ✅ CORRECTO: Debe ser un string
sentence.completed: "hola mundo"

// ❌ INCORRECTO: Es un boolean
sentence.completed: true  // ← BUG (ya corregido en backend)
```

**Verificación 3: Audio disponible**
```dart
// ✅ CORRECTO: Audio debe estar presente
tts.audio_available: true
tts.audio_base64: "UklGR..." // String largo base64

// ❌ INCORRECTO: No hay audio
tts.audio_available: false
tts.audio_base64: null
```

### Problema: "sentence.completed es boolean en vez de string"

**Solución:** Reiniciar el backend después de aplicar el fix:

```bash
# 1. Detener servidor (Ctrl+C en terminal donde corre uvicorn)
# 2. Reiniciar servidor
python -m uvicorn api.api_main:app --host 0.0.0.0 --port 8000
```

**Cambio aplicado en backend:**
```python
# ❌ ANTES (BUG):
"sentence": {
    "completed": self.sentence_completed,  # boolean!
}

# ✅ DESPUÉS (CORREGIDO):
"sentence": {
    "completed": self.completed_sentence,  # string!
}
```

### Problema: "audio_base64 está vacío"

**Causa:** TTS está deshabilitado en preferencias.

**Solución:**
```dart
// Al inicializar sesión, asegurar:
{
  "preferences": {
    "tts_enabled": true,    // ✅ 
    "tts_muted": false      // ✅
  }
}
```

---

## ⚡ Eventos Importantes (just_* flags)

Estos campos son **TRUE solo durante 1 frame** después del evento:

| Campo | Cuándo es TRUE | Acción Frontend |
|-------|----------------|-----------------|
| `word.just_finished` | Palabra completada | Actualizar UI, mostrar palabra corregida |
| `sentence.just_completed` | Oración completada | **🔊 REPRODUCIR TTS** |
| `translation.just_translated` | Traducción completada | Mostrar traducción |
| `tts.just_generated` | Audio TTS generado | Audio disponible en `audio_base64` |

**⚠️ IMPORTANTE:** Estos flags se resetean inmediatamente después, así que **debes actuar en el primer frame donde aparezcan**.

---

## 📝 Ejemplo Completo - Flutter

```dart
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:path_provider/path_provider.dart';

class BridgeTTSWebSocket {
  WebSocketChannel? _channel;
  String? _sessionId;
  final AudioPlayer _audioPlayer = AudioPlayer();
  
  // 1. Inicializar sesión
  Future<void> initialize() async {
    final response = await http.post(
      Uri.parse('http://localhost:8000/session/init'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'preferences': {
          'tts_enabled': true,
          'tts_muted': false,
          'auto_translate': false,
          'word_pause_ms': 4000,
          'phrase_pause_ms': 8000,
        }
      }),
    );
    
    final data = jsonDecode(response.body);
    _sessionId = data['session_id'];
    
    print('✅ Session initialized: $_sessionId');
  }
  
  // 2. Conectar WebSocket
  Future<void> connect() async {
    if (_sessionId == null) {
      throw Exception('Session not initialized');
    }
    
    _channel = WebSocketChannel.connect(
      Uri.parse('ws://localhost:8000/realtime/ws/detection/$_sessionId'),
    );
    
    // Escuchar mensajes
    _channel!.stream.listen(
      _handleMessage,
      onError: (error) => print('❌ WebSocket error: $error'),
      onDone: () => print('🔌 WebSocket closed'),
    );
    
    // Enviar comando PLAY
    _sendControl('play');
    
    print('✅ WebSocket connected');
  }
  
  // 3. Enviar frames
  void sendFrame(String base64Frame) {
    _channel?.sink.add(jsonEncode({
      'type': 'frame',
      'frameBase64': base64Frame,
    }));
  }
  
  // 4. Manejar mensajes del backend
  void _handleMessage(dynamic message) {
    final data = jsonDecode(message);
    
    if (data['type'] != 'state_update') return;
    
    // 🎯 Detectar oración completada
    final sentence = data['sentence'] as Map<String, dynamic>?;
    final justCompleted = sentence?['just_completed'] as bool? ?? false;
    
    if (justCompleted) {
      final completedText = sentence?['completed'] as String? ?? '';
      print('✅ Sentence completed: $completedText');
      
      // Reproducir TTS
      _playTTS(data);
    }
  }
  
  // 5. Reproducir TTS
  Future<void> _playTTS(Map<String, dynamic> message) async {
    final tts = message['tts'] as Map<String, dynamic>?;
    if (tts == null) return;
    
    final audioBase64 = tts['audio_base64'] as String?;
    if (audioBase64 == null || audioBase64.isEmpty) return;
    
    try {
      // Decodificar y guardar
      final audioBytes = base64Decode(audioBase64);
      final tempDir = await getTemporaryDirectory();
      final tempFile = File('${tempDir.path}/tts_${DateTime.now().millisecondsSinceEpoch}.mp3');
      await tempFile.writeAsBytes(audioBytes);
      
      // Reproducir
      await _audioPlayer.play(DeviceFileSource(tempFile.path));
      print('🔊 TTS audio playing');
      
      // Limpiar después
      _audioPlayer.onPlayerComplete.listen((_) {
        tempFile.delete();
      });
      
    } catch (e) {
      print('❌ Error playing TTS: $e');
    }
  }
  
  // Helpers
  void _sendControl(String action) {
    _channel?.sink.add(jsonEncode({
      'type': 'control',
      'action': action,
    }));
  }
  
  void dispose() {
    _channel?.sink.close();
    _audioPlayer.dispose();
  }
}
```

---

## 🚀 Testing en Backend

Si necesitas verificar que el backend está enviando datos correctos:

```bash
# 1. Ejecutar cliente de prueba visual
python main_ws_visual.py

# 2. Verificar en consola que aparezca:
#    sentence.just_completed: True | completed: 'texto aquí'
#    🔊 Playing TTS for completed sentence: 'texto aquí'
```

---

## 📊 Resumen de Cambios en Backend

### Bug Corregido (2025-11-21)

**Archivo:** `engine_bridge/session_engine.py`

```python
# ❌ ANTES (línea 533):
"sentence": {
    "completed": self.sentence_completed,  # boolean (True/False)
}

# ✅ AHORA (corregido):
"sentence": {
    "completed": self.completed_sentence,  # string ("hola mundo")
}
```

**Impacto:** 
- Antes el campo `sentence.completed` retornaba `true/false`
- Ahora retorna el texto de la oración: `"hola mundo"`
- Frontend debe leer este campo cuando `sentence.just_completed == true`

---

## 🎓 Conclusión

El TTS automático funciona con estos 3 pasos simples:

1. **Detectar evento:** `sentence.just_completed == true`
2. **Obtener texto:** `sentence.completed` (ahora es string)
3. **Reproducir audio:** `tts.audio_base64` (MP3 en base64)

**No olvides reiniciar el backend** después del fix para que tome efecto.

¡Buena suerte con la integración! 🚀
