import json
import time
import requests
from fastapi.testclient import TestClient
from api.api_main import app

client = TestClient(app)

class TestBridgeAPIv3:

    def test_health_endpoint(self):

        response = client.get("/health")
        assert response.status_code == 200
        assert "Bridge API is running" in response.json()["message"]

    def test_unified_session_init(self):

        response = client.post("/session/init", json={
            "preferences": {
                "tts_enabled": True,
                "voice_language": "es",
                "auto_translate": False
            }
        })

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert "session_id" in data
        assert "modules_initialized" in data
        assert "created_at" in data
        assert "autocorrector" in data["modules_initialized"]
        assert "realtime" in data["modules_initialized"]

    def test_session_init_with_client_token(self):

        response = client.post("/session/init",
            json={},
            headers={"X-Client-Token": "test-client-123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_session_status(self):

        init_response = client.post("/session/init", json={})
        session_id = init_response.json()["session_id"]

        response = client.get(f"/session/status/{session_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["session_id"] == session_id
        assert data["data"]["session_exists"] == True
        assert "autocorrector" in data["data"]["modules"]
        assert "realtime" in data["data"]["modules"]

    def test_continuous_detection_incremental_updates(self):

        init_response = client.post("/session/init", json={})
        session_id = init_response.json()["session_id"]

        test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

        response = client.post("/detection/continuous-detect", json={
            "session_id": session_id,
            "frameBase64": test_image_b64,
            "enable_timers": True,
            "confidence_threshold": 0.70
        })

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert "changed" in data
        assert isinstance(data["changed"], list)
        assert "word_buffer" in data
        assert "predicted_word" in data
        assert "sentence" in data

    def test_phrase_finalization_unified(self):

        init_response = client.post("/session/init", json={})
        session_id = init_response.json()["session_id"]

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

        response = client.post("/phrase/finalize", json={
            "session_id": session_id,
            "auto_translate": False,
            "tts_enabled": False,
        })

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert "phrase_finalized" in data
        assert "processing_time_ms" in data
        assert data["phrase_finalized"] != ""

    def test_quick_phrase_completion(self):

        init_response = client.post("/session/init", json={})
        session_id = init_response.json()["session_id"]

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

        init_response = client.post("/session/init", json={})
        session_id = init_response.json()["session_id"]

        status_response = client.get(f"/session/status/{session_id}")
        assert status_response.json()["data"]["session_exists"] == True

        destroy_response = client.delete(f"/session/destroy/{session_id}")
        assert destroy_response.status_code == 200

        data = destroy_response.json()
        assert data["status"] == "success"
        assert "modules_destroyed" in data["data"]
        assert len(data["data"]["modules_destroyed"]) > 0

    def test_backward_compatibility_session_create(self):

        response = client.post("/autocorrector/session/create", json={
            "session_id": "test-legacy-session"
        })
        assert response.status_code == 200

        response = client.post("/realtime/session/create", json={
            "session_id": "test-legacy-realtime"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_standardized_error_responses(self):

        response = client.get("/session/status/invalid-session-id")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "error"
        assert "detail" in data

    def test_performance_headers(self):

        response = client.get("/health")
        assert response.status_code == 200

        assert "X-Processing-Time" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers

if __name__ == "__main__":
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