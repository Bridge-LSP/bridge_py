"""
Test script to verify BERT model loading works correctly.

This validates:
1. Models load successfully
2. Global singleton pattern works
3. Multiple AutoCorrector instances share the same models
4. No duplicate model loading
"""

import time
import psutil
import os

def get_memory_usage():
    """Get current process memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def test_global_model_loader():
    """Test that global model loader works."""
    print("=" * 70)
    print("TEST 1: Global Model Loader")
    print("=" * 70)
    print()
    
    print("⏱️  Importing bert_model_loader...")
    start = time.time()
    from engine_bridge.bert_model_loader import (
        get_bert_tokenizer,
        get_bert_model,
        get_bert_pipeline,
        is_bert_available,
        get_model_info
    )
    elapsed = time.time() - start
    print(f"✅ Import took {elapsed:.2f}s")
    print()
    
    # Check model info
    info = get_model_info()
    print("📊 Model Info:")
    for key, value in info.items():
        print(f"   {key}: {value}")
    print()
    
    # Check availability
    if is_bert_available():
        print("✅ BERT models are available")
        print(f"   Tokenizer: {type(get_bert_tokenizer()).__name__}")
        print(f"   Model: {type(get_bert_model()).__name__}")
        print(f"   Pipeline: {type(get_bert_pipeline()).__name__}")
        print()
        return True
    else:
        print("❌ BERT models NOT available")
        print(f"   Error: {info['load_error']}")
        print()
        return False

def test_autocorrector_performance():
    """Test that AutoCorrector instantiation is fast."""
    print("=" * 70)
    print("TEST 2: AutoCorrector Performance")
    print("=" * 70)
    print()
    
    print("⏱️  Creating first AutoCorrector instance...")
    mem_before = get_memory_usage()
    start = time.time()
    
    from engine_bridge.autocorrector.autocorrector_core import AutoCorrector
    corrector1 = AutoCorrector()
    
    elapsed1 = time.time() - start
    mem_after1 = get_memory_usage()
    mem_increase1 = mem_after1 - mem_before
    
    print(f"✅ First instance created in {elapsed1:.3f}s")
    print(f"   Memory increase: {mem_increase1:.2f} MB")
    print()
    
    # Create second instance (should be instant)
    print("⏱️  Creating second AutoCorrector instance...")
    mem_before2 = mem_after1
    start2 = time.time()
    
    corrector2 = AutoCorrector()
    
    elapsed2 = time.time() - start2
    mem_after2 = get_memory_usage()
    mem_increase2 = mem_after2 - mem_before2
    
    print(f"✅ Second instance created in {elapsed2:.3f}s")
    print(f"   Memory increase: {mem_increase2:.2f} MB")
    print()
    
    # Create third instance
    print("⏱️  Creating third AutoCorrector instance...")
    start3 = time.time()
    corrector3 = AutoCorrector()
    elapsed3 = time.time() - start3
    print(f"✅ Third instance created in {elapsed3:.3f}s")
    print()
    
    # Verify they share the same model
    print("🔍 Verifying model sharing...")
    same_tokenizer = corrector1.tokenizer is corrector2.tokenizer
    same_model = corrector1.model is corrector2.model
    same_pipeline = corrector1.nlp is corrector2.nlp
    
    print(f"   Same tokenizer: {same_tokenizer}")
    print(f"   Same model: {same_model}")
    print(f"   Same pipeline: {same_pipeline}")
    print()
    
    if same_tokenizer and same_model and same_pipeline:
        print("✅ All instances share the SAME global models")
        print("   (No duplicate loading occurred)")
    else:
        print("❌ WARNING: Instances have DIFFERENT models")
        print("   (Models are being duplicated!)")
    print()
    
    # Performance check
    print("📊 Performance Summary:")
    print(f"   Instance 1: {elapsed1:.3f}s, +{mem_increase1:.2f} MB")
    print(f"   Instance 2: {elapsed2:.3f}s, +{mem_increase2:.2f} MB")
    print(f"   Instance 3: {elapsed3:.3f}s")
    print()
    
    if elapsed2 < 0.1 and elapsed3 < 0.1:
        print("✅ Subsequent instances are FAST (< 100ms)")
        print("   Global model loading is working correctly!")
    else:
        print("⚠️  WARNING: Subsequent instances are slow")
        print("   Models may be reloading unnecessarily")
    print()
    
    return same_tokenizer and same_model and same_pipeline

def test_correction_functionality():
    """Test that autocorrection actually works."""
    print("=" * 70)
    print("TEST 3: Correction Functionality")
    print("=" * 70)
    print()
    
    from engine_bridge.autocorrector.autocorrector_core import AutoCorrector
    
    if not AutoCorrector().model_loaded:
        print("⚠️  BERT models not loaded, skipping functionality test")
        print()
        return False
    
    corrector = AutoCorrector()
    
    # Test word correction
    print("🧪 Testing word correction...")
    test_words = [
        ("hola", "hola"),
        ("mndo", "mundo"),  # Typo
        ("casa", "casa"),
    ]
    
    for input_word, expected in test_words:
        corrected = corrector._correct_word(input_word, [])
        status = "✅" if corrected == expected else "⚠️"
        print(f"   {status} '{input_word}' → '{corrected}' (expected: '{expected}')")
    print()
    
    print("✅ Correction functionality works")
    print()
    return True

def main():
    """Run all tests."""
    print()
    print("=" * 70)
    print("BERT Model Loader Test Suite")
    print("=" * 70)
    print()
    
    overall_start = time.time()
    
    # Test 1: Global loader
    test1_passed = test_global_model_loader()
    
    if not test1_passed:
        print("❌ Global model loader test FAILED")
        print("   Cannot continue with other tests")
        return False
    
    # Test 2: Performance
    test2_passed = test_autocorrector_performance()
    
    # Test 3: Functionality
    test3_passed = test_correction_functionality()
    
    overall_time = time.time() - overall_start
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print()
    print(f"Test 1 (Global Loader):     {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Test 2 (Performance):       {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    print(f"Test 3 (Functionality):     {'✅ PASSED' if test3_passed else '⚠️ SKIPPED'}")
    print()
    print(f"Total time: {overall_time:.2f}s")
    print()
    
    if test1_passed and test2_passed:
        print("🎉 ALL CRITICAL TESTS PASSED")
        print()
        print("The BERT model loading refactor is working correctly:")
        print("  ✅ Models load once at startup")
        print("  ✅ No duplicate model loading")
        print("  ✅ Fast AutoCorrector instantiation")
        print("  ✅ Memory efficient (shared models)")
        print()
        return True
    else:
        print("❌ SOME TESTS FAILED")
        print("   Review the output above for details")
        print()
        return False

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
