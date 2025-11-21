"""
SessionManager - Global registry and factory for SessionEngine instances.

This module manages the lifecycle of user sessions, shared ML models,
and MediaPipe resources to avoid reloading models per session.
"""


USE_LSTM = False

import time
import threading
import logging
from typing import Dict, Optional
import joblib

from engine_bridge.session_engine import SessionEngine
from engine_bridge.hand_tracker import create_hand_landmarker

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Global registry of SessionEngine instances with shared ML resources.
    
    Manages session lifecycle, model loading, and cleanup of inactive sessions.
    """
    
    def __init__(self, 
                 rf_model_path: str = 'models/forest_model_u.pkl',
                 lstm_model_path: str = 'models/lstm_model.h5',
                 session_ttl_seconds: int = 3600):
        
        self.sessions: Dict[str, SessionEngine] = {}
        self.session_last_activity: Dict[str, float] = {}
        self.session_ttl = session_ttl_seconds
        self._lock = threading.RLock()
        
        self.hand_landmarker = None
        self.rf_model = None
        self.lstm_model = None
        
        self._load_models(rf_model_path, lstm_model_path)
        
        logger.info("SessionManager initialized with shared models")
    
    def _load_models(self, rf_model_path: str, lstm_model_path: str) -> None:
        """Load shared ML models once at startup."""
        try:
            self.hand_landmarker = create_hand_landmarker(running_mode="VIDEO")
            logger.info("✅ MediaPipe hand landmarker loaded")
            
            self.rf_model = joblib.load(rf_model_path)
            logger.info("✅ Random Forest model loaded")
            
            if USE_LSTM:
                try:
                    import tensorflow as tf
                    self.lstm_model = tf.keras.models.load_model(lstm_model_path)
                    logger.info("✅ LSTM model loaded (dynamic gestures: j, ll, rr, z, ñ)")
                except ImportError:
                    logger.warning("⚠️ TensorFlow not available. LSTM model disabled.")
                    self.lstm_model = None
                except Exception as e:
                    logger.warning(f"⚠️ Could not load LSTM model: {e}. Using RF only.")
                    self.lstm_model = None
            else:
                self.lstm_model = None
                logger.info("🔧 LSTM disabled (RF-only mode) - Set USE_LSTM=True to re-enable")
                
        except Exception as e:
            logger.error(f"❌ Error loading models: {e}")
            raise
    
    def get_or_create_session(self, session_id: str, preferences: Optional[Dict] = None) -> SessionEngine:
        """Get existing session or create a new one with shared models."""
        with self._lock:
            current_time = time.time()
            
            self.session_last_activity[session_id] = current_time
            
            if session_id in self.sessions:
                engine = self.sessions[session_id]
                if preferences:
                    engine.update_preferences(preferences)
                logger.debug(f"Retrieved existing session: {session_id}")
                return engine
            
            engine = SessionEngine(
                session_id=session_id,
                hand_landmarker=self.hand_landmarker,
                rf_model=self.rf_model,
                lstm_model=self.lstm_model,
                preferences=preferences
            )
            
            self.sessions[session_id] = engine
            logger.info(f"Created new session: {session_id}")
            
            return engine
    
    def get_session(self, session_id: str) -> Optional[SessionEngine]:
        """Get existing session without creating a new one."""
        with self._lock:
            if session_id in self.sessions:
                self.session_last_activity[session_id] = time.time()
                return self.sessions[session_id]
            return None
    
    def remove_session(self, session_id: str) -> bool:
        """Remove a specific session."""
        with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                if session_id in self.session_last_activity:
                    del self.session_last_activity[session_id]
                logger.info(f"Removed session: {session_id}")
                return True
            return False
    
    def cleanup_inactive_sessions(self) -> int:
        """Remove sessions that have been inactive for longer than TTL."""
        current_time = time.time()
        expired_sessions = []
        
        with self._lock:
            for session_id, last_activity in self.session_last_activity.items():
                if current_time - last_activity > self.session_ttl:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                if session_id in self.sessions:
                    del self.sessions[session_id]
                del self.session_last_activity[session_id]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} inactive sessions: {expired_sessions}")
        
        return len(expired_sessions)
    
    def get_session_count(self) -> int:
        """Get the current number of active sessions."""
        with self._lock:
            return len(self.sessions)
    
    def get_session_info(self) -> Dict[str, Dict]:
        """Get information about all active sessions."""
        current_time = time.time()
        info = {}
        
        with self._lock:
            for session_id, engine in self.sessions.items():
                last_activity = self.session_last_activity.get(session_id, 0)
                info[session_id] = {
                    "is_running": engine.is_running,
                    "last_activity": last_activity,
                    "inactive_seconds": current_time - last_activity,
                    "auto_translate": engine.auto_translate,
                    "target_language": engine.target_language,
                    "tts_enabled": engine.tts_enabled,
                    "tts_muted": engine.tts_muted
                }
        
        return info
    
    def stop_all_sessions(self) -> None:
        """Stop all active sessions (set is_running = False)."""
        with self._lock:
            for engine in self.sessions.values():
                engine.set_running(False)
            logger.info(f"Stopped all {len(self.sessions)} active sessions")
    
    def clear_all_sessions(self) -> None:
        """Clear all sessions (for shutdown or testing)."""
        with self._lock:
            session_count = len(self.sessions)
            self.sessions.clear()
            self.session_last_activity.clear()
            logger.info(f"Cleared all {session_count} sessions")


session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global session_manager
    if session_manager is None:
        session_manager = SessionManager()
    return session_manager


def initialize_session_manager(rf_model_path: str = 'models/forest_model_u.pkl',
                              lstm_model_path: str = 'models/lstm_model.h5',
                              session_ttl_seconds: int = 3600) -> SessionManager:
    """Initialize the global session manager with custom parameters."""
    global session_manager
    session_manager = SessionManager(
        rf_model_path=rf_model_path,
        lstm_model_path=lstm_model_path,
        session_ttl_seconds=session_ttl_seconds
    )
    return session_manager