# Guía de Integración LSP en Tiempo Real - Bridge API

## Descripción General

Esta guía detalla cómo integrar los endpoints de Bridge para replicar completamente el flujo de traducción de Lengua de Señas Peruana (LSP) a texto y voz en tiempo real, implementando la misma lógica de detección, autocorrección con BERT y traducción que utiliza nuestro sistema de laboratorio.

## Flujo Completo del Sistema

### 1. **Inicialización de la Sesión**
   
#### Endpoint: `POST /session/init`
```http
POST /session/init
Content-Type: application/json
X-Client-Token: tu_token_unico

{
  "session_id": "optional_custom_id",
  "preferences": {
    "tts_enabled": true,
    "voice_language": "es",
    "auto_translate": false
  }
}
```

**Características importantes:**
- Inicializa todas las sesiones necesarias: autocorrector con BERT y detección en tiempo real
- Genera un `session_id` único si no se proporciona
- Configura preferencias del usuario para TTS y traducción automática
- **Tiempo de respuesta típico**: < 100ms

### 2. **Conexión WebSocket para Detección en Tiempo Real**

#### WebSocket: `ws://servidor:puerto/realtime/ws/detection/{session_id}`

**Protocolo de comunicación:**
```javascript
// Envío de frame (cada 200ms máximo)
websocket.send(frameBase64String);

// Respuesta del servidor
{
  "predictions": [
    {
      "letter": "a",
      "confidence": 0.87,
      "handedness": "left",
      "hand_index": 0
    }
  ],
  "timestamp": 1637567890.123,
  "processing_time_ms": 23.45
}
```

**Configuración crítica:**
- **Intervalo mínimo entre frames**: 200ms
- **Umbral de confianza**: 0.75 
- **Tiempo de cooldown entre detecciones**: 1.0 segundo
- **Máximo 1 frame en procesamiento simultáneo**

### 3. **Detección Continua con Gestión Automática de Timers**

#### Endpoint: `POST /detection/continuous-detect`
```http
POST /detection/continuous-detect
Content-Type: application/json
X-Client-Token: tu_token

{
  "session_id": "tu_session_id",
  "frameBase64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ...",
  "enable_timers": true,
  "confidence_threshold": 0.70
}
```

**Respuesta detallada:**
```json
{
  "status": "success",
  "changed": ["letter_detected", "word_buffer", "should_auto_finish_word"],
  "letter_detected": "H",
  "confidence": 0.89,
  "word_buffer": "hol",
  "predicted_word": "hola",
  "sentence": "buenos dias",
  "word_timer_active": true,
  "phrase_timer_active": true,
  "time_since_last_detection": 1.2,
  "should_auto_finish_word": false,
  "should_auto_finish_phrase": false
}
```

**Lógica de timers implementada:**
- **Pausa para finalizar palabra**: 2.0 segundos sin detección
- **Timeout para finalizar frase**: 5.0 segundos sin detección  
- **Sistema de cooldown**: 1.0 segundo entre detecciones de la misma letra

## Funcionamiento Actual del Sistema

### **a) Encendido de Cámara y Captura**
El usuario activa la cámara y el sistema comienza a capturar frames a 30 FPS. Los frames se procesan con MediaPipe para detección de landmarks de mano.

### **b) Detección de Señas y Predicción**
1. **Extracción de características**: Se extraen 63 características (x,y,z) × 21 landmarks
2. **Predicción con modelo Random Forest**: Confianza mínima de 75% 
3. **Cooldown entre detecciones**: 1 segundo para evitar detecciones duplicadas
4. **Algoritmo LSTM adicional**: Para letras complejas (j, ll, rr, z, ñ) con secuencias de 30 frames

### **c) Formación Iterativa de Palabras** 
```
Letra detectada → Buffer temporal → Pausa de 2s → Palabra finalizada
```

**Proceso detallado:**
- Cada letra se agrega al buffer temporal (`word_buffer`)
- El sistema muestra predicción en tiempo real usando BERT
- Tras 2 segundos sin nuevas detecciones, la palabra se finaliza automáticamente
- Se aplica corrección con modelo BERT español: `dccuchile/bert-base-spanish-wwm-uncased`

### **d) Autocorrección con BERT - Proceso Crítico**

El sistema utiliza un enfoque híbrido para autocorrección:

1. **Predicción contextual**: BERT analiza el contexto de la oración parcial
2. **Corrección basada en aprendizaje**: Sistema que aprende de correcciones previas
3. **Fallback a corrector ortográfico**: Para palabras no reconocidas por BERT

**Implementación específica:**
```python
# Contexto actual: "buenos dias [MASK]"
# Buffer detectado: "hol"  
# BERT sugiere: "hola" (probabilidad: 0.94)
# Resultado: "buenos dias hola"
```

### **e) Agrupación en Oraciones**
Las palabras corregidas se van acumulando en `sentence_words[]` hasta que:
- **Timeout de frase**: 5 segundos sin actividad
- **Finalización manual**: Usuario indica fin de oración
- **Detección de pausa larga**: Sistema interpreta silencio como fin de frase

### **f) Traducción y Text-to-Speech**

**Orden específico de procesamiento:**
1. **Finalización de frase** → `POST /phrase/finalize`
2. **Traducción automática** (si está habilitada) → DeepL API
3. **Generación de audio TTS** → Síntesis de voz 
4. **Reproducción automática** → Audio en idioma objetivo

## Integración Paso a Paso con WebSockets

### **Paso 1: Configuración Inicial**
```javascript
// 1. Crear sesión unificada
const sessionResponse = await fetch('/session/init', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Client-Token': 'token_unico_cliente'
  },
  body: JSON.stringify({
    preferences: {
      tts_enabled: true,
      voice_language: 'es',
      auto_translate: true,
      target_language: 'en'
    }
  })
});

const session = await sessionResponse.json();
const sessionId = session.session_id;
```

### **Paso 2: Conexión WebSocket**
```javascript
const ws = new WebSocket(`ws://localhost:8000/realtime/ws/detection/${sessionId}`);

ws.onopen = () => {
  console.log('Conexión WebSocket establecida');
  startCameraCapture();
};

ws.onmessage = (event) => {
  const prediction = JSON.parse(event.data);
  handlePrediction(prediction);
};
```

### **Paso 3: Captura y Envío de Frames**
```javascript
function captureAndSend() {
  // Capturar frame cada 200ms
  canvas.toBlob((blob) => {
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result.split(',')[1];
      ws.send(base64); // Envío directo por WebSocket
    };
    reader.readAsDataURL(blob);
  }, 'image/jpeg', 0.7);
}

// Timer para envío controlado
setInterval(captureAndSend, 200);
```

### **Paso 4: Procesamiento de Predicciones**
```javascript
function handlePrediction(prediction) {
  if (prediction.predictions && prediction.predictions.length > 0) {
    const letter = prediction.predictions[0].letter;
    const confidence = prediction.predictions[0].confidence;
    
    // Actualizar UI con letra detectada
    updateLetterDisplay(letter, confidence);
    
    // El autocorrector se maneja automáticamente en el backend
    // No necesitas hacer nada más aquí
  }
}
```

### **Paso 5: Monitoreo de Estado de Sesión**
```javascript
// Monitorear estado cada 500ms
setInterval(async () => {
  const status = await fetch(`/detection/session-timeline/${sessionId}`);
  const data = await status.json();
  
  updateWordBuffer(data.data.session_state.current_buffer);
  updatePredictedWord(data.data.session_state.predicted_word);
  updateSentence(data.data.session_state.sentence);
  
  // Auto-finalización de palabras
  if (data.data.auto_finish_checks.should_auto_finish_word) {
    console.log('Auto-finalizando palabra por timeout');
  }
  
  // Auto-finalización de frases
  if (data.data.auto_finish_checks.should_auto_finish_phrase) {
    console.log('Auto-finalizando frase por timeout');
    await finalizePhraseAutomatically();
  }
}, 500);
```

### **Paso 6: Finalización y Traducción**
```javascript
async function finalizePhraseAutomatically() {
  const response = await fetch('/phrase/finalize', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Client-Token': 'token_unico_cliente'
    },
    body: JSON.stringify({
      session_id: sessionId,
      auto_translate: true,
      target_language: 'en',
      tts_enabled: true,
      voice_language: 'en'
    })
  });
  
  const result = await response.json();
  
  // Mostrar frase finalizada
  displayCompletedPhrase(result.phrase_finalized);
  
  // Mostrar traducción si está disponible
  if (result.translated) {
    displayTranslation(result.translated);
  }
  
  // Reproducir audio TTS si está disponible
  if (result.tts_audio) {
    playTTSAudio(result.tts_audio);
  }
}

function playTTSAudio(base64Audio) {
  const audioBlob = base64ToBlob(base64Audio, 'audio/mpeg');
  const audioUrl = URL.createObjectURL(audioBlob);
  const audio = new Audio(audioUrl);
  audio.play();
}
```

## Configuración de Timers y Umbrales

### **Parámetros Críticos del Sistema:**
```javascript
const CONFIG = {
  // Detección
  CONFIDENCE_THRESHOLD: 0.70,    // Confianza mínima para aceptar predicción
  FRAME_INTERVAL_MS: 200,        // Intervalo mínimo entre frames
  COOLDOWN_TIME: 1000,           // Cooldown entre letras iguales (ms)
  
  // Timers automáticos
  PAUSE_THRESHOLD: 2000,         // Auto-finalizar palabra (ms)
  PHRASE_TIMEOUT: 5000,          // Auto-finalizar frase (ms)
  
  // WebSocket
  MAX_MESSAGE_BYTES: 10485760,   // Tamaño máximo de mensaje (10MB)
  PING_INTERVAL: 25000,          // Heartbeat cada 25s
  
  // Rendimiento
  MAX_INFLIGHT_FRAMES: 1,        // Máximo frames en procesamiento
  PROCESSING_TARGET_MS: 50       // Target de latencia de procesamiento
};
```

## Manejo de Errores y Recuperación

### **Reconexión Automática del WebSocket**
```javascript
function setupWebSocketWithReconnection() {
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;
  
  function connect() {
    const ws = new WebSocket(`ws://localhost:8000/realtime/ws/detection/${sessionId}`);
    
    ws.onopen = () => {
      reconnectAttempts = 0;
      console.log('WebSocket conectado');
    };
    
    ws.onerror = (error) => {
      console.error('Error WebSocket:', error);
    };
    
    ws.onclose = () => {
      if (reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        setTimeout(connect, 2000 * reconnectAttempts);
      }
    };
    
    return ws;
  }
  
  return connect();
}
```

### **Validación de Estado de Sesión**
```javascript
async function validateSession() {
  try {
    const response = await fetch(`/session/status/${sessionId}`);
    const status = await response.json();
    
    if (!status.data.session_exists) {
      console.log('Sesión expirada, recreando...');
      await recreateSession();
    }
    
    return status.data.session_exists;
  } catch (error) {
    console.error('Error validando sesión:', error);
    return false;
  }
}
```

## Endpoints de Soporte Adicionales

### **Gestión de Palabras en Tiempo Real**
- `POST /word-builder/add-letter` - Agregar letra manualmente
- `POST /word-builder/finish-word` - Finalizar palabra actual
- `POST /word-builder/remove-last` - Remover última letra

### **Corrección Manual con BERT**
- `POST /bert/correct-word` - Corrección manual de palabra
- `POST /bert/suggest-completions` - Sugerencias de autocompletado
- `GET /bert/context-analysis` - Análisis de contexto actual

### **Gestión de Frases**
- `POST /phrase/quick-complete` - Finalización rápida sin TTS/traducción
- `POST /phrase/reset` - Reiniciar frase actual
- `GET /phrase/preview` - Vista previa de frase antes de finalizar

### **Text-to-Speech Avanzado**
- `POST /tts/enhanced-generate` - TTS con control de velocidad/tono
- `POST /tts/stream` - TTS en streaming para frases largas
- `GET /tts/voices` - Lista de voces disponibles por idioma

### **Traducción Avanzada**
- `POST /translation/batch` - Traducción de múltiples frases
- `GET /translation/languages` - Idiomas soportados
- `POST /translation/context-aware` - Traducción con contexto histórico

## Optimizaciones de Rendimiento

### **Gestión de Memoria**
- Las sesiones se limpian automáticamente tras 30 minutos de inactividad
- Buffer de frames limitado a 1 frame simultáneo para evitar lag
- Cache de estados de sesión con TTL de 30 segundos

### **Latencia de Red**
- Compresión de imágenes JPEG al 70% para reducir tamaño
- Headers de rendimiento en todas las respuestas HTTP
- Logging detallado de tiempos de procesamiento

### **Escalabilidad**
- Soporte para múltiples sesiones concurrentes
- Balanceo de carga automático entre modelos
- Métricas de rendimiento en tiempo real

## Consideraciones Importantes

1. **Orden de operaciones**: Respetar el flujo detección → autocorrección → formación de palabras → finalización → traducción → TTS
2. **Gestión de estado**: Mantener coherencia entre WebSocket y API REST
3. **Timeouts**: Configurar timeouts apropiados para evitar sesiones colgadas
4. **Calidad de audio**: Usar cámaras con buena resolución para mejor detección
5. **Conectividad**: Implementar reconexión automática para WebSockets
6. **Feedback del usuario**: Permitir corrección manual cuando el sistema falle
7. **Logging**: Mantener logs detallados para debugging y optimización

## Ejemplo de Integración Completa

```javascript
class BridgeLSPIntegration {
  constructor() {
    this.sessionId = null;
    this.websocket = null;
    this.isCapturing = false;
  }
  
  async initialize() {
    // 1. Crear sesión
    await this.createSession();
    
    // 2. Conectar WebSocket
    await this.connectWebSocket();
    
    // 3. Iniciar monitoreo
    this.startSessionMonitoring();
    
    // 4. Iniciar captura
    this.startCameraCapture();
  }
  
  async createSession() {
    const response = await fetch('/session/init', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        preferences: {
          tts_enabled: true,
          voice_language: 'es',
          auto_translate: true,
          target_language: 'en'
        }
      })
    });
    
    const session = await response.json();
    this.sessionId = session.session_id;
  }
  
  async connectWebSocket() {
    return new Promise((resolve) => {
      this.websocket = new WebSocket(
        `ws://localhost:8000/realtime/ws/detection/${this.sessionId}`
      );
      
      this.websocket.onopen = () => resolve();
      this.websocket.onmessage = this.handlePrediction.bind(this);
    });
  }
  
  handlePrediction(event) {
    const data = JSON.parse(event.data);
    if (data.predictions?.length > 0) {
      this.updateUI(data.predictions[0]);
    }
  }
  
  startSessionMonitoring() {
    setInterval(async () => {
      const status = await this.getSessionStatus();
      this.updateSessionUI(status);
      
      if (status.should_auto_finish_phrase) {
        await this.finalizePhraseWithTranslation();
      }
    }, 500);
  }
  
  async finalizePhraseWithTranslation() {
    const response = await fetch('/phrase/finalize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: this.sessionId,
        auto_translate: true,
        target_language: 'en',
        tts_enabled: true
      })
    });
    
    const result = await response.json();
    this.handleCompletedPhrase(result);
  }
}

// Uso
const integration = new BridgeLSPIntegration();
integration.initialize();
```

Esta guía proporciona una implementación completa que replica exactamente el comportamiento del sistema de laboratorio, manteniendo todos los timers, umbrales y la lógica de autocorrección con BERT, pero adaptado para funcionar con WebSockets en tiempo real para aplicaciones cliente.