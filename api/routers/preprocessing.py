from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import base64
import cv2
import numpy as np

from api.services.frame_preprocessor import frame_preprocessor

router = APIRouter()

class PreprocessingConfigRequest(BaseModel):
    flip_horizontal: bool = False
    flip_vertical: bool = False
    rotation_angle: int = 0  # 0, 90, 180, 270
    enable_normalization: bool = False

class CalibrateRequest(BaseModel):
    image_base64: str

@router.post("/preprocessing/configure")
async def configure_preprocessing(config: PreprocessingConfigRequest):
    """
    Configure frame preprocessing transformations.
    These apply to ALL WebSocket and HTTP detection endpoints.
    """
    try:
        frame_preprocessor.configure(
            flip_h=config.flip_horizontal,
            flip_v=config.flip_vertical,
            rotation=config.rotation_angle,
            normalize=config.enable_normalization
        )
        
        return {
            "success": True,
            "message": "Preprocessing configured successfully",
            "configuration": frame_preprocessor.get_stats()["configuration"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/preprocessing/stats")
async def get_preprocessing_stats():
    """Get preprocessing performance statistics."""
    return frame_preprocessor.get_stats()

@router.post("/preprocessing/reset-stats")
async def reset_preprocessing_stats():
    """Reset preprocessing statistics."""
    frame_preprocessor.reset_stats()
    return {"success": True, "message": "Statistics reset"}

@router.post("/calibrate")
async def auto_calibrate(request: CalibrateRequest):
    """
    Automatically calibrate preprocessing by testing transformations with MediaPipe.
    Returns the recommended configuration based on hand detection confidence.
    """
    try:
        image_bytes = base64.b64decode(request.image_base64)
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image data")
        
        from engine_bridge.hand_tracker import create_hand_tracker
        tracker = create_hand_tracker()
        
        transformations = []
        for flip_h in [False, True]:
            for flip_v in [False, True]:
                for rotation in [0, 90, 180, 270]:
                    test_frame = image.copy()
                    
                    if flip_h:
                        test_frame = cv2.flip(test_frame, 1)
                    if flip_v:
                        test_frame = cv2.flip(test_frame, 0)
                    if rotation == 90:
                        test_frame = cv2.rotate(test_frame, cv2.ROTATE_90_CLOCKWISE)
                    elif rotation == 180:
                        test_frame = cv2.rotate(test_frame, cv2.ROTATE_180)
                    elif rotation == 270:
                        test_frame = cv2.rotate(test_frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    
                    rgb_frame = cv2.cvtColor(test_frame, cv2.COLOR_BGR2RGB)
                    results = tracker.process(rgb_frame)
                    
                    confidence = 0
                    hands_detected = 0
                    if results and results.hand_landmarks:
                        hands_detected = len(results.hand_landmarks)
                        confidence = hands_detected
                    
                    transformations.append({
                        "flip_h": flip_h,
                        "flip_v": flip_v,
                        "rotation": rotation,
                        "confidence": confidence,
                        "hands_detected": hands_detected
                    })
        
        best = max(transformations, key=lambda t: t["confidence"])
        
        if best["confidence"] == 0:
            return {
                "success": False,
                "message": "No hands detected in any transformation. Try again with hand visible.",
                "all_results": transformations
            }
        
        frame_preprocessor.configure(
            flip_h=best["flip_h"],
            flip_v=best["flip_v"],
            rotation=best["rotation"],
            normalize=False
        )
        
        return {
            "success": True,
            "recommended_config": {
                "flip_horizontal": best["flip_h"],
                "flip_vertical": best["flip_v"],
                "rotation_angle": best["rotation"]
            },
            "hands_detected": best["hands_detected"],
            "message": f"Calibrated: flip_h={best['flip_h']}, flip_v={best['flip_v']}, rotation={best['rotation']}°",
            "top_results": sorted(transformations, key=lambda t: t["confidence"], reverse=True)[:5]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/detection/mode")
async def get_detection_mode():
    """Get current detection mode configuration."""
    return {
        "detection_mode": "random_forest_only",
        "lstm_enabled": False,
        "reason": "LSTM disabled for stability - requires proper sequence buffering",
        "preprocessing_enabled": True
    }
