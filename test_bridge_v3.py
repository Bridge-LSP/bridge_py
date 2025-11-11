import json
import time
import requests
from fastapi.testclient import TestClient
from api.api_main import app

# Test client for synchronous tests
client = TestClient(app)

class TestBridgeAPIv3:
    """Test suite for Bridge API v3.0 production features"""

    def test_health_endpoint(self):
        """Test basic health check"""
        response = client.get("/health")
        assert response.status_code == 200
        assert "Bridge API is running" in response.json()["message"]

    def test_unified_session_init(self):
        """Test unified session initialization"""
        response = client.post("/session/init", json={
            "preferences": {
                "tts_enabled": True,
                "voice_language": "es",
                "auto_translate": False
            }
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Check v3.0 standardized response format
        assert data["status"] == "success"
        assert "session_id" in data
        assert "modules_initialized" in data
        assert "created_at" in data
        assert "autocorrector" in data["modules_initialized"]
        assert "realtime" in data["modules_initialized"]

    def test_session_init_with_client_token(self):
        """Test session initialization with client authentication"""
        response = client.post("/session/init", 
            json={},
            headers={"X-Client-Token": "test-client-123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_session_status(self):
        """Test comprehensive session status"""
        # Create session first
        init_response = client.post("/session/init", json={})
        session_id = init_response.json()["session_id"]
        
        # Get status
        response = client.get(f"/session/status/{session_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["session_id"] == session_id
        assert data["data"]["session_exists"] == True
        assert "autocorrector" in data["data"]["modules"]
        assert "realtime" in data["data"]["modules"]

    def test_continuous_detection_incremental_updates(self):
        """Test incremental state updates in continuous detection"""
        # Create session first
        init_response = client.post("/session/init", json={})
        session_id = init_response.json()["session_id"]
        
        # Mock base64 image (small test image)
        test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        
        response = client.post("/detection/continuous-detect", json={
            "session_id": session_id,
            "frameBase64": test_image_b64,
            "enable_timers": True,
            "confidence_threshold": 0.70
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Check v3.0 incremental update format
        assert data["status"] == "success"
        assert "changed" in data
        assert isinstance(data["changed"], list)
        assert "word_buffer" in data
        assert "predicted_word" in data
        assert "sentence" in data

    def test_phrase_finalization_unified(self):
        """Test unified phrase finalization"""
        # Create session and add some content first
        init_response = client.post("/session/init", json={})
        session_id = init_response.json()["session_id"]
        
        # Add a letter to have content to finalize
        client.post("/autocorrector/letter/add", json={
            "session_id": session_id,
            "letter": "h"
        })
        client.post("/autocorrector/letter/add", json={
            "session_id": session_id,
            "letter": "o"
        })
        client.post("/autocorrector/letter/add", json={
            "session_id": session_id,
            "letter": "l"
        })
        client.post("/autocorrector/letter/add", json={
            "session_id": session_id,
            "letter": "a"
        })
        
        # Test phrase finalization
        response = client.post("/phrase/finalize", json={
            "session_id": session_id,
            "auto_translate": False,  # Skip translation for test
            "tts_enabled": False,     # Skip TTS for test
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Check v3.0 unified response format
        assert data["status"] == "success"
        assert "phrase_finalized" in data
        assert "processing_time_ms" in data
        assert data["phrase_finalized"] != ""

    def test_quick_phrase_completion(self):
        """Test quick phrase completion without TTS/translation"""
        # Create session and add content
        init_response = client.post("/session/init", json={})
        session_id = init_response.json()["session_id"]
        
        # Add letters
        client.post("/autocorrector/letter/add", json={
            "session_id": session_id,
            "letter": "h"
        })
        
        response = client.post("/phrase/quick-complete", json={
            "session_id": session_id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_websocket_status_enhanced(self):
        """Test enhanced WebSocket status with heartbeat info"""
        response = client.get("/realtime/ws/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "active_sessions" in data["data"]
        assert "active_websockets" in data["data"]
        assert "heartbeat_config" in data["data"]
        assert "interval_seconds" in data["data"]["heartbeat_config"]
        assert "timeout_seconds" in data["data"]["heartbeat_config"]

    def test_session_destruction(self):
        """Test comprehensive session cleanup"""
        # Create session
        init_response = client.post("/session/init", json={})
        session_id = init_response.json()["session_id"]
        
        # Verify session exists
        status_response = client.get(f"/session/status/{session_id}")
        assert status_response.json()["data"]["session_exists"] == True
        
        # Destroy session
        destroy_response = client.delete(f"/session/destroy/{session_id}")
        assert destroy_response.status_code == 200
        
        data = destroy_response.json()
        assert data["status"] == "success"
        assert "modules_destroyed" in data["data"]
        assert len(data["data"]["modules_destroyed"]) > 0

    def test_backward_compatibility_session_create(self):
        """Test that legacy session creation still works"""
        # Test legacy autocorrector session creation
        response = client.post("/autocorrector/session/create", json={
            "session_id": "test-legacy-session"
        })
        assert response.status_code == 200
        
        # Test legacy realtime session creation  
        response = client.post("/realtime/session/create", json={
            "session_id": "test-legacy-realtime"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_standardized_error_responses(self):
        """Test that all endpoints return standardized error format"""
        # Test with invalid session ID
        response = client.get("/session/status/invalid-session-id")
        assert response.status_code == 200  # We return 200 with error in body
        
        data = response.json()
        assert data["status"] == "error"
        assert "detail" in data

    def test_performance_headers(self):
        """Test that performance headers are included"""
        response = client.get("/health")
        assert response.status_code == 200
        
        # Check for performance headers
        assert "X-Processing-Time" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers

if __name__ == "__main__":
    # Run basic smoke tests
    test_suite = TestBridgeAPIv3()
    
    print("🚀 Running Bridge API v3.0 Tests...")
    
    try:
        test_suite.test_health_endpoint()
        print("✅ Health endpoint test passed")
        
        test_suite.test_unified_session_init()
        print("✅ Unified session init test passed")
        
        test_suite.test_websocket_status_enhanced()
        print("✅ Enhanced WebSocket status test passed")
        
        test_suite.test_backward_compatibility_session_create()
        print("✅ Backward compatibility test passed")
        
        test_suite.test_standardized_error_responses()
        print("✅ Standardized error responses test passed")
        
        test_suite.test_performance_headers()
        print("✅ Performance headers test passed")
        
        print("\n🎉 All Bridge API v3.0 core tests passed!")
        print("📝 Run 'pytest test_bridge_v3.py -v' for detailed test output")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("🔧 Make sure the server is running: python -m uvicorn api.api_main:app --reload")