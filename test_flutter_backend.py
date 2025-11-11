
import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"
TEST_SESSION_ID = "flutter_test_123"

def test_health():

    print("🔍 Testing /health...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"✅ Health: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health failed: {e}")
        return False

def test_session_creation():

    print(f"🔍 Testing session creation...")
    try:
        payload = {"session_id": TEST_SESSION_ID}
        response = requests.post(
            f"{BASE_URL}/autocorrector/session/create",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"✅ Session creation: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Session creation failed: {e}")
        return False

def test_session_status():

    print(f"🔍 Testing session status...")
    try:
        payload = {"session_id": TEST_SESSION_ID}
        response = requests.post(
            f"{BASE_URL}/autocorrector/session/status",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"✅ Session status: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Session status failed: {e}")
        return False

def test_add_letter():

    print(f"🔍 Testing add letter...")
    try:
        payload = {"session_id": TEST_SESSION_ID, "letter": "h"}
        response = requests.post(
            f"{BASE_URL}/autocorrector/letter/add",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"✅ Add letter: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Add letter failed: {e}")
        return False

def main():
    print("🚀 Testing Bridge Backend for Flutter Compatibility")
    print(f"📡 Base URL: {BASE_URL}")

    tests = [
        ("Health Check", test_health),
        ("Session Creation", test_session_creation),
        ("Session Status", test_session_status),
        ("Add Letter", test_add_letter)
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append((test_name, result))
        time.sleep(1)

    print("\n" + "="*50)
    print("📊 TEST RESULTS:")
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")
        if not result:
            all_passed = False

    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Backend is ready for Flutter!")
        print(f"📱 Flutter can connect to: {BASE_URL}")
        print(f"🔌 WebSocket available at: ws://127.0.0.1:8000/realtime/ws/detection/{{client_id}}")
    else:
        print("\n❌ Some tests failed. Check backend configuration.")

    return all_passed

if __name__ == "__main__":
    main()