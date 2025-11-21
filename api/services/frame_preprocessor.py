import cv2
import numpy as np
from typing import Tuple, Optional, Dict
import time

# ============================================================================
# BYPASS MODE FOR DEBUGGING
# ============================================================================
# Set to True to bypass ALL preprocessing and pass frames directly to MediaPipe
# This helps diagnose if preprocessing is causing detection failures
BYPASS_PREPROCESSOR = False
# ============================================================================

class FramePreprocessor:
    """
    Centralized frame preprocessing for all detection pipelines.
    Handles orientation correction, normalization, and diagnostics.
    
    CRITICAL: Default configuration MUST match main.py behavior:
    - main.py does cv2.flip(frame, 1) ONCE after camera capture
    - WebSocket frames should receive the SAME treatment
    - Default: flip_horizontal=True to match main.py's mirror effect
    """
    
    def __init__(self):
        # DEFAULT: Match main.py behavior (horizontal flip for mirror effect)
        self.flip_horizontal = True  # Match main.py's cv2.flip(frame, 1)
        self.flip_vertical = False
        self.rotation_angle = 0  # 0, 90, 180, 270
        self.normalization_enabled = False
        self.target_size = (640, 480)
        self.diagnostics_enabled = False
        
        self.frame_count = 0
        self.successful_decodes = 0
        self.failed_decodes = 0
        self.preprocessing_time_ms = []
        
        print(f"[FramePreprocessor] Initialized with flip_horizontal={self.flip_horizontal} (matches main.py)")
    
    def configure(self, flip_h: bool = False, flip_v: bool = False, 
                  rotation: int = 0, normalize: bool = False):
        """Configure preprocessing transformations."""
        self.flip_horizontal = flip_h
        self.flip_vertical = flip_v
        self.rotation_angle = rotation
        self.normalization_enabled = normalize
        print(f"[FramePreprocessor] Configured: flip_h={flip_h}, flip_v={flip_v}, rot={rotation}°")
    
    def decode_and_preprocess(self, image_bytes: bytes) -> Optional[np.ndarray]:
        """
        Decode base64 image and apply all preprocessing steps.
        Returns preprocessed BGR image ready for Mediapipe, or None if decode fails.
        """
        start_time = time.time()
        self.frame_count += 1
        
        try:
            np_arr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            if image is None or image.size == 0:
                self.failed_decodes += 1
                return None
            
            self.successful_decodes += 1
            
            # BYPASS MODE: Skip all transformations for debugging
            if BYPASS_PREPROCESSOR:
                if self.diagnostics_enabled:
                    print(f"[FramePreprocessor] BYPASS MODE: Returning raw frame shape={image.shape}")
                return image
            
            processed = self._apply_transformations(image)
            
            elapsed_ms = (time.time() - start_time) * 1000
            self.preprocessing_time_ms.append(elapsed_ms)
            
            if len(self.preprocessing_time_ms) > 100:
                self.preprocessing_time_ms = self.preprocessing_time_ms[-100:]
            
            return processed
            
        except Exception as e:
            self.failed_decodes += 1
            if self.diagnostics_enabled:
                print(f"[FramePreprocessor] Decode error: {e}")
            return None
    
    def _apply_transformations(self, image: np.ndarray) -> np.ndarray:
        """Apply configured transformations to image."""
        processed = image.copy()
        
        if self.flip_horizontal:
            processed = cv2.flip(processed, 1)
        
        if self.flip_vertical:
            processed = cv2.flip(processed, 0)
        
        if self.rotation_angle == 90:
            processed = cv2.rotate(processed, cv2.ROTATE_90_CLOCKWISE)
        elif self.rotation_angle == 180:
            processed = cv2.rotate(processed, cv2.ROTATE_180)
        elif self.rotation_angle == 270:
            processed = cv2.rotate(processed, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        if self.normalization_enabled:
            processed = self._normalize_size(processed)
        
        return processed
    
    def _normalize_size(self, image: np.ndarray) -> np.ndarray:
        """Resize image to target size with aspect ratio preservation."""
        target_w, target_h = self.target_size
        h, w = image.shape[:2]
        
        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        resized = cv2.resize(image, (new_w, new_h))
        
        canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        y_offset = (target_h - new_h) // 2
        x_offset = (target_w - new_w) // 2
        canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
        
        return canvas
    
    def get_stats(self) -> Dict:
        """Get preprocessing statistics."""
        avg_time = sum(self.preprocessing_time_ms) / len(self.preprocessing_time_ms) if self.preprocessing_time_ms else 0
        success_rate = (self.successful_decodes / self.frame_count * 100) if self.frame_count > 0 else 0
        
        return {
            "total_frames": self.frame_count,
            "successful_decodes": self.successful_decodes,
            "failed_decodes": self.failed_decodes,
            "success_rate_percent": round(success_rate, 2),
            "avg_preprocessing_time_ms": round(avg_time, 2),
            "configuration": {
                "flip_horizontal": self.flip_horizontal,
                "flip_vertical": self.flip_vertical,
                "rotation_angle": self.rotation_angle,
                "normalization_enabled": self.normalization_enabled
            }
        }
    
    def reset_stats(self):
        """Reset all statistics."""
        self.frame_count = 0
        self.successful_decodes = 0
        self.failed_decodes = 0
        self.preprocessing_time_ms = []


frame_preprocessor = FramePreprocessor()
