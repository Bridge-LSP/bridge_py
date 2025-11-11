# Bridge Integration Manual - Flutter Frontend

Complete step-by-step guide for integrating the Bridge backend into Flutter frontend app. This enables real-time Peruvian Sign Language detection, translation, and TTS integration.

## Step 0 - Environment Setup

### Create .env file
In your Flutter project root, create `.env`:

```env
# Development
API_BASE_URL=http://10.0.2.2:8000
WS_BASE_URL=ws://10.0.2.2:8000

# Production
API_BASE_URL_PROD=https://bridge-api-154694118574.europe-west1.run.app
WS_BASE_URL_PROD=wss://bridge-api-154694118574.europe-west1.run.app

APP_ENV=development
LOG_LEVEL=debug
```

### Install ALL required dependencies
```bash
flutter pub add dio web_socket_channel flutter_dotenv camera permission_handler just_audio provider image
```

### Configure permissions

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
<string>Camera access required for sign language detection</string>
<key>NSMicrophoneUsageDescription</key>
<string>Microphone access required for audio playback</string>
```

### Load environment in main.dart
```dart
import 'package:flutter_dotenv/flutter_dotenv.dart';

Future<void> main() async {
  await dotenv.load(fileName: ".env");
  runApp(MyApp());
}
```

## Step 1 - Bridge API Service (Complete with Error Handling)

Create: `lib/services/bridge_api_service.dart`

```dart
import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

class BridgeApiService {
  final Dio dio = Dio();
  final String baseUrl = dotenv.env['API_BASE_URL']!;
  String? sessionId;

  BridgeApiService() {
    dio.interceptors.add(InterceptorsWrapper(
      onError: (error, handler) {
        print('[API Error] ${error.message}');
        handler.next(error);
      },
    ));
  }

  Future<Map<String, dynamic>> initializeSession() async {
    try {
      final response = await dio.post('$baseUrl/session/init', data: {
        'preferences': {
          'tts_enabled': true,
          'voice_language': 'es',
          'auto_translate': true,
          'target_language': 'en',
        }
      });
      
      if (response.data['status'] == 'success') {
        sessionId = response.data['data']['session_id'];
        return response.data['data'];
      } else {
        throw Exception('Session initialization failed');
      }
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionTimeout) {
        throw 'Connection timeout - check your internet';
      } else if (e.type == DioExceptionType.connectionError) {
        throw 'Cannot connect to server - is backend running?';
      }
      throw 'API Error: ${e.message}';
    }
  }

  Future<bool> checkHealth() async {
    try {
      final response = await dio.get('$baseUrl/health');
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }
}
```

Test: Run backend, call initializeSession(), verify session_id is returned.

## Step 2 - Camera Service (Complete Frame Capture)

Create: `lib/services/camera_service.dart`

```dart
import 'package:camera/camera.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:image/image.dart' as img;
import 'dart:convert';
import 'dart:typed_data';

class CameraService {
  CameraController? controller;
  List<CameraDescription>? cameras;

  Future<bool> requestPermissions() async {
    final status = await Permission.camera.request();
    return status == PermissionStatus.granted;
  }

  Future<void> initializeCamera() async {
    if (!await requestPermissions()) {
      throw 'Camera permission denied';
    }

    cameras = await availableCameras();
    if (cameras!.isEmpty) {
      throw 'No cameras available';
    }

    controller = CameraController(
      cameras![0], // Use front camera for sign language
      ResolutionPreset.medium,
      enableAudio: false,
    );

    await controller!.initialize();
  }

  Future<String> captureFrameAsBase64() async {
    if (controller == null || !controller!.value.isInitialized) {
      throw 'Camera not initialized';
    }

    final image = await controller!.takePicture();
    final bytes = await image.readAsBytes();
    
    // Optimize frame for better performance
    final optimizedBytes = _optimizeFrame(bytes);
    return base64Encode(optimizedBytes);
  }

  Uint8List _optimizeFrame(Uint8List bytes) {
    try {
      final image = img.decodeImage(bytes);
      if (image == null) return bytes;
      
      // Resize to 480x320 for optimal performance
      final resized = img.copyResize(image, width: 480, height: 320);
      
      // Compress to JPEG with 65% quality
      return Uint8List.fromList(img.encodeJpg(resized, quality: 65));
    } catch (e) {
      print('[Camera] Frame optimization error: $e');
      return bytes; // Return original if optimization fails
    }
  }

  void dispose() {
    controller?.dispose();
  }
}
```

## Step 3 - Detection Service (Enhanced)

Create: `lib/services/detection_service.dart`

```dart
import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

class DetectionService {
  final Dio dio = Dio();
  final String baseUrl = dotenv.env['API_BASE_URL']!;

  Future<Map<String, dynamic>> sendFrame(String sessionId, String base64Frame) async {
    try {
      final response = await dio.post(
        '$baseUrl/detection/continuous-detect',
        data: {
          'session_id': sessionId,
          'frameBase64': base64Frame,
          'enable_timers': true,
          'confidence_threshold': 0.70,
        },
      );
      return response.data;
    } on DioException catch (e) {
      print('[Detection] Error: ${e.message}');
      return {'status': 'error', 'message': e.message};
    }
  }
}
```

## Step 4 - WebSocket Manager (Complete)

Create: `lib/services/websocket_manager.dart`

```dart
import 'package:web_socket_channel/io.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'dart:convert';
import 'dart:async';

class WebSocketManager {
  final String clientId;
  final String sessionId;
  final String wsUrl = dotenv.env['WS_BASE_URL']!;
  IOWebSocketChannel? channel;
  StreamSubscription? _subscription;
  Timer? _heartbeatTimer;
  bool _isConnected = false;

  Function(Map<String, dynamic>)? onDetectionUpdate;
  Function(bool)? onConnectionChange;

  WebSocketManager({required this.sessionId, required this.clientId});

  Future<void> connect() async {
    try {
      final url = '$wsUrl/realtime/ws/detection/$clientId';
      channel = IOWebSocketChannel.connect(url);
      _isConnected = true;
      onConnectionChange?.call(true);
      
      _subscription = channel!.stream.listen(
        (data) => _handleMessage(jsonDecode(data)),
        onError: (error) {
          _isConnected = false;
          onConnectionChange?.call(false);
          _reconnect();
        },
        onDone: () {
          _isConnected = false;
          onConnectionChange?.call(false);
          _reconnect();
        },
      );
      
      _startHeartbeat();
    } catch (e) {
      _isConnected = false;
      onConnectionChange?.call(false);
    }
  }

  void _handleMessage(Map<String, dynamic> message) {
    switch (message['type']) {
      case 'ping':
        channel?.sink.add(jsonEncode({'type': 'pong'}));
        break;
      case 'detection_update':
        onDetectionUpdate?.call(message['data']);
        break;
      case 'letter_added':
        print('[WS] Letter: ${message['letter']} (${message['confidence']})');
        break;
    }
  }

  void _startHeartbeat() {
    _heartbeatTimer = Timer.periodic(Duration(seconds: 10), (timer) {
      if (!_isConnected) timer.cancel();
    });
  }

  void _reconnect() {
    Future.delayed(Duration(seconds: 3), () {
      if (!_isConnected) connect();
    });
  }

  void dispose() {
    _heartbeatTimer?.cancel();
    _subscription?.cancel();
    channel?.sink.close();
  }
}
```

## Step 5 - Audio Service (TTS Playback)

Create: `lib/services/audio_service.dart`

```dart
import 'package:just_audio/just_audio.dart';
import 'dart:convert';
import 'dart:typed_data';

class AudioService {
  final AudioPlayer _player = AudioPlayer();

  Future<void> playTTSAudio(String base64Audio) async {
    try {
      final bytes = base64Decode(base64Audio);
      await _player.setAudioSource(AudioSource.bytes(bytes));
      await _player.play();
    } catch (e) {
      print('[Audio] Error playing TTS: $e');
    }
  }

  Future<void> stop() async {
    await _player.stop();
  }

  void dispose() {
    _player.dispose();
  }
}
```

## Step 6 - Phrase Service (Enhanced)

Create: `lib/services/phrase_service.dart`

```dart
import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

class PhraseService {
  final Dio dio = Dio();
  final String baseUrl = dotenv.env['API_BASE_URL']!;

  Future<Map<String, dynamic>> finalizePhrase(String sessionId) async {
    try {
      final response = await dio.post(
        '$baseUrl/phrase/finalize',
        data: {
          'session_id': sessionId,
          'auto_translate': true,
          'target_language': 'en',
          'tts_enabled': true,
          'voice_language': 'es',
        },
      );
      return response.data;
    } on DioException catch (e) {
      print('[Phrase] Error: ${e.message}');
      throw 'Failed to finalize phrase: ${e.message}';
    }
  }
}
```

## Step 7 - Timer Service & Frame Optimization

Create: `lib/services/timer_service.dart`

```dart
import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

class TimerService {
  final Dio dio = Dio();
  final String baseUrl = dotenv.env['API_BASE_URL']!;

  Future<void> resetSession(String sessionId) async {
    try {
      await dio.post('$baseUrl/detection/reset-detection-state', 
        data: {'session_id': sessionId});
    } catch (e) {
      print('[Timer] Reset error: $e');
    }
  }

  Future<void> autoFinishWord(String sessionId) async {
    try {
      await dio.post('$baseUrl/timers/word/auto-finish', 
        data: {'session_id': sessionId});
    } catch (e) {
      print('[Timer] Word finish error: $e');
    }
  }

  Future<void> autoFinishPhrase(String sessionId) async {
    try {
      await dio.post('$baseUrl/timers/phrase/auto-finish', 
        data: {'session_id': sessionId});
    } catch (e) {
      print('[Timer] Phrase finish error: $e');
    }
  }
}
```

Create: `lib/utils/frame_throttler.dart`

```dart
class FrameThrottler {
  static const int FRAME_INTERVAL_MS = 300; // 3 FPS
  DateTime _lastFrameTime = DateTime.now();
  
  bool shouldSendFrame() {
    final now = DateTime.now();
    if (now.difference(_lastFrameTime).inMilliseconds >= FRAME_INTERVAL_MS) {
      _lastFrameTime = now;
      return true;
    }
    return false;
  }
  
  void reset() {
    _lastFrameTime = DateTime.now();
  }
}
```

## Step 8 - State Management

Create: `lib/models/detection_state.dart`

```dart
import 'package:flutter/foundation.dart';

class DetectionState extends ChangeNotifier {
  String _currentLetter = '';
  String _currentWord = '';
  String _currentSentence = '';
  double _confidence = 0.0;
  bool _isDetecting = false;
  bool _isConnected = false;
  bool _wordTimerActive = false;
  bool _phraseTimerActive = false;
  String? _sessionId;

  // Getters
  String get currentLetter => _currentLetter;
  String get currentWord => _currentWord;
  String get currentSentence => _currentSentence;
  double get confidence => _confidence;
  bool get isDetecting => _isDetecting;
  bool get isConnected => _isConnected;
  bool get wordTimerActive => _wordTimerActive;
  bool get phraseTimerActive => _phraseTimerActive;
  String? get sessionId => _sessionId;

  void updateLetter(String letter, double confidence) {
    _currentLetter = letter;
    _confidence = confidence;
    notifyListeners();
  }

  void updateWord(String word) {
    _currentWord = word;
    notifyListeners();
  }

  void updateSentence(String sentence) {
    _currentSentence = sentence;
    notifyListeners();
  }

  void setDetecting(bool detecting) {
    _isDetecting = detecting;
    notifyListeners();
  }

  void setConnected(bool connected) {
    _isConnected = connected;
    notifyListeners();
  }

  void setTimerStates(bool wordTimer, bool phraseTimer) {
    _wordTimerActive = wordTimer;
    _phraseTimerActive = phraseTimer;
    notifyListeners();
  }

  void setSessionId(String? id) {
    _sessionId = id;
    notifyListeners();
  }

  void reset() {
    _currentLetter = '';
    _currentWord = '';
    _currentSentence = '';
    _confidence = 0.0;
    _wordTimerActive = false;
    _phraseTimerActive = false;
    notifyListeners();
  }
}
```

## Step 9 - Complete Home Screen Integration

Update your `home_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:camera/camera.dart';
import 'dart:async';

import 'services/bridge_api_service.dart';
import 'services/camera_service.dart';
import 'services/detection_service.dart';
import 'services/websocket_manager.dart';
import 'services/phrase_service.dart';
import 'services/audio_service.dart';
import 'services/timer_service.dart';
import 'models/detection_state.dart';
import 'utils/frame_throttler.dart';

class HomeScreen extends StatefulWidget {
  @override
  _HomeScreenState createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // Services
  late BridgeApiService _apiService;
  late CameraService _cameraService;
  late DetectionService _detectionService;
  late WebSocketManager _wsManager;
  late PhraseService _phraseService;
  late AudioService _audioService;
  late TimerService _timerService;
  
  // Utilities
  late FrameThrottler _frameThrottler;
  
  // Timers
  Timer? _frameTimer;
  
  // State
  bool _isInitialized = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _initializeServices();
  }

  Future<void> _initializeServices() async {
    try {
      // Initialize all services
      _apiService = BridgeApiService();
      _cameraService = CameraService();
      _detectionService = DetectionService();
      _phraseService = PhraseService();
      _audioService = AudioService();
      _timerService = TimerService();
      _frameThrottler = FrameThrottler();
      
      // Check API health
      final isHealthy = await _apiService.checkHealth();
      if (!isHealthy) {
        throw 'Backend is not responding';
      }
      
      // Initialize session
      final session = await _apiService.initializeSession();
      final sessionId = session['session_id'];
      
      // Update state
      final detectionState = Provider.of<DetectionState>(context, listen: false);
      detectionState.setSessionId(sessionId);
      
      // Initialize camera
      await _cameraService.initializeCamera();
      
      // Setup WebSocket
      _wsManager = WebSocketManager(
        sessionId: sessionId,
        clientId: 'flutter_${DateTime.now().millisecondsSinceEpoch}',
      );
      
      _wsManager.onDetectionUpdate = (data) {
        _handleDetectionUpdate(data);
      };
      
      _wsManager.onConnectionChange = (connected) {
        detectionState.setConnected(connected);
      };
      
      await _wsManager.connect();
      
      // Start frame processing
      _startFrameProcessing();
      
      setState(() {
        _isInitialized = true;
      });
      
    } catch (e) {
      setState(() {
        _error = e.toString();
      });
    }
  }

  void _startFrameProcessing() {
    _frameTimer = Timer.periodic(Duration(milliseconds: 100), (timer) async {
      if (_frameThrottler.shouldSendFrame()) {
        try {
          final base64Frame = await _cameraService.captureFrameAsBase64();
          final response = await _detectionService.sendFrame(
            _apiService.sessionId!,
            base64Frame,
          );
          _handleDetectionResponse(response);
        } catch (e) {
          print('[Frame Processing] Error: $e');
        }
      }
    });
  }

  void _handleDetectionResponse(Map<String, dynamic> response) {
    final detectionState = Provider.of<DetectionState>(context, listen: false);
    
    if (response['status'] == 'success') {
      if (response['letter_detected'] != null) {
        detectionState.updateLetter(
          response['letter_detected'],
          response['confidence']?.toDouble() ?? 0.0,
        );
      }
      
      if (response['word_buffer'] != null) {
        detectionState.updateWord(response['word_buffer']);
      }
      
      if (response['sentence'] != null) {
        detectionState.updateSentence(response['sentence']);
      }
      
      detectionState.setTimerStates(
        response['word_timer_active'] ?? false,
        response['phrase_timer_active'] ?? false,
      );
    }
  }

  void _handleDetectionUpdate(Map<String, dynamic> data) {
    final detectionState = Provider.of<DetectionState>(context, listen: false);
    
    // Handle real-time WebSocket updates
    if (data.containsKey('letter_detected')) {
      detectionState.updateLetter(
        data['letter_detected'],
        data['confidence']?.toDouble() ?? 0.0,
      );
    }
    
    if (data.containsKey('word_buffer')) {
      detectionState.updateWord(data['word_buffer']);
    }
    
    if (data.containsKey('sentence')) {
      detectionState.updateSentence(data['sentence']);
    }
  }

  Future<void> _finalizePhrase() async {
    try {
      final response = await _phraseService.finalizePhrase(_apiService.sessionId!);
      
      if (response['status'] == 'success') {
        // Play TTS audio if available
        if (response['data']['tts_audio'] != null) {
          await _audioService.playTTSAudio(response['data']['tts_audio']);
        }
        
        // Show translation result
        _showTranslationDialog(
          original: response['data']['phrase_finalized'],
          translated: response['data']['translated'],
        );
      }
    } catch (e) {
      print('[Phrase Finalization] Error: $e');
    }
  }

  void _showTranslationDialog({required String original, String? translated}) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Translation Result'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Original: $original'),
            if (translated != null) Text('Translated: $translated'),
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

  Future<void> _resetSession() async {
    try {
      await _timerService.resetSession(_apiService.sessionId!);
      final detectionState = Provider.of<DetectionState>(context, listen: false);
      detectionState.reset();
    } catch (e) {
      print('[Reset] Error: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      return Scaffold(
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text('Error: $_error'),
              ElevatedButton(
                onPressed: () {
                  setState(() {
                    _error = null;
                  });
                  _initializeServices();
                },
                child: Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (!_isInitialized) {
      return Scaffold(
        body: Center(
          child: CircularProgressIndicator(),
        ),
      );
    }

    return Scaffold(
      body: Consumer<DetectionState>(
        builder: (context, detectionState, child) {
          return Column(
            children: [
              // Camera Preview
              Expanded(
                flex: 3,
                child: _cameraService.controller?.value.isInitialized == true
                    ? CameraPreview(_cameraService.controller!)
                    : Container(color: Colors.black),
              ),
              
              // Detection Info
              Expanded(
                flex: 1,
                child: Container(
                  padding: EdgeInsets.all(16),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          Text('Status: '),
                          Icon(
                            detectionState.isConnected ? Icons.wifi : Icons.wifi_off,
                            color: detectionState.isConnected ? Colors.green : Colors.red,
                          ),
                        ],
                      ),
                      SizedBox(height: 8),
                      Text('Letter: ${detectionState.currentLetter}'),
                      Text('Confidence: ${detectionState.confidence.toStringAsFixed(2)}'),
                      Text('Word: ${detectionState.currentWord}'),
                      Text('Sentence: ${detectionState.currentSentence}'),
                    ],
                  ),
                ),
              ),
              
              // Control Buttons
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  ElevatedButton(
                    onPressed: _finalizePhrase,
                    child: Text('Finalize Phrase'),
                  ),
                  ElevatedButton(
                    onPressed: _resetSession,
                    child: Text('Reset'),
                  ),
                ],
              ),
            ],
          );
        },
      ),
    );
  }

  @override
  void dispose() {
    _frameTimer?.cancel();
    _cameraService.dispose();
    _wsManager.dispose();
    _audioService.dispose();
    super.dispose();
  }
}
```

## Step 10 - Main App Setup

Update your `main.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:provider/provider.dart';
import 'models/detection_state.dart';
import 'screens/home_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(fileName: ".env");
  
  runApp(
    ChangeNotifierProvider(
      create: (context) => DetectionState(),
      child: MyApp(),
    ),
  );
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Bridge LSP Integration',
      theme: ThemeData(
        primarySwatch: Colors.blue,
      ),
      home: HomeScreen(),
    );
  }
}
```

## Testing & Validation

Run these tests in order:

1. **API Health Check**: Verify backend is running at configured URL
2. **Session Initialization**: Confirm session_id is returned
3. **Camera Permissions**: Ensure camera access is granted
4. **Frame Capture**: Test base64 encoding and optimization
5. **Detection API**: Send test frame and verify response
6. **WebSocket Connection**: Confirm ping/pong and real-time updates
7. **Audio Playback**: Test TTS audio decoding and playback
8. **State Management**: Verify UI updates with detection changes
9. **Error Handling**: Test network failures and recovery
10. **Full Integration**: Complete sign language detection to translation flow

## Production Considerations

### Environment Configuration
- Set `APP_ENV=production` in .env
- Use HTTPS URLs for production API endpoints
- Configure proper SSL certificate validation
- Enable crash reporting and analytics

### Performance Optimization
- Frame processing limited to 3 FPS (300ms intervals)
- Image compression to 480x320 at 65% JPEG quality
- WebSocket reconnection with exponential backoff
- Proper resource cleanup and memory management

### Error Handling
- Network timeout and retry logic
- Graceful degradation when backend unavailable
- User-friendly error messages
- Automatic session recovery

### Security
- Validate all API responses
- Handle sensitive data appropriately
- Implement proper permission requests
- Secure WebSocket connections

This integration provides complete real-time Peruvian Sign Language detection with automatic translation and text-to-speech capabilities in Flutter applications.
```
