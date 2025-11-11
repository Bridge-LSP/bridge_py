#!/usr/bin/env python3
"""
Test script for hardened WebSocket backend
"""
import requests
import json
import base64
import asyncio
import websockets
import time

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000"

# Create a simple test image (1x1 pixel JPEG)
def create_test_image_b64():
    """Create a minimal test JPEG image as base64"""
    # This is a minimal 1x1 pixel JPEG in base64
    test_jpeg_b64 = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k="
    return test_jpeg_b64

def test_health():
    """Test health endpoint"""
    print("🔍 Testing /health...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✅ Health: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health failed: {e}")
        return False

def test_session_creation():
    """Test session creation"""
    print("🔍 Testing session creation...")
    try:
        payload = {"session_id": "test_session_123"}
        response = requests.post(
            f"{BASE_URL}/realtime/session/create",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        print(f"✅ Session creation: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Session creation failed: {e}")
        return False

def test_detect_fallback():
    """Test HTTP detect fallback"""
    print("🔍 Testing HTTP detect fallback...")
    try:
        payload = {
            "frameBase64": create_test_image_b64(),
            "clientId": "test_client"
        }
        response = requests.post(
            f"{BASE_URL}/realtime/detect",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"✅ HTTP detect: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ HTTP detect failed: {e}")
        return False

async def test_websocket_echo():
    """Test WebSocket echo endpoint"""
    print("🔍 Testing WebSocket echo...")
    try:
        uri = f"{WS_URL}/realtime/ws/echo"
        async with websockets.connect(uri) as websocket:
            # Send test message
            test_msg = "Hello WebSocket!"
            await websocket.send(test_msg)
            
            # Receive echo
            response = await websocket.recv()
            print(f"✅ WebSocket echo: Sent '{test_msg}', Received '{response}'")
            return True
            
    except Exception as e:
        print(f"❌ WebSocket echo failed: {e}")
        return False

async def test_websocket_detection():
    """Test WebSocket detection endpoint"""
    print("🔍 Testing WebSocket detection...")
    try:
        uri = f"{WS_URL}/realtime/ws/detection/test_client_123"
        async with websockets.connect(uri) as websocket:
            # Send test frame
            test_frame = create_test_image_b64()
            frame_msg = json.dumps({"type": "frame", "data": test_frame})
            await websocket.send(frame_msg)
            
            # Wait for response with timeout
            response = await asyncio.wait_for(websocket.recv(), timeout=10)
            result = json.loads(response)
            print(f"✅ WebSocket detection: {result}")
            return True
            
    except asyncio.TimeoutError:
        print("❌ WebSocket detection timeout")
        return False
    except Exception as e:
        print(f"❌ WebSocket detection failed: {e}")
        return False

def test_ws_status():
    """Test WebSocket status endpoint"""
    print("🔍 Testing WebSocket status...")
    try:
        response = requests.get(f"{BASE_URL}/realtime/ws/status", timeout=5)
        print(f"✅ WS Status: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ WS Status failed: {e}")
        return False

def test_timer_management():
    """Test timer management endpoints"""
    print("🔍 Testing timer management...")
    try:
        # Test word timer
        payload = {"session_id": "timer_test", "action": "start_word"}
        response = requests.post(
            f"{BASE_URL}/timers/control",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        print(f"✅ Timer control: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Timer management failed: {e}")
        return False

def test_continuous_detection():
    """Test continuous detection endpoint"""
    print("🔍 Testing continuous detection...")
    try:
        payload = {
            "session_id": "continuous_test",
            "frameBase64": create_test_image_b64(),
            "enable_timers": True,
            "confidence_threshold": 0.70
        }
        response = requests.post(
            f"{BASE_URL}/detection/continuous-detect",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"✅ Continuous detection: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Continuous detection failed: {e}")
        return False

async def run_async_tests():
    """Run async WebSocket tests"""
    ws_echo_result = await test_websocket_echo()
    ws_detection_result = await test_websocket_detection()
    return ws_echo_result, ws_detection_result

def main():
    print("🚀 Testing Hardened Bridge Backend")
    print(f"📡 Base URL: {BASE_URL}")
    print(f"🔌 WebSocket URL: {WS_URL}")
    print("=" * 60)
    
    # HTTP tests
    http_tests = [
        ("Health Check", test_health),
        ("Session Creation", test_session_creation),
        ("HTTP Detect Fallback", test_detect_fallback),
        ("WebSocket Status", test_ws_status),
        ("Timer Management", test_timer_management),
        ("Continuous Detection", test_continuous_detection)
    ]
    
    http_results = []
    for test_name, test_func in http_tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        http_results.append((test_name, result))
        time.sleep(0.5)
    
    # WebSocket tests
    print(f"\n--- WebSocket Tests ---")
    ws_echo_result, ws_detection_result = asyncio.run(run_async_tests())
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS:")
    
    all_passed = True
    for test_name, result in http_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")
        if not result:
            all_passed = False
    
    status = "✅ PASS" if ws_echo_result else "❌ FAIL"
    print(f"  {status}: WebSocket Echo")
    if not ws_echo_result:
        all_passed = False
    
    status = "✅ PASS" if ws_detection_result else "❌ FAIL"
    print(f"  {status}: WebSocket Detection")
    if not ws_detection_result:
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Hardened backend is ready!")
        print(f"📱 Flutter can connect to:")
        print(f"   - HTTP: {BASE_URL}")
        print(f"   - WebSocket: {WS_URL}/realtime/ws/detection/{{client_id}}")
        print(f"   - Echo Test: {WS_URL}/realtime/ws/echo")
    else:
        print("❌ Some tests failed. Check backend configuration.")
        print("\n💡 To start the server:")
        print("  python -m uvicorn api.api_main:app --reload --host 0.0.0.0 --port 8000")
    
    return all_passed

if __name__ == "__main__":
    main()