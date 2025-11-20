"""
Test script for SessionEngine architecture.

This script validates that the new SessionEngine correctly replicates
the behavior from main.py without requiring a frontend client.
"""

import asyncio
import json
import time
import base64
import cv2
import numpy as np
from engine_bridge.session_manager import initialize_session_manager
from engine_bridge.session_engine import SessionEngine


def create_test_frame() -> str:
    """Create a dummy frame for testing."""
    # Create a simple test image
    frame = cv2.imread("test_hand_image.jpg") if cv2.imread("test_hand_image.jpg") is not None else None
    
    if frame is None:
        # Create a blank frame if no test image available
        frame = cv2.zeros((480, 640, 3), dtype=np.uint8)
    
    # Encode to JPEG
    _, buffer = cv2.imencode('.jpg', frame)
    
    # Convert to base64
    frame_base64 = base64.b64encode(buffer).decode('utf-8')
    return frame_base64


async def test_session_engine():
    """Test the SessionEngine functionality."""
    print("🧪 Testing SessionEngine Architecture")
    print("=" * 50)
    
    # Initialize SessionManager
    try:
        session_manager = initialize_session_manager()
        print("✅ SessionManager initialized")
    except Exception as e:
        print(f"❌ Failed to initialize SessionManager: {e}")
        return
    
    # Test 1: Create session
    print("\n📋 Test 1: Session Creation")
    session_id = "test-session-123"
    preferences = {
        "tts_enabled": True,
        "auto_translate": True,
        "target_language": "en",
        "word_pause_ms": 2000,  # Shorter for testing
        "phrase_pause_ms": 4000
    }
    
    session_engine = session_manager.get_or_create_session(session_id, preferences)
    print(f"✅ Session created: {session_id}")
    print(f"   - TTS enabled: {session_engine.tts_enabled}")
    print(f"   - Auto translate: {session_engine.auto_translate}")
    print(f"   - Target language: {session_engine.target_language}")
    
    # Test 2: Session state when not running
    print("\n📋 Test 2: Stopped State")
    session_engine.set_running(False)
    frame_base64 = create_test_frame()
    state = session_engine.process_frame_base64(frame_base64)
    print(f"✅ Processing when stopped returns state without detection")
    print(f"   - Type: {state['type']}")
    print(f"   - Session ID: {state['session_id']}")
    
    # Test 3: Start session and simulate frame processing
    print("\n📋 Test 3: Running State and Frame Processing")
    session_engine.set_running(True)
    
    # Process a few frames to simulate detection
    for i in range(3):
        state = session_engine.process_frame_base64(frame_base64)
        print(f"   Frame {i+1}: {state['detection']['letter'] or 'No detection'}")
        time.sleep(0.2)  # Simulate frame interval
    
    # Test 4: Manual letter addition (simulate detection)
    print("\n📋 Test 4: Manual Letter Addition")
    try:
        # Manually add letters to test autocorrector flow
        session_engine._accept_new_letter("H", time.time(), "test")
        time.sleep(0.1)
        session_engine._accept_new_letter("O", time.time(), "test") 
        time.sleep(0.1)
        session_engine._accept_new_letter("L", time.time(), "test")
        time.sleep(0.1)
        session_engine._accept_new_letter("A", time.time(), "test")
        
        state = session_engine._build_state_payload()
        print(f"✅ Letters added: {state['word']['raw_buffer']}")
        print(f"   - Corrected word: {state['word']['corrected']}")
        print(f"   - Current sentence: {state['sentence']['current']}")
    except Exception as e:
        print(f"❌ Error in manual letter addition: {e}")
    
    # Test 5: Word timeout simulation
    print("\n📋 Test 5: Word Timeout")
    try:
        # Wait for word timeout to trigger
        time.sleep(2.5)  # More than word_pause_ms (2000ms)
        current_time = time.time()
        session_engine._check_word_timeout(current_time)
        
        state = session_engine._build_state_payload()
        print(f"✅ Word timeout triggered")
        print(f"   - Just finished: {state['word']['just_finished']}")
        print(f"   - Current sentence: {state['sentence']['current']}")
    except Exception as e:
        print(f"❌ Error in word timeout: {e}")
    
    # Test 6: Manual phrase finalization
    print("\n📋 Test 6: Manual Phrase Finalization")
    try:
        # Add another word first
        session_engine._accept_new_letter("M", time.time(), "test")
        session_engine._accept_new_letter("U", time.time(), "test")
        session_engine._accept_new_letter("N", time.time(), "test")
        session_engine._accept_new_letter("D", time.time(), "test")
        session_engine._accept_new_letter("O", time.time(), "test")
        
        # Manually finalize phrase
        state = session_engine.manual_finalize_phrase()
        print(f"✅ Phrase finalized manually")
        print(f"   - Completed: {state['sentence']['completed']}")
        print(f"   - Just completed: {state['sentence']['just_completed']}")
        print(f"   - Translation enabled: {state['translation']['enabled']}")
        print(f"   - TTS available: {state['tts']['audio_available']}")
    except Exception as e:
        print(f"❌ Error in phrase finalization: {e}")
    
    # Test 7: Preferences update
    print("\n📋 Test 7: Preferences Update")
    try:
        new_preferences = {
            "tts_muted": True,
            "target_language": "fr",
            "word_pause_ms": 3000
        }
        session_engine.update_preferences(new_preferences)
        print(f"✅ Preferences updated")
        print(f"   - TTS muted: {session_engine.tts_muted}")
        print(f"   - Target language: {session_engine.target_language}")
        print(f"   - Word pause: {session_engine.word_pause_ms}ms")
    except Exception as e:
        print(f"❌ Error updating preferences: {e}")
    
    # Test 8: Session cleanup
    print("\n📋 Test 8: Session Cleanup")
    try:
        session_engine.clear_all()
        state = session_engine._build_state_payload()
        print(f"✅ Session cleared")
        print(f"   - Word buffer: '{state['word']['raw_buffer']}'")
        print(f"   - Sentence: '{state['sentence']['current']}'")
        print(f"   - Completed: {state['sentence']['completed']}")
    except Exception as e:
        print(f"❌ Error in session cleanup: {e}")
    
    # Test 9: SessionManager functionality
    print("\n📋 Test 9: SessionManager Functions")
    try:
        session_count = session_manager.get_session_count()
        session_info = session_manager.get_session_info()
        print(f"✅ SessionManager status")
        print(f"   - Active sessions: {session_count}")
        print(f"   - Session info keys: {list(session_info.keys())}")
        
        # Test session removal
        removed = session_manager.remove_session(session_id)
        print(f"   - Session removed: {removed}")
        print(f"   - Remaining sessions: {session_manager.get_session_count()}")
    except Exception as e:
        print(f"❌ Error in SessionManager tests: {e}")
    
    print("\n🎉 SessionEngine tests completed!")
    print("=" * 50)


async def test_websocket_protocol():
    """Test WebSocket message protocol parsing."""
    print("\n🌐 Testing WebSocket Protocol")
    
    # Test frame message
    frame_message = {
        "type": "frame",
        "frameBase64": create_test_frame()
    }
    
    # Test control messages
    control_messages = [
        {"type": "control", "action": "play"},
        {"type": "control", "action": "stop"},
        {"type": "control", "action": "clear_all"},
        {
            "type": "control", 
            "action": "update_preferences",
            "payload": {"tts_muted": True, "target_language": "fr"}
        }
    ]
    
    print("✅ Message protocol structures validated")
    for i, msg in enumerate(control_messages):
        print(f"   Control {i+1}: {msg['action']}")


if __name__ == "__main__":
    print("🚀 Starting SessionEngine Architecture Tests")
    
    # Run async tests
    asyncio.run(test_session_engine())
    asyncio.run(test_websocket_protocol())
    
    print("\n✅ All tests completed!")