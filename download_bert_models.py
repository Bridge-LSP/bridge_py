"""
Helper script to download BERT models for Docker packaging.

This script downloads the BERT model to a local cache directory,
which can then be copied into the Docker image to avoid network
access during container startup in Cloud Run.

Usage:
    python download_bert_models.py
    
This will download models to ./hf-cache/ which can be packaged in Docker:
    COPY hf-cache /app/hf-cache
"""

import os
import sys
from pathlib import Path

MODEL_NAME = "dccuchile/bert-base-spanish-wwm-uncased"
CACHE_DIR = "./hf-cache"

def download_models():
    """Download BERT models to local cache directory."""
    print("=" * 70)
    print("BERT Model Downloader for Docker Packaging")
    print("=" * 70)
    print()
    print(f"Model: {MODEL_NAME}")
    print(f"Cache directory: {CACHE_DIR}")
    print()
    
    cache_path = Path(CACHE_DIR)
    cache_path.mkdir(parents=True, exist_ok=True)
    print(f"✅ Cache directory ready: {cache_path.absolute()}")
    print()
    
    try:
        print("📦 Importing transformers library...")
        from transformers import AutoTokenizer, AutoModelForMaskedLM
        print("✅ Transformers imported successfully")
        print()
        
        print(f"⬇️  Downloading tokenizer: {MODEL_NAME}")
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            cache_dir=CACHE_DIR
        )
        print("✅ Tokenizer downloaded successfully")
        print()
        
        print(f"⬇️  Downloading model: {MODEL_NAME}")
        print("   (This may take a few minutes on first run...)")
        model = AutoModelForMaskedLM.from_pretrained(
            MODEL_NAME,
            cache_dir=CACHE_DIR
        )
        print("✅ Model downloaded successfully")
        print()
        
        print("📂 Verifying downloaded files...")
        cache_contents = list(cache_path.rglob("*"))
        file_count = len([f for f in cache_contents if f.is_file()])
        total_size = sum(f.stat().st_size for f in cache_contents if f.is_file())
        total_size_mb = total_size / (1024 * 1024)
        
        print(f"   Files: {file_count}")
        print(f"   Total size: {total_size_mb:.2f} MB")
        print()
        
        print("🧪 Testing local-only loading...")
        tokenizer_test = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            cache_dir=CACHE_DIR,
            local_files_only=True
        )
        model_test = AutoModelForMaskedLM.from_pretrained(
            MODEL_NAME,
            cache_dir=CACHE_DIR,
            local_files_only=True
        )
        print("✅ Local-only loading works correctly")
        print()
        
        print("=" * 70)
        print("🎉 SUCCESS! Models are ready for Docker packaging")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. Add to your Dockerfile:")
        print(f"   COPY {CACHE_DIR} /app/hf-cache")
        print()
        print("2. Set environment variable in Cloud Run:")
        print("   ENV=prod")
        print()
        print("3. (Optional) Set custom cache directory:")
        print("   HF_CACHE_DIR=/app/hf-cache")
        print()
        
        return True
        
    except Exception as e:
        print()
        print("=" * 70)
        print("❌ ERROR: Failed to download models")
        print("=" * 70)
        print(f"Error: {e}")
        print()
        print("Troubleshooting:")
        print("1. Check internet connection")
        print("2. Verify transformers library is installed:")
        print("   pip install transformers")
        print("3. Try manually:")
        print(f"   python -c 'from transformers import AutoTokenizer; AutoTokenizer.from_pretrained(\"{MODEL_NAME}\")'")
        print()
        return False


if __name__ == "__main__":
    success = download_models()
    sys.exit(0 if success else 1)
