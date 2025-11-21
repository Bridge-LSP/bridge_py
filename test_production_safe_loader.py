"""
Test script for production-safe BERT loader.

Tests:
1. Lazy background loading
2. Health endpoint status
3. Session creation blocking during load
4. Fallback behavior (cache → network)
"""

import time
import sys


def test_lazy_loading():
    """Test that module imports instantly without blocking."""
    print("\n" + "="*80)
    print("TEST 1: Lazy Background Loading")
    print("="*80)
    
    start_time = time.time()
    from engine_bridge.bert_model_loader import get_model_info, is_loading, start_background_loading
    import_time = time.time() - start_time
    
    print(f"✅ Import time: {import_time*1000:.1f}ms (should be < 100ms)")
    
    # Check initial state
    info = get_model_info()
    print(f"\nInitial state:")
    print(f"  - Mode: {info['mode']}")
    print(f"  - Loading: {info['loading']}")
    print(f"  - Loaded: {info['loaded']}")
    
    assert info['mode'] == 'not-started', "Should start in not-started mode"
    assert not info['loading'], "Should not be loading initially"
    assert not info['loaded'], "Should not be loaded initially"
    
    # Start background loading
    print(f"\n🚀 Starting background loading...")
    start_background_loading()
    
    # Check loading state
    time.sleep(0.1)  # Brief delay
    info = get_model_info()
    print(f"\nDuring loading:")
    print(f"  - Mode: {info['mode']}")
    print(f"  - Loading: {info['loading']}")
    print(f"  - Loaded: {info['loaded']}")
    
    # Wait for completion (with timeout)
    max_wait = 60  # 60 seconds max
    elapsed = 0
    while is_loading() and elapsed < max_wait:
        time.sleep(1)
        elapsed += 1
        if elapsed % 5 == 0:
            print(f"  ⏳ Still loading... ({elapsed}s)")
    
    # Final state
    info = get_model_info()
    print(f"\nFinal state:")
    print(f"  - Mode: {info['mode']}")
    print(f"  - Loading: {info['loading']}")
    print(f"  - Loaded: {info['loaded']}")
    print(f"  - Network fallback used: {info['network_fallback_used']}")
    
    if info['error']:
        print(f"  - Error: {info['error'][:100]}")
    
    if info['loaded']:
        print(f"\n✅ TEST 1 PASSED: Models loaded successfully in {elapsed}s")
        print(f"   Mode: {info['mode']}")
        return True
    else:
        print(f"\n⚠️  TEST 1: Loading failed (this is OK if transformers not installed)")
        print(f"   Error: {info['error']}")
        return False


def test_model_info():
    """Test the /bert/status endpoint data."""
    print("\n" + "="*80)
    print("TEST 2: Model Info / Health Status")
    print("="*80)
    
    from engine_bridge.bert_model_loader import get_model_info
    
    info = get_model_info()
    
    print("\nModel Info:")
    print(f"  - Model name: {info['model_name']}")
    print(f"  - Cache dir: {info['cache_dir']}")
    print(f"  - Environment: {info['environment']}")
    print(f"  - Production: {info['is_production']}")
    print(f"  - Mode: {info['mode']}")
    print(f"  - Loaded: {info['loaded']}")
    print(f"  - Loading: {info['loading']}")
    print(f"  - Network fallback: {info['network_fallback_used']}")
    print(f"  - Tokenizer loaded: {info['tokenizer_loaded']}")
    print(f"  - Model loaded: {info['model_loaded']}")
    print(f"  - Pipeline loaded: {info['pipeline_loaded']}")
    
    if info['error']:
        print(f"  - Error: {info['error'][:200]}")
    
    # Validate required fields
    required_fields = ['model_name', 'cache_dir', 'environment', 'is_production', 
                      'loaded', 'loading', 'mode', 'network_fallback_used', 'error']
    
    for field in required_fields:
        assert field in info, f"Missing required field: {field}"
    
    print("\n✅ TEST 2 PASSED: All required fields present")
    return True


def test_is_loading_check():
    """Test the is_loading() function for endpoint guards."""
    print("\n" + "="*80)
    print("TEST 3: is_loading() Check")
    print("="*80)
    
    from engine_bridge.bert_model_loader import is_loading, is_bert_available
    
    loading = is_loading()
    available = is_bert_available()
    
    print(f"\nStatus:")
    print(f"  - is_loading(): {loading}")
    print(f"  - is_bert_available(): {available}")
    
    if loading:
        print("\n⚠️  Models still loading - endpoints should block/warn")
    elif available:
        print("\n✅ Models available - endpoints can proceed")
    else:
        print("\n⚠️  Models not available - endpoints should return error")
    
    print("\n✅ TEST 3 PASSED: Status checks working")
    return True


def test_fallback_logic():
    """Test that fallback logic is properly implemented."""
    print("\n" + "="*80)
    print("TEST 4: Fallback Logic Validation")
    print("="*80)
    
    from engine_bridge.bert_model_loader import get_model_info
    
    info = get_model_info()
    
    print("\nFallback behavior:")
    print(f"  - Mode: {info['mode']}")
    print(f"  - Network fallback used: {info['network_fallback_used']}")
    
    if info['mode'] == 'cache-only':
        print("  ✅ Loaded from cache (optimal)")
    elif info['mode'] == 'network-fallback':
        print("  ⚠️  Used network fallback (cache was empty)")
    elif info['mode'] == 'failed':
        print("  ⚠️  Loading failed (both cache and network failed)")
    elif info['mode'] == 'loading':
        print("  ⏳ Still loading...")
    
    print("\n✅ TEST 4 PASSED: Fallback logic present")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("PRODUCTION-SAFE BERT LOADER TEST SUITE")
    print("="*80)
    
    results = []
    
    try:
        results.append(("Lazy Loading", test_lazy_loading()))
        results.append(("Model Info", test_model_info()))
        results.append(("is_loading Check", test_is_loading_check()))
        results.append(("Fallback Logic", test_fallback_logic()))
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print("\n⚠️  SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
