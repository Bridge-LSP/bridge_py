# Flutter Integration Guide - Bridge LSP API

> **Complete integration guide for real-time Peruvian Sign Language detection, translation, and text-to-speech in Flutter applications.**

## Overview

Bridge LSP API provides production-ready real-time Peruvian Sign Language detection with automatic translation and text-to-speech capabilities. This guide covers complete Flutter integration from camera setup to voice output.

## Quick Start

**Core Features:**
- Real-time LSP detection from camera feed
- Automatic word and phrase completion with timers
- Instant translation (Spanish ↔ English)
- Text-to-speech audio generation
- WebSocket real-time updates
- Performance monitoring and analytics

**Essential Endpoints:**
1. `POST /session/init` - Initialize detection session
2. `POST /detection/continuous-detect` - Main detection loop
3. `POST /phrase/finalize` - Complete phrase with translation & TTS
4. `WS /realtime/ws/detection/{client_id}` - Real-time WebSocket updates

---

## API Configuration

### Environment URLs

```dart
class BridgeApiConfig {
  // Development (local server)
  static const String DEV_BASE_URL = 'http://127.0.0.1:8000';
  static const String DEV_WS_URL = 'ws://127.0.0.1:8000';
  
  // Production (Google Cloud Run)
  static const String PROD_BASE_URL = 'https://bridge-api-154694118574.europe-west1.run.app';
  static const String PROD_WS_URL = 'wss://bridge-api-154694118574.europe-west1.run.app';
  
  // Current environment
  static const bool isDevelopment = true; // Set to false for production
  
  static String get baseUrl => isDevelopment ? DEV_BASE_URL : PROD_BASE_URL;
  static String get wsUrl => isDevelopment ? DEV_WS_URL : PROD_WS_URL;
  
  // Android emulator specific (if needed)
  static const String ANDROID_EMULATOR_URL = 'http://10.0.2.2:8000';
}

## API Endpoints

### Core Detection Endpoints
```
POST /session/init                      # Initialize detection session
POST /detection/continuous-detect       # Main detection loop (200-300ms intervals)
POST /phrase/finalize                   # Complete phrase with translation & TTS
GET  /health                            # API health check
```

### Real-Time Communication
```
WS   /realtime/ws/detection/{client_id} # WebSocket for real-time updates
GET  /realtime/ws/status                # WebSocket connection status
```

### Timer Management
```
POST /timers/word/auto-finish           # Force word completion (2s default)
POST /timers/phrase/auto-finish         # Force phrase completion (5s default)
GET  /timers/status/{session_id}        # Get current timer status
POST /detection/reset-detection-state   # Reset all detection state
```

### Session Management
```
GET  /session/status/{session_id}       # Get session information
DELETE /session/destroy/{session_id}    # Clean session destruction
```

---

## Home Screen Integration

### 1. Dependencies Setup

Add to your `pubspec.yaml`:

```yaml
dependencies:
  flutter:
    sdk: flutter
  camera: ^0.10.5
  dio: ^5.3.2
  web_socket_channel: ^2.4.0
  just_audio: ^0.9.34
  permission_handler: ^10.4.3
  image: ^4.0.17

dev_dependencies:
  flutter_test:
    sdk: flutter
```

### 2. Permissions Setup

**Android** (`android/app/src/main/AndroidManifest.xml`):
```xml
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.INTERNET" />
<uses-feature android:name="android.hardware.camera" android:required="true" />
```

**iOS** (`ios/Runner/Info.plist`):
```xml
<key>NSCameraUsageDescription</key>
<string>This app needs camera access for sign language detection</string>
<key>NSMicrophoneUsageDescription</key>
<string>This app needs microphone access for audio playback</string>
```

### 3. Complete Home Screen Implementation

```dart
// home_screen.dart
import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:dio/dio.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:just_audio/just_audio.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:image/image.dart' as img;

class HomeScreen extends StatefulWidget {
  @override
  _HomeScreenState createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // Bridge API Integration
  BridgeApiService? _apiService;
  LSPDetectionService? _detectionService;
  WebSocketManager? _wsManager;
  
  // Camera
  CameraController? _cameraController;
  List<CameraDescription>? _cameras;
  bool _isCameraInitialized = false;
  
  // Detection State
  String _currentLetter = '';
  String _currentWord = '';
  String _currentSentence = '';
  double _confidence = 0.0;
  bool _isDetecting = false;
  bool _isConnected = false;
  
  // Timers
  bool _wordTimerActive = false;
  bool _phraseTimerActive = false;
  
  // Audio
  final AudioPlayer _audioPlayer = AudioPlayer();
  
  @override
  void initState() {
    super.initState();
    _initializeApp();
  }
  
  Future<void> _initializeApp() async {
    await _requestPermissions();
    await _initializeCamera();
    await _initializeBridgeAPI();
  }
  
  Future<void> _requestPermissions() async {
    await [
      Permission.camera,
      Permission.microphone,
    ].request();
  }
  
  Future<void> _initializeCamera() async {
    try {
      _cameras = await availableCameras();
      if (_cameras!.isNotEmpty) {
        _cameraController = CameraController(
          _cameras![0], // Front camera for sign language
          ResolutionPreset.medium,
          enableAudio: false,
        );
        
        await _cameraController!.initialize();
        setState(() {
          _isCameraInitialized = true;
        });
        
        _startCameraStream();
      }
    } catch (e) {
      print('Camera initialization error: $e');
    }
  }
  
  Future<void> _initializeBridgeAPI() async {
    try {
      _apiService = BridgeApiService();
      
      // Initialize session
      await _apiService!.initializeSession(
        preferences: {
          'tts_enabled': true,
          'voice_language': 'es',
          'auto_translate': true,
          'target_language': 'en',
        }
      );
      
      // Initialize detection service
      _detectionService = LSPDetectionService(_apiService!);
      
      // Initialize WebSocket
      _wsManager = WebSocketManager(
        sessionId: _apiService!.sessionId,
        clientId: 'flutter_home_${DateTime.now().millisecondsSinceEpoch}',
      );
      
      _wsManager!.onStateUpdate = _handleDetectionUpdate;
      _wsManager!.onConnectionChange = (connected) {
        setState(() {
          _isConnected = connected;
        });
      };
      
      await _wsManager!.connect();
      
      print('✅ Bridge API initialized successfully');
    } catch (e) {
      print('❌ Bridge API initialization error: $e');
    }
  }
  
  void _startCameraStream() {
    if (_cameraController != null && _cameraController!.value.isInitialized) {
      // Stream frames every 300ms to avoid overwhelming the API
      Timer.periodic(Duration(milliseconds: 300), (timer) {
        if (_isDetecting && _isCameraInitialized) {
          _captureAndAnalyzeFrame();
        }
        
        if (!mounted) {
          timer.cancel();
        }
      });
    }
  }
  
  Future<void> _captureAndAnalyzeFrame() async {
    if (_cameraController == null || !_cameraController!.value.isInitialized) {
      return;
    }
    
    try {
      final XFile picture = await _cameraController!.takePicture();
      final bytes = await picture.readAsBytes();
      
      // Resize and compress image for better performance
      final compressedImage = _compressImage(bytes);
      final base64Frame = base64Encode(compressedImage);
      
      // Send to detection service
      await _detectionService!.detectFromFrame(base64Frame);
      
    } catch (e) {
      print('Frame capture error: $e');
    }
  }
  
  Uint8List _compressImage(Uint8List bytes) {
    final image = img.decodeImage(bytes);
    if (image == null) return bytes;
    
    // Resize to 480x320 for optimal performance
    final resized = img.copyResize(image, width: 480, height: 320);
    
    // Compress to JPEG with 65% quality
    return Uint8List.fromList(img.encodeJpg(resized, quality: 65));
  }
  
  void _handleDetectionUpdate(DetectionState state) {
    setState(() {
      if (state.letterDetected != null) _currentLetter = state.letterDetected!;
      if (state.wordBuffer.isNotEmpty) _currentWord = state.wordBuffer;
      if (state.sentence.isNotEmpty) _currentSentence = state.sentence;
      if (state.confidence != null) _confidence = state.confidence!;
      _wordTimerActive = state.wordTimerActive;
      _phraseTimerActive = state.phraseTimerActive;
    });
  }
  
  Future<void> _finalizePhrase() async {
    if (_detectionService == null) return;
    
    try {
      final result = await _detectionService!.finalizePhrase(
        autoTranslate: true,
        ttsEnabled: true,
      );
      
      // Show completion dialog
      _showPhraseCompletionDialog(result);
      
      // Play TTS audio if available
      if (result.hasAudio()) {
        await _playTTSAudio(result.getAudioBytes()!);
      }
      
    } catch (e) {
      _showErrorDialog('Failed to finalize phrase: $e');
    }
  }
  
  Future<void> _playTTSAudio(Uint8List audioBytes) async {
    try {
      await _audioPlayer.setAudioSource(
        AudioSource.bytes(audioBytes, tag: AudioMetadata(title: 'TTS Audio'))
      );
      await _audioPlayer.play();
    } catch (e) {
      print('Audio playback error: $e');
    }
  }
  
  void _showPhraseCompletionDialog(PhraseResult result) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Phrase Completed'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Sign Language: ${result.phraseFinalized}'),
            if (result.hasTranslation()) ...[
              SizedBox(height: 8),
              Text('Translation: ${result.translated}'),
            ],
            SizedBox(height: 8),
            Text('Processing Time: ${result.processingTimeMs}ms'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text('OK'),
          ),
        ],
      ),
    );
  }
  
  void _showErrorDialog(String message) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Error'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text('OK'),
          ),
        ],
      ),
    );
  }
  
  Future<void> _resetDetection() async {
    if (_detectionService != null) {
      await _detectionService!.resetState();
      setState(() {
        _currentLetter = '';
        _currentWord = '';
        _currentSentence = '';
        _confidence = 0.0;
        _wordTimerActive = false;
        _phraseTimerActive = false;
      });
    }
  }
  
  void _toggleDetection() {
    setState(() {
      _isDetecting = !_isDetecting;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Bridge LSP Detection'),
        backgroundColor: Colors.blue[800],
        foregroundColor: Colors.white,
        actions: [
          // Connection status indicator
          Container(
            padding: EdgeInsets.all(8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  _isConnected ? Icons.wifi : Icons.wifi_off,
                  color: _isConnected ? Colors.green : Colors.red,
                  size: 20,
                ),
                SizedBox(width: 4),
                Text(
                  _isConnected ? 'Connected' : 'Disconnected',
                  style: TextStyle(fontSize: 12),
                ),
              ],
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          // Camera Preview
          Expanded(
            flex: 3,
            child: Container(
              width: double.infinity,
              child: _isCameraInitialized
                  ? Stack(
                      children: [
                        CameraPreview(_cameraController!),
                        // Detection overlay
                        Positioned(
                          top: 16,
                          left: 16,
                          right: 16,
                          child: Container(
                            padding: EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.black54,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Column(
                              children: [
                                Text(
                                  'Current Letter: $_currentLetter',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 18,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                Text(
                                  'Confidence: ${(_confidence * 100).toStringAsFixed(1)}%',
                                  style: TextStyle(
                                    color: Colors.white70,
                                    fontSize: 14,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                        // Timer indicators
                        Positioned(
                          bottom: 16,
                          right: 16,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              if (_wordTimerActive)
                                Container(
                                  padding: EdgeInsets.symmetric(
                                    horizontal: 8,
                                    vertical: 4,
                                  ),
                                  decoration: BoxDecoration(
                                    color: Colors.orange,
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    'Word Timer',
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontSize: 12,
                                    ),
                                  ),
                                ),
                              SizedBox(width: 8),
                              if (_phraseTimerActive)
                                Container(
                                  padding: EdgeInsets.symmetric(
                                    horizontal: 8,
                                    vertical: 4,
                                  ),
                                  decoration: BoxDecoration(
                                    color: Colors.green,
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    'Phrase Timer',
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontSize: 12,
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ],
                    )
                  : Center(
                      child: CircularProgressIndicator(),
                    ),
            ),
          ),
          
          // Detection Results
          Expanded(
            flex: 2,
            child: Container(
              width: double.infinity,
              padding: EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.grey[100],
                border: Border(
                  top: BorderSide(color: Colors.grey[300]!),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Current Word
                  Text(
                    'Current Word:',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                      color: Colors.grey[700],
                    ),
                  ),
                  SizedBox(height: 4),
                  Container(
                    width: double.infinity,
                    padding: EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.grey[300]!),
                    ),
                    child: Text(
                      _currentWord.isEmpty ? '(detecting...)' : _currentWord,
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: _currentWord.isEmpty ? Colors.grey[400] : Colors.black,
                      ),
                    ),
                  ),
                  
                  SizedBox(height: 16),
                  
                  // Current Sentence
                  Text(
                    'Current Sentence:',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                      color: Colors.grey[700],
                    ),
                  ),
                  SizedBox(height: 4),
                  Container(
                    width: double.infinity,
                    padding: EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.grey[300]!),
                    ),
                    child: Text(
                      _currentSentence.isEmpty ? '(building sentence...)' : _currentSentence,
                      style: TextStyle(
                        fontSize: 18,
                        color: _currentSentence.isEmpty ? Colors.grey[400] : Colors.black,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          
          // Control Buttons
          Container(
            padding: EdgeInsets.all(16),
            child: Column(
              children: [
                // Main detection toggle
                SizedBox(
                  width: double.infinity,
                  height: 50,
                  child: ElevatedButton(
                    onPressed: _toggleDetection,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _isDetecting ? Colors.red : Colors.green,
                      foregroundColor: Colors.white,
                    ),
                    child: Text(
                      _isDetecting ? 'Stop Detection' : 'Start Detection',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
                
                SizedBox(height: 12),
                
                // Action buttons row
                Row(
                  children: [
                    // Finalize phrase
                    Expanded(
                      child: ElevatedButton(
                        onPressed: _currentSentence.isNotEmpty ? _finalizePhrase : null,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.blue,
                          foregroundColor: Colors.white,
                        ),
                        child: Text('Complete & Translate'),
                      ),
                    ),
                    
                    SizedBox(width: 12),
                    
                    // Reset
                    Expanded(
                      child: ElevatedButton(
                        onPressed: _resetDetection,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.orange,
                          foregroundColor: Colors.white,
                        ),
                        child: Text('Reset'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
  
  @override
  void dispose() {
    _cameraController?.dispose();
    _wsManager?.disconnect();
    _audioPlayer.dispose();
    super.dispose();
  }
}
  
## Service Classes Implementation

### 1. Bridge API Service

```dart
// services/bridge_api_service.dart
import 'dart:convert';
import 'package:dio/dio.dart';

class BridgeApiService {
  late Dio _dio;
  String? sessionId;
  final String clientToken = _generateClientToken();
  
  BridgeApiService() {
    _dio = Dio(BaseOptions(
      baseUrl: BridgeApiConfig.baseUrl,
      connectTimeout: Duration(seconds: 10),
      receiveTimeout: Duration(seconds: 30),
      headers: {
        'Content-Type': 'application/json',
        'X-Client-Token': clientToken,
      },
    ));
    
    // Add logging interceptor for debugging
    _dio.interceptors.add(LogInterceptor(
      requestBody: true,
      responseBody: true,
      logPrint: (obj) => print('[Bridge API] $obj'),
    ));
  }
  
  static String _generateClientToken() {
    return 'flutter_${DateTime.now().millisecondsSinceEpoch}';
  }
  
  Future<SessionResponse> initializeSession({
    Map<String, dynamic>? preferences,
  }) async {
    try {
      final response = await _dio.post(
        '/session/init',
        data: {
          'preferences': preferences ?? {
            'tts_enabled': true,
            'voice_language': 'es',
            'auto_translate': true,
            'target_language': 'en',
          }
        },
      );
      
      if (response.statusCode == 200 && response.data['status'] == 'success') {
        final sessionResponse = SessionResponse.fromJson(response.data['data']);
        sessionId = sessionResponse.sessionId;
        return sessionResponse;
      } else {
        throw BridgeApiException(response.data['detail'] ?? 'Session initialization failed');
      }
    } on DioException catch (e) {
      throw BridgeApiException('Network error: ${e.message}');
    } catch (e) {
      throw BridgeApiException('Unexpected error: $e');
    }
  }
  
  Future<DetectionResponse> detectFromFrame(String base64Frame) async {
    if (sessionId == null) {
      throw BridgeApiException('Session not initialized. Call initializeSession() first.');
    }
    
    try {
      final response = await _dio.post(
        '/detection/continuous-detect',
        data: {
          'session_id': sessionId,
          'frameBase64': base64Frame,
          'enable_timers': true,
          'confidence_threshold': 0.70,
        },
      );
      
      if (response.statusCode == 200) {
        return DetectionResponse.fromJson(response.data);
      } else {
        throw BridgeApiException('Detection failed: ${response.data['detail']}');
      }
    } on DioException catch (e) {
      throw BridgeApiException('Detection request failed: ${e.message}');
    }
  }
  
  Future<PhraseResult> finalizePhrase({
    bool autoTranslate = true,
    String targetLanguage = 'en',
    bool ttsEnabled = true,
    String voiceLanguage = 'es',
  }) async {
    if (sessionId == null) {
      throw BridgeApiException('Session not initialized');
    }
    
    try {
      final response = await _dio.post(
        '/phrase/finalize',
        data: {
          'session_id': sessionId,
          'auto_translate': autoTranslate,
          'target_language': targetLanguage,
          'tts_enabled': ttsEnabled,
          'voice_language': voiceLanguage,
        },
      );
      
      if (response.statusCode == 200 && response.data['status'] == 'success') {
        return PhraseResult.fromJson(response.data['data']);
      } else {
        throw BridgeApiException('Phrase finalization failed: ${response.data['detail']}');
      }
    } on DioException catch (e) {
      throw BridgeApiException('Phrase finalization request failed: ${e.message}');
    }
  }
  
  Future<void> resetDetectionState() async {
    if (sessionId == null) return;
    
    try {
      await _dio.post(
        '/detection/reset-detection-state',
        data: {'session_id': sessionId},
      );
    } catch (e) {
      print('Reset state error: $e');
    }
  }
  
  Future<bool> checkHealth() async {
    try {
      final response = await _dio.get('/health');
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }
}

class BridgeApiException implements Exception {
  final String message;
  BridgeApiException(this.message);
  
  @override
  String toString() => 'BridgeApiException: $message';
}
```

### 2. LSP Detection Service

```dart
// services/lsp_detection_service.dart
import 'dart:async';

class LSPDetectionService {
  final BridgeApiService _apiService;
  StreamController<DetectionState>? _stateController;
  DetectionState _currentState = DetectionState();
  
  LSPDetectionService(this._apiService);
  
  Stream<DetectionState> get stateStream {
    _stateController ??= StreamController<DetectionState>.broadcast();
    return _stateController!.stream;
  }
  
  Future<void> detectFromFrame(String base64Frame) async {
    try {
      final response = await _apiService.detectFromFrame(base64Frame);
      
      // Update state only with changed fields for efficiency
      if (response.changed.isNotEmpty) {
        _currentState.updateFromResponse(response);
        _stateController?.add(_currentState);
      }
    } catch (e) {
      print('Detection error: $e');
    }
  }
  
  Future<PhraseResult> finalizePhrase({
    bool autoTranslate = true,
    bool ttsEnabled = true,
  }) async {
    return await _apiService.finalizePhrase(
      autoTranslate: autoTranslate,
      ttsEnabled: ttsEnabled,
    );
  }
  
  Future<void> resetState() async {
    await _apiService.resetDetectionState();
    _currentState = DetectionState();
    _stateController?.add(_currentState);
  }
  
  void dispose() {
    _stateController?.close();
  }
}
```

### 3. WebSocket Manager

```dart
// services/websocket_manager.dart
import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';

class WebSocketManager {
  WebSocketChannel? _channel;
  Timer? _heartbeatTimer;
  bool _isConnected = false;
  final String sessionId;
  final String clientId;
  
  // Callbacks
  Function(DetectionState)? onStateUpdate;
  Function(bool)? onConnectionChange;
  
  WebSocketManager({
    required this.sessionId,
    required this.clientId,
  });
  
  Future<void> connect() async {
    try {
      final wsUrl = '${BridgeApiConfig.wsUrl}/realtime/ws/detection/$clientId';
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      
      _isConnected = true;
      onConnectionChange?.call(true);
      _startHeartbeatMonitoring();
      
      // Listen for messages
      _channel!.stream.listen(
        (data) => _handleMessage(jsonDecode(data)),
        onError: (error) => _handleError(error),
        onDone: () => _handleDisconnect(),
      );
      
      print('✅ WebSocket connected to $wsUrl');
    } catch (e) {
      print('❌ WebSocket connection failed: $e');
      _isConnected = false;
      onConnectionChange?.call(false);
    }
  }
  
  void _startHeartbeatMonitoring() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(Duration(seconds: 10), (timer) {
      if (_isConnected && _channel != null) {
        // Server handles ping automatically, we just monitor connection
      } else {
        timer.cancel();
      }
    });
  }
  
  void _handleMessage(Map<String, dynamic> message) {
    switch (message['type']) {
      case 'ping':
        _sendPong();
        break;
      case 'detection_update':
        final state = DetectionState.fromWebSocket(message['data']);
        onStateUpdate?.call(state);
        break;
      case 'letter_added':
        print('Letter detected: ${message['letter']} (${message['confidence']})');
        break;
      case 'word_updated':
        print('Word updated: ${message['word']}');
        break;
      case 'phrase_completed':
        print('Phrase completed: ${message['phrase']}');
        break;
      case 'error':
        print('WebSocket error: ${message['message']}');
        break;
    }
  }
  
  void _sendPong() {
    if (_isConnected && _channel != null) {
      _channel!.sink.add(jsonEncode({'type': 'pong'}));
    }
  }
  
  void sendFrame(String base64Frame) {
    if (_isConnected && _channel != null) {
      _channel!.sink.add(jsonEncode({
        'type': 'frame',
        'data': base64Frame,
      }));
    }
  }
  
  void _handleError(dynamic error) {
    print('WebSocket error: $error');
    _isConnected = false;
    onConnectionChange?.call(false);
    
    // Attempt to reconnect after 3 seconds
    Timer(Duration(seconds: 3), () => connect());
  }
  
  void _handleDisconnect() {
    _isConnected = false;
    onConnectionChange?.call(false);
    _heartbeatTimer?.cancel();
    
    // Attempt to reconnect
    Timer(Duration(seconds: 2), () => connect());
  }
  
  void disconnect() {
    _heartbeatTimer?.cancel();
    _channel?.sink.close();
    _isConnected = false;
    onConnectionChange?.call(false);
  }
}
```

## Model Classes

### Data Models

```dart
// models/bridge_models.dart
import 'dart:convert';
import 'dart:typed_data';

class SessionResponse {
  final String sessionId;
  final List<String> modulesInitialized;
  final DateTime createdAt;
  
  SessionResponse({
    required this.sessionId,
    required this.modulesInitialized,
    required this.createdAt,
  });
  
  factory SessionResponse.fromJson(Map<String, dynamic> json) => SessionResponse(
    sessionId: json['session_id'],
    modulesInitialized: List<String>.from(json['modules_initialized'] ?? []),
    createdAt: DateTime.parse(json['created_at']),
  );
}

class DetectionResponse {
  final String status;
  final List<String> changed;
  final String? letterDetected;
  final double? confidence;
  final String wordBuffer;
  final String predictedWord;
  final String sentence;
  final bool wordTimerActive;
  final bool phraseTimerActive;
  
  DetectionResponse({
    required this.status,
    required this.changed,
    this.letterDetected,
    this.confidence,
    required this.wordBuffer,
    required this.predictedWord,
    required this.sentence,
    required this.wordTimerActive,
    required this.phraseTimerActive,
  });
  
  factory DetectionResponse.fromJson(Map<String, dynamic> json) => DetectionResponse(
    status: json['status'] ?? 'unknown',
    changed: List<String>.from(json['changed'] ?? []),
    letterDetected: json['letter_detected'],
    confidence: json['confidence']?.toDouble(),
    wordBuffer: json['word_buffer'] ?? '',
    predictedWord: json['predicted_word'] ?? '',
    sentence: json['sentence'] ?? '',
    wordTimerActive: json['word_timer_active'] ?? false,
    phraseTimerActive: json['phrase_timer_active'] ?? false,
  );
}

class DetectionState {
  String? letterDetected;
  double? confidence;
  String wordBuffer = '';
  String predictedWord = '';
  String sentence = '';
  bool wordTimerActive = false;
  bool phraseTimerActive = false;
  Set<String> changedFields = {};
  
  void updateFromResponse(DetectionResponse response) {
    changedFields = Set<String>.from(response.changed);
    
    if (response.changed.contains('letter_detected')) {
      letterDetected = response.letterDetected;
    }
    if (response.changed.contains('confidence')) {
      confidence = response.confidence;
    }
    if (response.changed.contains('word_buffer')) {
      wordBuffer = response.wordBuffer;
    }
    if (response.changed.contains('predicted_word')) {
      predictedWord = response.predictedWord;
    }
    if (response.changed.contains('sentence')) {
      sentence = response.sentence;
    }
    if (response.changed.contains('word_timer_active')) {
      wordTimerActive = response.wordTimerActive;
    }
    if (response.changed.contains('phrase_timer_active')) {
      phraseTimerActive = response.phraseTimerActive;
    }
  }
  
  factory DetectionState.fromWebSocket(Map<String, dynamic> data) {
    final state = DetectionState();
    state.letterDetected = data['letter_detected'];
    state.confidence = data['confidence']?.toDouble();
    state.wordBuffer = data['word_buffer'] ?? '';
    state.predictedWord = data['predicted_word'] ?? '';
    state.sentence = data['sentence'] ?? '';
    state.wordTimerActive = data['word_timer_active'] ?? false;
    state.phraseTimerActive = data['phrase_timer_active'] ?? false;
    return state;
  }
}

class PhraseResult {
  final String phraseFinalized;
  final String? translated;
  final String? ttsAudio;
  final int processingTimeMs;
  
  PhraseResult({
    required this.phraseFinalized,
    this.translated,
    this.ttsAudio,
    required this.processingTimeMs,
  });
  
  factory PhraseResult.fromJson(Map<String, dynamic> json) => PhraseResult(
    phraseFinalized: json['phrase_finalized'] ?? '',
    translated: json['translated'],
    ttsAudio: json['tts_audio'],
    processingTimeMs: json['processing_time_ms'] ?? 0,
  );
  
  bool hasTranslation() => translated != null && translated!.isNotEmpty;
  bool hasAudio() => ttsAudio != null && ttsAudio!.isNotEmpty;
  
  Uint8List? getAudioBytes() {
    if (ttsAudio == null) return null;
    try {
      return base64Decode(ttsAudio!);
    } catch (e) {
      print('Audio decode error: $e');
      return null;
    }
  }
}
```

## Performance Optimization

### Frame Processing Best Practices

```dart
// utils/frame_processor.dart
import 'dart:typed_data';
import 'package:image/image.dart' as img;

class FrameProcessor {
  static const int TARGET_WIDTH = 480;
  static const int TARGET_HEIGHT = 320;
  static const int JPEG_QUALITY = 65;
  
  static Uint8List processFrame(Uint8List imageBytes) {
    try {
      // Decode image
      final image = img.decodeImage(imageBytes);
      if (image == null) return imageBytes;
      
      // Resize for optimal performance
      final resized = img.copyResize(
        image,
        width: TARGET_WIDTH,
        height: TARGET_HEIGHT,
        interpolation: img.Interpolation.linear,
      );
      
      // Compress to JPEG
      final compressed = img.encodeJpg(resized, quality: JPEG_QUALITY);
      
      return Uint8List.fromList(compressed);
    } catch (e) {
      print('Frame processing error: $e');
      return imageBytes; // Return original if processing fails
    }
  }
  
  static bool shouldProcessFrame() {
    // Implement frame rate limiting logic
    static DateTime? lastProcessTime;
    final now = DateTime.now();
    
    if (lastProcessTime == null) {
      lastProcessTime = now;
      return true;
    }
    
    final timeDiff = now.difference(lastProcessTime!).inMilliseconds;
    if (timeDiff >= 300) { // 300ms = ~3 FPS
      lastProcessTime = now;
      return true;
    }
    
    return false;
  }
}
```

## Error Handling & Debugging

### Production Error Management

```dart
// utils/error_handler.dart
class BridgeErrorHandler {
  static void handleApiError(Object error, StackTrace stackTrace) {
    if (error is BridgeApiException) {
      print('Bridge API Error: ${error.message}');
      // Log to crash reporting service in production
    } else {
      print('Unexpected error: $error');
      print('Stack trace: $stackTrace');
    }
  }
  
  static void handleCameraError(Object error) {
    print('Camera error: $error');
    // Implement camera recovery logic
  }
  
  static void handleWebSocketError(Object error) {
    print('WebSocket error: $error');
    // Implement reconnection logic
  }
}
```

### Debug Logging

```dart
// utils/debug_logger.dart
import 'package:flutter/foundation.dart';

class BridgeLogger {
  static void logDetection({
    required String letter,
    required double confidence,
    required int latencyMs,
  }) {
    if (kDebugMode) {
      print('[Detection] Letter: $letter | Confidence: ${confidence.toStringAsFixed(2)} | Latency: ${latencyMs}ms');
    }
  }
  
  static void logWebSocketEvent(String event, {Map<String, dynamic>? data}) {
    if (kDebugMode) {
      print('[WebSocket] $event ${data != null ? '| Data: $data' : ''}');
    }
  }
  
  static void logPerformance(String operation, int durationMs) {
    if (kDebugMode) {
      print('[Performance] $operation: ${durationMs}ms');
    }
  }
}
```

## Testing & Validation

### Integration Testing

```dart
// test/bridge_integration_test.dart
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Bridge API Integration Tests', () {
    test('should initialize session successfully', () async {
      final apiService = BridgeApiService();
      final response = await apiService.initializeSession();
      
      expect(response.sessionId, isNotEmpty);
      expect(response.modulesInitialized, isNotEmpty);
    });
    
    test('should handle detection requests', () async {
      final apiService = BridgeApiService();
      await apiService.initializeSession();
      
      // Test with dummy base64 image
      const dummyFrame = 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD...';
      final response = await apiService.detectFromFrame(dummyFrame);
      
      expect(response.status, equals('success'));
    });
    
    test('should check API health', () async {
      final apiService = BridgeApiService();
      final isHealthy = await apiService.checkHealth();
      
      expect(isHealthy, isTrue);
    });
  });
}
```

## Production Deployment

### Environment Configuration

```dart
// config/app_config.dart
class AppConfig {
  static const bool isProduction = bool.fromEnvironment('PRODUCTION', defaultValue: false);
  
  // API Configuration
  static String get bridgeApiUrl {
    return isProduction 
        ? BridgeApiConfig.PROD_BASE_URL 
        : BridgeApiConfig.DEV_BASE_URL;
  }
  
  // Feature Flags
  static const bool enableAnalytics = true;
  static const bool enableCrashReporting = true;
  static const bool enableDebugLogging = !isProduction;
  
## Troubleshooting

### Common Issues & Solutions

#### Connection Problems

**Issue**: WebSocket connection fails
```
Solution: Verify network connectivity and API health
```

```dart
// Check API health before connecting
final apiService = BridgeApiService();
if (await apiService.checkHealth()) {
  // Proceed with WebSocket connection
  await webSocketManager.connect();
} else {
  // Show error to user
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text('Bridge API is not available. Please try again later.'))
  );
}
```

**Issue**: Session initialization fails
```
Solution: Check API configuration and network status
```

```dart
try {
  final session = await apiService.initializeSession();
  print('Session initialized: ${session.sessionId}');
} on BridgeApiException catch (e) {
  print('Session error: ${e.message}');
  // Implement retry logic or show user-friendly error
}
```

#### Performance Issues

**Issue**: High CPU usage during detection
```
Solution: Implement frame rate limiting
```

```dart
// Limit detection to 3 FPS
if (FrameProcessor.shouldProcessFrame()) {
  final processedFrame = FrameProcessor.processFrame(imageBytes);
  await detectionService.detectFromFrame(base64Encode(processedFrame));
}
```

**Issue**: App crashes on camera switching
```
Solution: Properly dispose resources
```

```dart
@override
void dispose() {
  cameraController?.dispose();
  detectionService.dispose();
  webSocketManager.disconnect();
  audioPlayer.dispose();
  super.dispose();
}
```

#### Audio & TTS Issues

**Issue**: TTS audio not playing
```
Solution: Check audio permissions and format
```

```dart
Future<void> playTTS(String base64Audio) async {
  try {
    final audioBytes = base64Decode(base64Audio);
    final tempFile = await _createTempAudioFile(audioBytes);
    await audioPlayer.setFilePath(tempFile.path);
    await audioPlayer.play();
  } catch (e) {
    print('Audio playback error: $e');
    // Fallback: Show text instead of playing audio
  }
}
```

### Performance Optimization Tips

1. **Frame Processing**: Resize images to 480x320 before sending to API
2. **Detection Rate**: Limit to 3-5 FPS for optimal performance
3. **Memory Management**: Dispose controllers and streams properly
4. **Network Efficiency**: Use WebSocket for real-time updates instead of polling
5. **UI Responsiveness**: Use `FutureBuilder` and `StreamBuilder` for async operations

### Debug Mode Features

```dart
// Enable debug logging for development
class DebugConfig {
  static const bool enableApiLogging = true;
  static const bool enablePerformanceMetrics = true;
  static const bool enableFrameVisualization = true;
  
  static void logDetectionMetrics(DetectionResponse response, int latencyMs) {
    if (enablePerformanceMetrics) {
      print('Detection: ${response.letterDetected} | Confidence: ${response.confidence} | Latency: ${latencyMs}ms');
    }
  }
}
```

## Production Checklist

### Pre-deployment Validation

- [ ] **API Configuration**: Verify production URL is correct
- [ ] **Permissions**: Camera and microphone permissions are properly handled
- [ ] **Error Handling**: All API calls have proper try-catch blocks
- [ ] **Performance**: Frame processing is optimized (480x320, 65% JPEG quality)
- [ ] **Resource Management**: All controllers and streams are disposed
- [ ] **Network Handling**: Offline scenarios are handled gracefully
- [ ] **User Feedback**: Loading states and error messages are implemented

### Security Considerations

- [ ] **SSL/HTTPS**: Production API uses HTTPS endpoints
- [ ] **Token Management**: Client tokens are generated securely
- [ ] **Data Privacy**: Camera frames are processed locally when possible
- [ ] **Permission Requests**: Clear explanations for camera/microphone access

### Testing Requirements

- [ ] **Unit Tests**: API service methods are tested
- [ ] **Integration Tests**: Complete detection flow is validated
- [ ] **Performance Tests**: Frame processing latency is measured
- [ ] **Error Scenarios**: Network failures and API errors are tested

## API Reference Summary

### Core Endpoints

| Endpoint | Method | Purpose | Required |
|----------|---------|---------|----------|
| `/session/init` | POST | Initialize detection session | ✅ |
| `/detection/continuous-detect` | POST | Send frame for LSP detection | ✅ |
| `/phrase/finalize` | POST | Finalize and translate phrase | Optional |
| `/health` | GET | Check API status | Health checks |

### WebSocket Events

| Event Type | Direction | Description |
|------------|-----------|-------------|
| `detection_update` | Server → Client | Real-time detection state |
| `letter_added` | Server → Client | New letter detected |
| `word_updated` | Server → Client | Word buffer changed |
| `phrase_completed` | Server → Client | Phrase finalization |
| `frame` | Client → Server | Send camera frame |
| `ping`/`pong` | Bidirectional | Connection keepalive |

## Support & Resources

### Official Documentation
- Bridge LSP API Documentation: Available at your API base URL + `/docs`
- Flutter Camera Package: [pub.dev/packages/camera](https://pub.dev/packages/camera)
- WebSocket Channel: [pub.dev/packages/web_socket_channel](https://pub.dev/packages/web_socket_channel)

### Community & Help
- For API issues: Check server logs and `/health` endpoint
- For Flutter issues: Consult Flutter documentation and community forums
- For performance issues: Monitor frame processing times and network latency

---

**Bridge LSP API Flutter Integration Guide**  
*Complete implementation for real-time Peruvian Sign Language detection with automatic translation and text-to-speech.*

Last updated: December 2024  
API Version: Compatible with all current Bridge API deployments
```

### 2. Incremental State Management (v3.0)

```dart
class DetectionState {
  String? letterDetected;
  double? confidence;
  String wordBuffer = '';
  String predictedWord = '';
  String sentence = '';
  bool wordTimerActive = false;
  bool phraseTimerActive = false;
  
  // Track what changed for UI optimization
  Set<String> changedFields = {};
  
  void updateFromResponse(Map<String, dynamic> response) {
    if (response['status'] != 'success') return;
    
    // Get list of changed fields
    final changed = List<String>.from(response['changed'] ?? []);
    changedFields = Set<String>.from(changed);
    
    // Update only changed fields
    if (changed.contains('letter_detected')) {
      letterDetected = response['letter_detected'];
    }
    if (changed.contains('confidence')) {
      confidence = response['confidence']?.toDouble();
    }
    if (changed.contains('word_buffer')) {
      wordBuffer = response['word_buffer'] ?? '';
    }
    if (changed.contains('predicted_word')) {
      predictedWord = response['predicted_word'] ?? '';
    }
    if (changed.contains('sentence')) {
      sentence = response['sentence'] ?? '';
    }
    if (changed.contains('word_timer_active')) {
      wordTimerActive = response['word_timer_active'] ?? false;
    }
    if (changed.contains('phrase_timer_active')) {
      phraseTimerActive = response['phrase_timer_active'] ?? false;
    }
  }
  
  // UI optimization: only rebuild widgets for changed data
  bool shouldUpdateLetterUI() => changedFields.contains('letter_detected');
  bool shouldUpdateWordUI() => changedFields.contains('word_buffer') || 
                               changedFields.contains('predicted_word');
  bool shouldUpdateSentenceUI() => changedFields.contains('sentence');
  bool shouldUpdateTimerUI() => changedFields.contains('word_timer_active') || 
                                changedFields.contains('phrase_timer_active');
}
```

### 3. Enhanced WebSocket with Heartbeat (v3.0)

```dart
class WebSocketManager {
  IOWebSocketChannel? _channel;
  Timer? _heartbeatTimer;
  bool _isConnected = false;
  final String sessionId;
  final String clientId;
  
  WebSocketManager({required this.sessionId, required this.clientId});
  
  Future<void> connect() async {
    try {
      _channel = IOWebSocketChannel.connect(
        '$wsUrl/realtime/ws/detection/$clientId'
      );
      
      _isConnected = true;
      _startHeartbeatMonitoring();
      
      // Listen for messages including ping/pong
      _channel!.stream.listen(
        (data) => _handleMessage(jsonDecode(data)),
        onError: _handleError,
        onDone: _handleDisconnect,
      );
      
    } catch (e) {
      print('WebSocket connection failed: $e');
      _isConnected = false;
    }
  }
  
  void _startHeartbeatMonitoring() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(Duration(seconds: 1), (timer) {
      // Heartbeat is handled automatically by server
      // Just monitor connection health
      if (!_isConnected) {
        timer.cancel();
      }
    });
  }
  
  void _handleMessage(Map<String, dynamic> message) {
    switch (message['type']) {
      case 'ping':
        // Respond to server ping
        _sendPong();
        break;
      case 'letter_added':
        _onLetterDetected(message);
        break;
      case 'word_updated':
        _onWordUpdated(message);
        break;
      case 'phrase_updated':
        _onPhraseCompleted(message);
        break;
      case 'error':
        print('WebSocket error: ${message['message']}');
        break;
    }
  }
  
  void _sendPong() {
    if (_isConnected && _channel != null) {
      _channel!.sink.add(jsonEncode({'type': 'pong'}));
    }
  }
  
  void sendFrame(String base64Image) {
    if (_isConnected && _channel != null) {
      _channel!.sink.add(jsonEncode({
        'type': 'frame',
        'data': base64Image
      }));
    }
  }
  
  void _handleDisconnect() {
    _isConnected = false;
    _heartbeatTimer?.cancel();
    // Implement reconnection logic
    Future.delayed(Duration(seconds: 2), () => connect());
  }
}
```

### 4. Optimized Detection with Incremental Updates (v3.0)

```dart
class ContinuousDetectionService {
  final BridgeApiService apiService;
  final DetectionState state = DetectionState();
  Timer? _detectionTimer;
  
  ContinuousDetectionService(this.apiService);
  
  void startContinuousDetection(Stream<String> frameStream) {
    frameStream.listen((base64Frame) {
      _performDetection(base64Frame);
    });
  }
  
  Future<void> _performDetection(String base64Frame) async {
    try {
      final response = await apiService.dio.post(
        '${BridgeApiService.baseUrl}/detection/continuous-detect',
        data: {
          'session_id': apiService.currentSessionId,
          'frameBase64': base64Frame,
          'enable_timers': true,
          'confidence_threshold': 0.70,
        },
        options: Options(
          headers: {
            'X-Client-Token': apiService.clientToken,
          }
        )
      );
      
      // Update state with only changed fields
      state.updateFromResponse(response.data);
      
      // Trigger UI updates only for changed components
      _notifyUIChanges();
      
    } catch (e) {
      print('Detection error: $e');
    }
  }
  
  void _notifyUIChanges() {
    // Optimize UI updates based on what actually changed
    if (state.shouldUpdateLetterUI()) {
      _letterStreamController.add(state.letterDetected);
    }
    if (state.shouldUpdateWordUI()) {
      _wordStreamController.add(state.wordBuffer);
    }
    if (state.shouldUpdateSentenceUI()) {
      _sentenceStreamController.add(state.sentence);
    }
    if (state.shouldUpdateTimerUI()) {
      _timerStreamController.add({
        'word': state.wordTimerActive,
        'phrase': state.phraseTimerActive,
      });
    }
  }
}
```

### 5. Unified Phrase Finalization (v3.0)

```dart
class PhraseFinalizationService {
  final BridgeApiService apiService;
  
  PhraseFinalizationService(this.apiService);
  
  Future<PhraseResult> finalizePhrase({
    bool autoTranslate = false,
    String targetLanguage = 'en',
    bool ttsEnabled = true,
    String voiceLanguage = 'es',
  }) async {
    try {
      final response = await apiService.dio.post(
        '${BridgeApiService.baseUrl}/phrase/finalize',
        data: {
          'session_id': apiService.currentSessionId,
          'auto_translate': autoTranslate,
          'target_language': targetLanguage,
          'tts_enabled': ttsEnabled,
          'voice_language': voiceLanguage,
        },
        options: Options(
          headers: {
            'X-Client-Token': apiService.clientToken,
          }
        )
      );
      
      if (response.data['status'] == 'success') {
        return PhraseResult.fromJson(response.data);
      } else {
        throw ApiException(response.data['detail']);
      }
      
    } catch (e) {
      throw ApiException('Phrase finalization failed: $e');
    }
  }
  
  // Quick completion without translation/TTS for faster UI updates
  Future<String> quickCompletePhrase() async {
    try {
      final response = await apiService.dio.post(
        '${BridgeApiService.baseUrl}/phrase/quick-complete',
        data: {
          'session_id': apiService.currentSessionId,
        }
      );
      
      if (response.data['status'] == 'success') {
        return response.data['data']['phrase_finalized'];
      } else {
        throw ApiException(response.data['detail']);
      }
    } catch (e) {
      throw ApiException('Quick completion failed: $e');
    }
  }
}

class PhraseResult {
  final String phraseFinalized;
  final String? translated;
  final String? ttsAudio;
  final int processingTimeMs;
  
  PhraseResult({
    required this.phraseFinalized,
    this.translated,
    this.ttsAudio,
    required this.processingTimeMs,
  });
  
  factory PhraseResult.fromJson(Map<String, dynamic> json) => PhraseResult(
    phraseFinalized: json['phrase_finalized'],
    translated: json['translated'],
    ttsAudio: json['tts_audio'],
    processingTimeMs: json['processing_time_ms'],
  );
  
  // Helper methods
  bool hasTranslation() => translated != null && translated!.isNotEmpty;
  bool hasAudio() => ttsAudio != null && ttsAudio!.isNotEmpty;
  
  // Convert base64 audio to bytes for playback
  Uint8List? getAudioBytes() {
    if (ttsAudio == null) return null;
    return base64Decode(ttsAudio!);
  }
}
```

### 6. Error Handling with Standardized Responses (v3.0)

All endpoints now follow consistent response patterns for unified error handling:

```dart
class ApiResponse<T> {
  final String status;
  final T? data;
  final String? error;
  
  ApiResponse({required this.status, this.data, this.error});
  
  factory ApiResponse.fromJson(Map<String, dynamic> json, T Function(Map<String, dynamic>)? fromJson) {
    return ApiResponse(
      status: json['status'],
      data: json['status'] == 'success' && json['data'] != null && fromJson != null 
            ? fromJson(json['data']) 
            : json['data'],
      error: json['detail'],
    );
  }
  
  bool get isSuccess => status == 'success';
  bool get isError => status == 'error';
}

// Unified error handling wrapper
Future<ApiResponse<T>> safeApiCall<T>(
  Future<Response> Function() apiCall,
  T Function(Map<String, dynamic>)? fromJson,
) async {
  try {
    final response = await apiCall();
    return ApiResponse.fromJson(response.data, fromJson);
  } catch (e) {
    return ApiResponse(
      status: 'error',
      error: e.toString(),
    );
  }
}

// Usage examples
Future<void> demonstrateErrorHandling() async {
  // Session initialization
  final sessionResult = await safeApiCall(
    () => dio.post('/session/init'),
    (json) => SessionResponse.fromJson(json),
  );
  
  if (sessionResult.isSuccess) {
    print('Session created: ${sessionResult.data!.sessionId}');
  } else {
    print('Session error: ${sessionResult.error}');
  }
  
  // Phrase finalization
  final phraseResult = await safeApiCall(
    () => dio.post('/phrase/finalize', data: {...}),
    (json) => PhraseResult.fromJson(json),
  );
  
  if (phraseResult.isSuccess && phraseResult.data!.hasTranslation()) {
    showTranslation(phraseResult.data!.translated!);
  }
}
```

### 7. Performance Monitoring and Analytics (v3.0)

```dart
class PerformanceMonitor {
  final List<DetectionMetrics> _metrics = [];
  final String clientToken;
  
  PerformanceMonitor(this.clientToken);
  
  void recordDetection({
    required int latencyMs,
    required double confidence,
    required String letter,
    required bool changedFields,
  }) {
    _metrics.add(DetectionMetrics(
      timestamp: DateTime.now(),
      latencyMs: latencyMs,
      confidence: confidence,
      letter: letter,
      changedFields: changedFields,
    ));
    
    // Keep only last 100 metrics
    if (_metrics.length > 100) {
      _metrics.removeAt(0);
    }
  }
  
  // Analytics for debugging and optimization
  PerformanceStats getStats() {
    if (_metrics.isEmpty) {
      return PerformanceStats.empty();
    }
    
    final latencies = _metrics.map((m) => m.latencyMs).toList();
    final confidences = _metrics.map((m) => m.confidence).toList();
    final changeRates = _metrics.where((m) => m.changedFields).length / _metrics.length;
    
    return PerformanceStats(
      avgLatencyMs: latencies.reduce((a, b) => a + b) / latencies.length,
      maxLatencyMs: latencies.reduce(math.max),
      avgConfidence: confidences.reduce((a, b) => a + b) / confidences.length,
      changeRate: changeRates,
      totalDetections: _metrics.length,
    );
  }
}

class DetectionMetrics {
  final DateTime timestamp;
  final int latencyMs;
  final double confidence;
  final String letter;
  final bool changedFields;
  
  DetectionMetrics({
    required this.timestamp,
    required this.latencyMs,
    required this.confidence,
    required this.letter,
    required this.changedFields,
  });
}

class PerformanceStats {
  final double avgLatencyMs;
  final int maxLatencyMs;
  final double avgConfidence;
  final double changeRate;
  final int totalDetections;
  
  PerformanceStats({
    required this.avgLatencyMs,
    required this.maxLatencyMs,
    required this.avgConfidence,
    required this.changeRate,
    required this.totalDetections,
  });
  
  factory PerformanceStats.empty() => PerformanceStats(
    avgLatencyMs: 0,
    maxLatencyMs: 0,
    avgConfidence: 0,
    changeRate: 0,
    totalDetections: 0,
  );
  
  bool get isPerformingWell => avgLatencyMs < 100 && avgConfidence > 0.8;
}
```

---

## WebSocket & Heartbeat

Enhanced WebSocket connections include automatic health monitoring with ping/pong messages every 10 seconds and automatic connection cleanup on timeout. See the WebSocketManager class implementation in the Flutter Implementation section above.

---

## Phrase Finalization

The unified `/phrase/finalize` endpoint combines phrase completion, translation, and TTS in a single optimized call. Use the PhraseFinalizationService class for both full finalization with translation/TTS and quick completion for faster UI updates.

---

## Timer & Reset Controls

Bridge API v3.0 provides automatic timer management with manual override options:

```dart
class BridgeControlsWidget extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        // Force word completion
        ElevatedButton(
          onPressed: () => bridgeService.forceFinishWord(),
          child: Text('Finish Word'),
        ),
        
        // Force phrase completion
        ElevatedButton(
          onPressed: () => bridgeService.forceFinishPhrase(),
          child: Text('Finish Phrase'),
        ),
        
        // Complete reset
        ElevatedButton(
          onPressed: () => bridgeService.resetEverything(),
          child: Text('Reset'),
          style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
        ),
      ],
    );
  }
}
```

---

## Timer Configuration (Settings)

```dart
class TimerSettingsWidget extends StatefulWidget {
  @override
  _TimerSettingsWidgetState createState() => _TimerSettingsWidgetState();
}

class _TimerSettingsWidgetState extends State<TimerSettingsWidget> {
  double wordTimeout = 2.0;  // PAUSE_THRESHOLD from main.py
  double phraseTimeout = 5.0; // PHRASE_TIMEOUT from main.py
  
  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text('Timer Configuration'),
        
        // Word timeout slider
        Text('Auto-finish word: ${wordTimeout.toStringAsFixed(1)}s'),
        Slider(
          value: wordTimeout,
          min: 1.0,
          max: 5.0,
          divisions: 40,
          onChanged: (value) {
            setState(() {
              wordTimeout = value;
            });
            // Future improvement: dynamic backend timer configuration
          },
        ),
        
        // Phrase timeout slider  
        Text('Auto-finish phrase: ${phraseTimeout.toStringAsFixed(1)}s'),
        Slider(
          value: phraseTimeout,
          min: 3.0,
          max: 10.0,
          divisions: 70,
          onChanged: (value) {
            setState(() {
              phraseTimeout = value;
            });
            // Future improvement: dynamic backend timer configuration
          },
        ),
      ],
    );
  }
}
```

---

## Debugging & Troubleshooting

### Enable Debug Logging (Server)
Set environment variable for detailed performance logs:
```bash
# Enable detailed logging
export LOG_LEVEL=DEBUG

# Start server
python -m uvicorn api.api_main:app --reload --host 0.0.0.0 --port 8000
```

**Debug Log Examples:**
```
[Detect] Frame 1523 | latency=68ms | confidence=0.94 | letter=H
[Phrase] Auto-finished in 5.2s | phrase="HOLA AMIGO" | processing=45ms
[WS] ping sent to flutter_client_001
[WS] pong received from flutter_client_001
[WS] client flutter_client_001 inactive >20s — closing connection
```

### Client-Side Debug Information
```dart
class DebugInfo {
  static void logDetectionCycle({
    required int frameId,
    required int latencyMs,
    required List<String> changedFields,
    required double confidence,
  }) {
    if (kDebugMode) {
      print('[Flutter] Frame $frameId | '
            'latency=${latencyMs}ms | '
            'changed=${changedFields.join(",")} | '
            'conf=${confidence.toStringAsFixed(2)}');
    }
  }
  
  static void logWebSocketEvent(String event, {String? details}) {
    if (kDebugMode) {
      print('[Flutter/WS] $event${details != null ? " | $details" : ""}');
    }
  }
  
  static void logPerformanceStats(PerformanceStats stats) {
    if (kDebugMode) {
      print('[Flutter/Perf] '
            'avg_latency=${stats.avgLatencyMs.toStringAsFixed(1)}ms | '
            'max_latency=${stats.maxLatencyMs}ms | '
            'avg_conf=${stats.avgConfidence.toStringAsFixed(2)} | '
            'change_rate=${(stats.changeRate * 100).toStringAsFixed(1)}%');
    }
  }
}
```

---

## Performance Targets

**Bridge API v3.0 Performance Goals:**
- **Detection Latency:** < 50ms average
- **WebSocket Heartbeat:** 10s intervals, 20s timeout
- **State Update Efficiency:** Only changed fields transmitted
- **Session Init Time:** < 200ms for full setup
- **Phrase Finalization:** < 500ms with translation + TTS

**Recommended Flutter Settings:**
- **Frame Rate:** 30 FPS for camera input
- **Detection Frequency:** 200ms intervals (5 FPS)
- **UI Update Strategy:** Selective rebuilds based on `changed` fields
- **Memory Management:** Cleanup old detection metrics (keep last 100)

---

## Useful Resources

- **API Documentation:** http://localhost:8000/docs
- **WebSocket Test:** http://localhost:8000/realtime/ws/echo
- **Health Check:** http://localhost:8000/health
- **Performance Status:** http://localhost:8000/realtime/ws/status

---

## Legacy Endpoints (Deprecated)

These endpoints remain only for backward compatibility with Bridge v2.0:

### Legacy Session Creation
```
POST /autocorrector/session/create      # Use /session/init instead
POST /realtime/session/create           # Use /session/init instead
```

### Legacy Translation & TTS
```
POST /translate                         # Use /phrase/finalize with auto_translate=true
POST /tts/generate-speech               # Use /phrase/finalize with tts_enabled=true
POST /tts/generate-audio                # Use /phrase/finalize with tts_enabled=true
POST /text_to_speech                    # Use /phrase/finalize with tts_enabled=true
POST /phrase/complete-phrase            # Use /phrase/finalize instead
```

### Legacy Migration Examples

**Old Session Initialization (v2.0):**
```dart
// Required 2 separate calls
await http.post('$BASE_URL/autocorrector/session/create');
await http.post('$BASE_URL/realtime/session/create');
```

**Old Phrase Processing (v2.0):**
```dart
// Required 3 sequential calls
final phrase = await finishPhrase();
final translation = await translateText(phrase);
final audio = await generateTTS(translation);
```

**These patterns should not be used in new implementations. Use the unified v3.0 endpoints instead.**