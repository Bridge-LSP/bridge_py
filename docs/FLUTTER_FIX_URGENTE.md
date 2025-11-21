# 🚨 FLUTTER FIX URGENTE - Estado WebSocket no se actualiza en UI

## 📋 DIAGNÓSTICO COMPLETO

### ✅ Backend (FUNCIONANDO CORRECTAMENTE)
```
✋ MediaPipe: detected 1 hand(s)
🌲 RF prediction result: 'p' (confidence: 0.360)
📤 [WS] Sent state update | session: d7fca8c7... | letter: P  ← ✅ SE ENVÍA
```

**Confirmado:**
- ✅ WebSocket conectado
- ✅ Frames recibidos del frontend
- ✅ Detección de manos funcionando (MediaPipe)
- ✅ Clasificación de letras funcionando (Random Forest)
- ✅ Estados enviados por WebSocket cada frame

### ❌ Frontend Flutter (NO ACTUALIZA UI)

**Problema:** El frontend NO muestra:
- ❌ Letra detectada (`detection.letter`)
- ❌ Palabra que se va formando (`word.raw_buffer` o `word.corrected`)
- ❌ Frase completa (`sentence.current`)
- ❌ TTS no suena cuando termina la frase

---

## 🔍 ESTRUCTURA DEL MENSAJE QUE LLEGA DESDE BACKEND

Cada frame procesado envía un JSON como este:

```json
{
  "detection": {
    "letter": "p",
    "confidence": 0.360,
    "timestamp": 1732183504.123
  },
  "word": {
    "raw_buffer": "pppppp",
    "corrected": "",
    "just_corrected": false
  },
  "sentence": {
    "current": "",
    "completed": "",
    "just_completed": false
  },
  "translation": {
    "translated_sentence": "",
    "target_language": "en"
  },
  "tts": {
    "audio_available": false,
    "audio_base64": null,
    "just_generated": false
  },
  "processing_time_ms": 45.2
}
```

---

## 🛠️ SOLUCIÓN PASO A PASO

### 📁 **Archivo 1: `lib/core/services/bridge_session_service.dart`**

#### ❌ **PROBLEMA ACTUAL:**

El servicio probablemente tiene uno de estos problemas:
1. **No está parseando correctamente el JSON del WebSocket**
2. **El stream de estados no está emitiendo correctamente**
3. **Está filtrando mensajes cuando no debería**

#### ✅ **SOLUCIÓN:**

Verifica el método `connectWebSocket()` en `BridgeSessionService`:

```dart
Future<void> connectWebSocket(String websocketUrl) async {
  try {
    LoggerService.debug('🔌 Connecting to WebSocket...');
    LoggerService.debug('   URL: $websocketUrl');

    _channel = WebSocketChannel.connect(Uri.parse(websocketUrl));

    _isConnected = true;
    _connectionController.add(true);

    // ⚠️ CRÍTICO: Verificar esta parte
    _channel!.stream.listen(
      (message) {
        try {
          // 🔥 AGREGAR ESTE LOG PARA DEBUG
          LoggerService.debug('📨 RAW WebSocket message received:');
          LoggerService.debug(message.toString());
          
          final json = jsonDecode(message as String) as Map<String, dynamic>;
          
          // 🔥 AGREGAR ESTE LOG PARA DEBUG
          LoggerService.debug('📨 Parsed JSON:');
          LoggerService.debug('   detection.letter: ${json['detection']?['letter']}');
          LoggerService.debug('   word.raw_buffer: ${json['word']?['raw_buffer']}');
          LoggerService.debug('   word.corrected: ${json['word']?['corrected']}');
          LoggerService.debug('   sentence.current: ${json['sentence']?['current']}');
          
          final state = BridgeSessionState.fromJson(json);
          
          // 🔥 AGREGAR ESTE LOG PARA DEBUG
          LoggerService.debug('📨 State object created:');
          LoggerService.debug('   state.detection?.letter: ${state.detection?.letter}');
          LoggerService.debug('   state.word?.rawBuffer: ${state.word?.rawBuffer}');
          
          // ⚠️ CRÍTICO: EMITIR AL STREAM SIN CONDICIONES
          _stateController.add(state);
          
        } catch (e, st) {
          LoggerService.error('❌ Failed to parse WebSocket message', e);
          LoggerService.debug('Stack trace: $st');
        }
      },
      onError: (error) {
        LoggerService.error('❌ WebSocket error', error);
        _isConnected = false;
        _connectionController.add(false);
      },
      onDone: () {
        LoggerService.debug('🔌 WebSocket connection closed');
        _isConnected = false;
        _isRunning = false;
        _connectionController.add(false);
      },
    );

    LoggerService.debug('✅ WebSocket connected successfully');

    // ⚡ CRÍTICO: Send PLAY command immediately after connecting
    await Future.delayed(const Duration(milliseconds: 100));
    _sendControlMessage("play");
    _isRunning = true;
    LoggerService.debug('▶️  Sent PLAY control message');
  } catch (e) {
    LoggerService.error('❌ Failed to connect WebSocket', e);
    _isConnected = false;
    _connectionController.add(false);
    rethrow;
  }
}
```

**⚠️ PUNTOS CRÍTICOS A VERIFICAR:**

1. **¿El `_stateController` está correctamente inicializado?**
   ```dart
   final _stateController = StreamController<BridgeSessionState>.broadcast();
   ```

2. **¿El getter `stateStream` está exponiendo el stream?**
   ```dart
   Stream<BridgeSessionState> get stateStream => _stateController.stream;
   ```

3. **¿NO hay filtros que bloqueen la emisión?** (NO debe haber condiciones como `if (state.detection != null)`)

---

### 📁 **Archivo 2: `lib/core/models/bridge_session_state.dart`**

#### ✅ **VERIFICAR MODELO:**

Asegúrate de que el modelo `BridgeSessionState` tenga estos campos:

```dart
class BridgeSessionState {
  final DetectionData? detection;
  final WordData? word;
  final SentenceData? sentence;
  final TranslationData? translation;
  final TtsData? tts;
  final double? processingTimeMs;

  BridgeSessionState({
    this.detection,
    this.word,
    this.sentence,
    this.translation,
    this.tts,
    this.processingTimeMs,
  });

  factory BridgeSessionState.fromJson(Map<String, dynamic> json) {
    return BridgeSessionState(
      detection: json['detection'] != null
          ? DetectionData.fromJson(json['detection'] as Map<String, dynamic>)
          : null,
      word: json['word'] != null
          ? WordData.fromJson(json['word'] as Map<String, dynamic>)
          : null,
      sentence: json['sentence'] != null
          ? SentenceData.fromJson(json['sentence'] as Map<String, dynamic>)
          : null,
      translation: json['translation'] != null
          ? TranslationData.fromJson(json['translation'] as Map<String, dynamic>)
          : null,
      tts: json['tts'] != null
          ? TtsData.fromJson(json['tts'] as Map<String, dynamic>)
          : null,
      processingTimeMs: json['processing_time_ms']?.toDouble(),
    );
  }
}

class DetectionData {
  final String letter;
  final double confidence;
  final double timestamp;

  DetectionData({
    required this.letter,
    required this.confidence,
    required this.timestamp,
  });

  factory DetectionData.fromJson(Map<String, dynamic> json) {
    return DetectionData(
      letter: json['letter'] as String? ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      timestamp: (json['timestamp'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class WordData {
  final String rawBuffer;
  final String corrected;
  final bool justCorrected;

  WordData({
    required this.rawBuffer,
    required this.corrected,
    required this.justCorrected,
  });

  factory WordData.fromJson(Map<String, dynamic> json) {
    return WordData(
      rawBuffer: json['raw_buffer'] as String? ?? '',
      corrected: json['corrected'] as String? ?? '',
      justCorrected: json['just_corrected'] as bool? ?? false,
    );
  }
}

class SentenceData {
  final String current;
  final String completed;
  final bool justCompleted;

  SentenceData({
    required this.current,
    required this.completed,
    required this.justCompleted,
  });

  factory SentenceData.fromJson(Map<String, dynamic> json) {
    return SentenceData(
      current: json['current'] as String? ?? '',
      completed: json['completed'] as String? ?? '',
      justCompleted: json['just_completed'] as bool? ?? false,
    );
  }
}

class TranslationData {
  final String translatedSentence;
  final String targetLanguage;

  TranslationData({
    required this.translatedSentence,
    required this.targetLanguage,
  });

  factory TranslationData.fromJson(Map<String, dynamic> json) {
    return TranslationData(
      translatedSentence: json['translated_sentence'] as String? ?? '',
      targetLanguage: json['target_language'] as String? ?? 'en',
    );
  }
}

class TtsData {
  final bool audioAvailable;
  final String? audioBase64;
  final bool justGenerated;

  TtsData({
    required this.audioAvailable,
    this.audioBase64,
    required this.justGenerated,
  });

  factory TtsData.fromJson(Map<String, dynamic> json) {
    return TtsData(
      audioAvailable: json['audio_available'] as bool? ?? false,
      audioBase64: json['audio_base64'] as String?,
      justGenerated: json['just_generated'] as bool? ?? false,
    );
  }
}
```

---

### 📁 **Archivo 3: `lib/features/home/home_screen.dart`**

#### ❌ **PROBLEMA PROBABLE:**

El listener del stream puede estar:
1. **No inicializado en `initState()`**
2. **Usando condiciones incorrectas para actualizar UI**
3. **No llamando a `setState()`**
4. **Cancelado prematuramente**

#### ✅ **SOLUCIÓN COMPLETA:**

```dart
class _HomeScreenState extends State<HomeScreen> {
  // ... otros campos ...
  
  late BridgeSessionService _sessionService;
  StreamSubscription<BridgeSessionState>? _stateSubscription;
  
  // Estados de UI
  String detectedLetter = '';
  String rawWord = '';
  String correctedWord = '';
  String sentence = '';
  String translation = '';
  bool isSessionRunning = false;
  bool isTtsMuted = false;
  
  @override
  void initState() {
    super.initState();
    _sessionService = BridgeSessionService();
    
    // ⚠️ CRÍTICO: Setup state listener INMEDIATAMENTE
    _setupStateListener();
    
    // ... resto del initState ...
  }
  
  void _setupStateListener() {
    _stateSubscription = _sessionService.stateStream.listen(
      (state) {
        if (!mounted) return;

        // 🔥 AGREGAR ESTE LOG PARA DEBUG
        LoggerService.debug('🎨 UI received state update:');
        LoggerService.debug('   detection.letter: ${state.detection?.letter}');
        LoggerService.debug('   word.rawBuffer: ${state.word?.rawBuffer}');
        LoggerService.debug('   word.corrected: ${state.word?.corrected}');
        LoggerService.debug('   sentence.current: ${state.sentence?.current}');

        setState(() {
          // ⚠️ ACTUALIZAR SIEMPRE, SIN CONDICIONES COMPLEJAS
          
          // 1. LETRA DETECTADA ACTUAL
          if (state.detection != null) {
            detectedLetter = state.detection!.letter.toUpperCase();
          }

          // 2. PALABRA QUE SE VA FORMANDO
          if (state.word != null) {
            // Mostrar buffer crudo (las letras que van llegando)
            rawWord = state.word!.rawBuffer;
            
            // Si hay corrección, mostrar la palabra corregida
            if (state.word!.corrected.isNotEmpty) {
              correctedWord = state.word!.corrected;
            }
          }

          // 3. FRASE COMPLETA
          if (state.sentence != null) {
            // Si hay frase en construcción, mostrarla
            if (state.sentence!.current.isNotEmpty) {
              sentence = state.sentence!.current;
            }
            
            // Si la frase acaba de completarse, preparar para TTS
            if (state.sentence!.justCompleted && state.sentence!.completed.isNotEmpty) {
              sentence = state.sentence!.completed;
              
              // ⚠️ CRÍTICO: Reproducir TTS si no está muteado
              if (!isTtsMuted) {
                LoggerService.debug('🔊 Sentence completed, checking for TTS...');
              }
            }
          }

          // 4. TRADUCCIÓN (opcional)
          if (state.translation != null && 
              state.translation!.translatedSentence.isNotEmpty) {
            translation = state.translation!.translatedSentence;
          }

          // 5. TTS (reproducir audio cuando esté disponible)
          if (state.tts != null &&
              state.tts!.audioAvailable &&
              state.tts!.justGenerated &&
              state.tts!.audioBase64 != null) {
            LoggerService.debug('🔊 TTS audio available, playing...');
            if (!isTtsMuted) {
              _playTtsAudio(state.tts!.audioBase64!);
            }
          }
        });
      },
      onError: (error) {
        LoggerService.error('❌ State stream error', error);
      },
    );
    
    LoggerService.debug('✅ State listener setup complete');
  }

  Future<void> _playTtsAudio(String audioBase64) async {
    try {
      // Remover el prefijo "data:audio/mp3;base64," si existe
      String cleanBase64 = audioBase64;
      if (audioBase64.contains(',')) {
        cleanBase64 = audioBase64.split(',')[1];
      }

      // Decodificar base64 a bytes
      final bytes = base64Decode(cleanBase64);

      // Guardar en archivo temporal
      final tempDir = await getTemporaryDirectory();
      final tempFile = File('${tempDir.path}/tts_audio_${DateTime.now().millisecondsSinceEpoch}.mp3');
      await tempFile.writeAsBytes(bytes);

      // Reproducir audio
      final audioPlayer = AudioPlayer();
      await audioPlayer.play(DeviceFileSource(tempFile.path));

      LoggerService.debug('✅ TTS audio playing');

      // Limpiar después de reproducir
      audioPlayer.onPlayerComplete.listen((_) {
        tempFile.delete();
        audioPlayer.dispose();
      });
    } catch (e) {
      LoggerService.error('❌ Failed to play TTS audio', e);
    }
  }

  void _handlePlayPauseToggle() async {
    if (isSessionRunning) {
      // DETENER DETECCIÓN
      _sessionService.stop();
      _stopFrameStreaming();
      setState(() {
        isSessionRunning = false;
        uiConnectionState = UiConnectionState.paused;
      });
      LoggerService.debug('⏸️  Session paused');
    } else {
      // INICIAR DETECCIÓN
      try {
        setState(() {
          uiConnectionState = UiConnectionState.connecting;
        });

        // 1. Inicializar sesión y obtener websocket_url del backend
        LoggerService.debug('📡 Initializing session...');
        final sessionData = await _sessionService.initSession();
        final websocketUrl = sessionData['websocket_url'] as String?;

        if (websocketUrl == null) {
          throw Exception('No websocket_url in session response');
        }

        LoggerService.debug('✅ Session initialized, connecting WebSocket...');

        // 2. Conectar WebSocket usando URL del backend
        await _sessionService.connectWebSocket(websocketUrl);

        // 3. Iniciar streaming de frames
        _startFrameStreaming();

        setState(() {
          isSessionRunning = true;
          uiConnectionState = UiConnectionState.connected;
        });

        LoggerService.debug('✅ Session started successfully');
      } catch (e) {
        LoggerService.error('❌ Failed to start session', e);
        setState(() {
          _hasError = true;
          uiConnectionState = UiConnectionState.error;
        });
        
        // Mostrar error al usuario
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error al iniciar sesión: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  void _handleClearSentence() {
    // Enviar comando de limpieza al backend
    _sessionService.clearAll();
    
    // Limpiar estado local
    setState(() {
      detectedLetter = '';
      rawWord = '';
      correctedWord = '';
      sentence = '';
      translation = '';
    });
    
    LoggerService.debug('🧹 Cleared all state');
  }

  void _handleToggleMute() {
    setState(() {
      isTtsMuted = !isTtsMuted;
    });
    
    LoggerService.debug('🔇 TTS muted: $isTtsMuted');
  }

  @override
  void dispose() {
    _stateSubscription?.cancel();
    _sessionService.disconnect();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Bridge LSP'),
        actions: [
          // Botón de mute/unmute
          IconButton(
            icon: Icon(isTtsMuted ? Icons.volume_off : Icons.volume_up),
            onPressed: _handleToggleMute,
          ),
          // Botón de limpiar
          IconButton(
            icon: Icon(Icons.clear_all),
            onPressed: _handleClearSentence,
          ),
        ],
      ),
      body: Column(
        children: [
          // Cámara
          Expanded(
            flex: 3,
            child: _buildCameraPreview(),
          ),
          
          // Letra detectada (grande, en tiempo real)
          Container(
            padding: EdgeInsets.all(16),
            child: Text(
              detectedLetter.isEmpty ? '·' : detectedLetter,
              style: TextStyle(
                fontSize: 80,
                fontWeight: FontWeight.bold,
                color: Colors.blue,
              ),
            ),
          ),
          
          // Palabra que se va formando
          Container(
            padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Palabra en construcción:', style: TextStyle(fontSize: 12, color: Colors.grey)),
                SizedBox(height: 4),
                Text(
                  rawWord.isEmpty ? '(esperando letras...)' : rawWord,
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w500,
                    color: Colors.black87,
                    letterSpacing: 2,
                  ),
                ),
                if (correctedWord.isNotEmpty) ...[
                  SizedBox(height: 8),
                  Text('Corregida:', style: TextStyle(fontSize: 12, color: Colors.grey)),
                  Text(
                    correctedWord,
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      color: Colors.green,
                    ),
                  ),
                ],
              ],
            ),
          ),
          
          // Frase completa (cajita)
          Container(
            margin: EdgeInsets.all(16),
            padding: EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.blue.shade50,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.blue.shade200, width: 2),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Frase:', style: TextStyle(fontSize: 14, color: Colors.grey)),
                    IconButton(
                      icon: Icon(Icons.clear, size: 20),
                      onPressed: _handleClearSentence,
                      tooltip: 'Limpiar frase',
                    ),
                  ],
                ),
                SizedBox(height: 8),
                Text(
                  sentence.isEmpty ? '(detectando signos...)' : sentence,
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w600,
                    color: Colors.black87,
                  ),
                ),
                if (translation.isNotEmpty) ...[
                  SizedBox(height: 8),
                  Text('Traducción:', style: TextStyle(fontSize: 12, color: Colors.grey)),
                  Text(
                    translation,
                    style: TextStyle(
                      fontSize: 18,
                      fontStyle: FontStyle.italic,
                      color: Colors.blue.shade700,
                    ),
                  ),
                ],
              ],
            ),
          ),
          
          // Botón PLAY/PAUSE
          Padding(
            padding: EdgeInsets.all(16),
            child: ElevatedButton(
              onPressed: _handlePlayPauseToggle,
              style: ElevatedButton.styleFrom(
                padding: EdgeInsets.symmetric(horizontal: 48, vertical: 16),
                backgroundColor: isSessionRunning ? Colors.red : Colors.green,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(isSessionRunning ? Icons.pause : Icons.play_arrow),
                  SizedBox(width: 8),
                  Text(
                    isSessionRunning ? 'PAUSAR' : 'INICIAR',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
```

---

## 📦 DEPENDENCIAS REQUERIDAS

Verifica que en `pubspec.yaml` tengas:

```yaml
dependencies:
  flutter:
    sdk: flutter
  
  # WebSocket
  web_socket_channel: ^2.4.0
  
  # HTTP
  http: ^1.1.0
  
  # Environment variables
  flutter_dotenv: ^5.1.0
  
  # Audio playback
  audioplayers: ^5.2.1
  path_provider: ^2.1.1
  
  # Camera
  camera: ^0.10.5
  
  # Image processing
  image: ^4.1.3
```

---

## 🧪 TESTING & DEBUGGING

### 1. **Agregar estos logs en Flutter para debug:**

En `main.dart`:
```dart
void main() {
  // Habilitar logs detallados
  WidgetsFlutterBinding.ensureInitialized();
  
  LoggerService.setLogLevel(LogLevel.DEBUG);
  
  runApp(MyApp());
}
```

### 2. **Verificar logs en orden:**

Cuando presiones PLAY, deberías ver:

```
📡 Initializing session...
✅ Session initialized, connecting WebSocket...
🔌 Connecting to WebSocket...
   URL: ws://192.168.0.15:8000/realtime/ws/detection/d7fca8c7...
✅ WebSocket connected successfully
▶️  Sent PLAY control message
✅ State listener setup complete
📨 RAW WebSocket message received:
{"detection": {"letter": "p", ...}, "word": {...}, ...}
📨 Parsed JSON:
   detection.letter: p
   word.raw_buffer: pppppp
🎨 UI received state update:
   detection.letter: p
   word.rawBuffer: pppppp
```

### 3. **Si NO ves los logs `📨 RAW WebSocket message received:`:**

El problema es que el WebSocket NO está recibiendo mensajes. Verifica:

1. **¿El stream listener está activo?**
   ```dart
   _channel!.stream.listen((message) { ... })
   ```

2. **¿El stream está cerrado prematuramente?**
   - NO canceles el listener antes de tiempo
   - NO cierres el WebSocket channel mientras está en uso

3. **¿Hay algún filtro bloqueando mensajes?**
   - Revisa si hay condiciones como `if (state.detection != null && state.detection.letter.isNotEmpty)`
   - DEBE emitir TODOS los estados sin filtrar

---

## 🎯 COMPORTAMIENTO ESPERADO

### Flujo completo:

1. **Usuario presiona PLAY** → UI muestra "Conectando..."
2. **Backend se conecta** → UI muestra "Conectado"
3. **Usuario hace signo de letra "P"**:
   - Letra grande muestra: **P**
   - Palabra muestra: **p**, luego **pp**, luego **ppp** (se va formando)
4. **Usuario espera 4 segundos** (fin de palabra):
   - Palabra se autocorrige (si hay corrector BERT)
   - Palabra muestra: **papa** (corregida)
5. **Usuario continúa con siguiente palabra** ("hola"):
   - Letra muestra: **h**, **o**, **l**, **a**
   - Palabra muestra: **hola**
   - Frase muestra: **papa hola**
6. **Usuario espera 8 segundos** (fin de frase):
   - Frase se completa: **papa hola**
   - Si TTS NO está muteado → **SUENA EL AUDIO** 🔊
   - Si TTS está muteado → NO suena
7. **Usuario presiona botón limpiar** → Frase se borra

---

## 📝 RESUMEN DE CAMBIOS CRÍTICOS

| Archivo | Cambio | Prioridad |
|---------|--------|-----------|
| `bridge_session_service.dart` | Agregar logs en `connectWebSocket()` para debug | 🔴 CRÍTICO |
| `bridge_session_service.dart` | Asegurar que `_stateController.add(state)` se llama SIEMPRE | 🔴 CRÍTICO |
| `home_screen.dart` | Llamar `_setupStateListener()` en `initState()` | 🔴 CRÍTICO |
| `home_screen.dart` | Actualizar UI con `setState()` en CADA mensaje | 🔴 CRÍTICO |
| `home_screen.dart` | Implementar `_playTtsAudio()` para reproducir audio | 🟡 IMPORTANTE |
| `home_screen.dart` | Agregar botón mute/unmute | 🟡 IMPORTANTE |
| `home_screen.dart` | Agregar botón limpiar frase | 🟡 IMPORTANTE |

---

## 🆘 SI SIGUE SIN FUNCIONAR

1. **Ejecuta la app en modo DEBUG** y activa breakpoints en:
   - `_channel!.stream.listen((message) { ... })` ← ¿Llega aquí?
   - `_stateController.add(state)` ← ¿Emite el estado?
   - `_stateSubscription = _sessionService.stateStream.listen(...)` ← ¿Recibe el estado?
   - `setState(() { ... })` ← ¿Actualiza la UI?

2. **Verifica que el WebSocket NO se cierra prematuramente:**
   ```dart
   _channel!.stream.listen(
     (message) { ... },
     onDone: () {
       print('❌ WebSocket stream closed!'); // ← ¿Aparece este log?
     },
   );
   ```

3. **Prueba con un log simple en el listener:**
   ```dart
   _channel!.stream.listen(
     (message) {
       print('🔥 RECEIVED: ${message.toString().substring(0, 100)}');
       // ... resto del código
     },
   );
   ```

---

## ✅ CHECKLIST FINAL

- [ ] Logs de debug agregados en `connectWebSocket()`
- [ ] `_stateController.add(state)` se llama sin condiciones
- [ ] `_setupStateListener()` se llama en `initState()`
- [ ] `setState()` actualiza UI en cada mensaje
- [ ] `_playTtsAudio()` implementado
- [ ] Botón mute/unmute funcional
- [ ] Botón limpiar frase funcional
- [ ] Dependencias instaladas (`audioplayers`, `path_provider`)
- [ ] Prueba completa: letra → palabra → frase → TTS

---

**¡Con estos cambios el frontend DEBE funcionar correctamente!** 🚀

El backend está enviando los datos perfectamente, solo falta que Flutter los reciba y actualice la UI.
