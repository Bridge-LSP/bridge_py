"""
Global BERT Model Loader - Production Safe

This module loads Hugging Face BERT models with:
- Automatic cache fallback (local → network)
- Lazy background initialization (non-blocking startup)
- Health endpoint support
- Hard stop on catastrophic errors

Usage:
    from engine_bridge.bert_model_loader import get_bert_tokenizer, get_bert_model, get_bert_pipeline, is_loading
    
    if not is_loading():
        tokenizer = get_bert_tokenizer()
        model = get_bert_model()
        pipeline = get_bert_pipeline()
"""

import os
import logging
import time
import threading
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

MODEL_NAME = "dccuchile/bert-base-spanish-wwm-uncased"
DEFAULT_CACHE_DIR = "./hf-cache"  # Development default
PRODUCTION_CACHE_DIR = "/app/hf-cache"  # Production container path

# Retry configuration
MAX_RETRIES = 3
RETRY_INTERVAL_SECONDS = 1.0

# Detect environment
ENV = os.environ.get("ENV", "dev").lower()
IS_PRODUCTION = ENV in ("prod", "production")

# Determine cache directory
if IS_PRODUCTION:
    CACHE_DIR = os.environ.get("HF_CACHE_DIR", PRODUCTION_CACHE_DIR)
else:
    CACHE_DIR = os.environ.get("HF_CACHE_DIR", DEFAULT_CACHE_DIR)

logger.info(f"[BERT MODEL LOADER] Environment: {ENV}")
logger.info(f"[BERT MODEL LOADER] Production mode: {IS_PRODUCTION}")
logger.info(f"[BERT MODEL LOADER] Cache directory: {CACHE_DIR}")

# ============================================================================
# GLOBAL MODEL INSTANCES (loaded once)
# ============================================================================

_TOKENIZER: Optional[object] = None
_MODEL: Optional[object] = None
_PIPELINE: Optional[object] = None
_LOAD_SUCCESS: bool = False
_LOAD_ERROR: Optional[str] = None
_LOADING: bool = False
_NETWORK_FALLBACK_USED: bool = False
_LOADING_MODE: str = "not-started"  # "not-started" | "loading" | "cache-only" | "network-fallback" | "failed"

# ============================================================================
# MODEL LOADING FUNCTIONS
# ============================================================================

def _ensure_cache_dir_exists():
    """Create cache directory if it doesn't exist."""
    cache_path = Path(CACHE_DIR)
    if not cache_path.exists():
        logger.info(f"[BERT MODEL LOADER] Creating cache directory: {CACHE_DIR}")
        try:
            cache_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"[BERT MODEL LOADER] Could not create cache dir: {e}")


def _attempt_model_load(local_files_only: bool, attempt_num: int) -> bool:
    """
    Attempt to load BERT models with given configuration.
    
    Args:
        local_files_only: Whether to restrict to local cache only
        attempt_num: Current attempt number (for logging)
    
    Returns:
        True if successful, False otherwise
    
    Raises:
        Exception: Only on catastrophic non-recoverable errors
    """
    global _TOKENIZER, _MODEL, _PIPELINE, _LOAD_SUCCESS, _LOAD_ERROR, _LOADING_MODE, _NETWORK_FALLBACK_USED
    
    try:
        from transformers import AutoTokenizer, AutoModelForMaskedLM, pipeline
        
        load_kwargs = {
            "cache_dir": CACHE_DIR,
            "local_files_only": local_files_only
        }
        
        mode_str = "cache-only" if local_files_only else "network-enabled"
        logger.info(f"[BERT MODEL LOADER] Attempt {attempt_num}: Loading with mode={mode_str}")
        
        # Load tokenizer
        logger.info(f"[BERT MODEL LOADER] Loading tokenizer...")
        _TOKENIZER = AutoTokenizer.from_pretrained(MODEL_NAME, **load_kwargs)
        logger.info("[BERT MODEL LOADER] ✅ Tokenizer loaded")
        
        # Load model
        logger.info(f"[BERT MODEL LOADER] Loading model...")
        _MODEL = AutoModelForMaskedLM.from_pretrained(MODEL_NAME, **load_kwargs)
        logger.info("[BERT MODEL LOADER] ✅ Model loaded")
        
        # Create pipeline
        logger.info("[BERT MODEL LOADER] Creating pipeline...")
        _PIPELINE = pipeline('fill-mask', model=_MODEL, tokenizer=_TOKENIZER)
        logger.info("[BERT MODEL LOADER] ✅ Pipeline created")
        
        _LOAD_SUCCESS = True
        _LOADING_MODE = "cache-only" if local_files_only else "network-fallback"
        
        if not local_files_only:
            _NETWORK_FALLBACK_USED = True
            logger.warning("[BERT MODEL LOADER] ⚠️  Network fallback was used to load models")
        else:
            logger.info("[BERT MODEL LOADER] 🎉 Models loaded from local cache")
        
        return True
        
    except (FileNotFoundError, OSError) as e:
        # Cache miss or file system error
        error_str = str(e)
        if "429" in error_str or "rate" in error_str.lower():
            logger.warning(f"[BERT MODEL LOADER] Attempt {attempt_num}: Rate limit detected")
            _LOAD_ERROR = f"HuggingFace rate limit (429): {error_str}"
        elif local_files_only:
            logger.warning(f"[BERT MODEL LOADER] Attempt {attempt_num}: Cache miss - {error_str}")
            _LOAD_ERROR = f"Cache miss: {error_str}"
        else:
            logger.warning(f"[BERT MODEL LOADER] Attempt {attempt_num}: File error - {error_str}")
            _LOAD_ERROR = f"File error: {error_str}"
        return False
        
    except Exception as e:
        # Network errors, timeouts, connection issues
        error_str = str(e)
        error_type = type(e).__name__
        
        if "timeout" in error_str.lower():
            logger.warning(f"[BERT MODEL LOADER] Attempt {attempt_num}: Timeout - {error_str}")
            _LOAD_ERROR = f"Timeout: {error_str}"
        elif "connection" in error_str.lower():
            logger.warning(f"[BERT MODEL LOADER] Attempt {attempt_num}: Connection error - {error_str}")
            _LOAD_ERROR = f"Connection error: {error_str}"
        else:
            logger.warning(f"[BERT MODEL LOADER] Attempt {attempt_num}: {error_type} - {error_str}")
            _LOAD_ERROR = f"{error_type}: {error_str}"
        
        return False


def _load_models_with_fallback():
    """
    Load BERT models with automatic cache → network fallback.
    
    Strategy:
    1. Try local_files_only=True first (cache only)
    2. If that fails, retry with local_files_only=False (network allowed)
    3. Retry up to MAX_RETRIES times with RETRY_INTERVAL_SECONDS delay
    4. On catastrophic failure, raise exception (hard stop)
    """
    global _LOAD_SUCCESS, _LOAD_ERROR, _LOADING, _LOADING_MODE
    
    _LOADING = True
    _LOADING_MODE = "loading"
    
    try:
        logger.info(f"[BERT MODEL LOADER] 🚀 Starting model load: {MODEL_NAME}")
        _ensure_cache_dir_exists()
        
        # PHASE 1: Try cache-only mode first
        logger.info("[BERT MODEL LOADER] PHASE 1: Attempting cache-only load...")
        if _attempt_model_load(local_files_only=True, attempt_num=1):
            _LOADING_MODE = "cache-only"
            _LOADING = False
            logger.info("[BERT MODEL LOADER] 🎉 SUCCESS: Models loaded from cache")
            return
        
        # PHASE 2: Cache failed, try network fallback with retries
        logger.warning("[BERT MODEL LOADER] PHASE 2: Cache failed, attempting network fallback...")
        
        for attempt in range(1, MAX_RETRIES + 1):
            logger.info(f"[BERT MODEL LOADER] Network fallback attempt {attempt}/{MAX_RETRIES}")
            
            if _attempt_model_load(local_files_only=False, attempt_num=attempt + 1):
                _LOADING_MODE = "network-fallback"
                _LOADING = False
                logger.info(f"[BERT MODEL LOADER] 🎉 SUCCESS: Models loaded via network (attempt {attempt})")
                return
            
            if attempt < MAX_RETRIES:
                logger.info(f"[BERT MODEL LOADER] Retrying in {RETRY_INTERVAL_SECONDS}s...")
                time.sleep(RETRY_INTERVAL_SECONDS)
        
        # PHASE 3: All retries exhausted - CATASTROPHIC FAILURE
        _LOADING_MODE = "failed"
        _LOADING = False
        _LOAD_SUCCESS = False
        
        error_msg = (
            f"[BERT MODEL LOADER] ❌ CRITICAL: BERT model loading FAILED after {MAX_RETRIES} retries\n"
            f"  Model: {MODEL_NAME}\n"
            f"  Cache: {CACHE_DIR}\n"
            f"  Last error: {_LOAD_ERROR}\n\n"
            f"  Possible causes:\n"
            f"  1. Cache directory empty AND network unavailable\n"
            f"  2. HuggingFace rate limiting (429 errors)\n"
            f"  3. No internet connection\n"
            f"  4. Transformers library not installed\n\n"
            f"  SOLUTION:\n"
            f"  - Ensure models are pre-cached: python download_bert_models.py\n"
            f"  - Check network connectivity\n"
            f"  - Verify transformers library: pip install transformers\n"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)
        
    except RuntimeError:
        # Re-raise our own runtime errors
        raise
    except Exception as e:
        # Unexpected catastrophic error
        _LOADING = False
        _LOADING_MODE = "failed"
        _LOAD_SUCCESS = False
        _LOAD_ERROR = str(e)
        
        error_msg = (
            f"[BERT MODEL LOADER] ❌ CRITICAL: Unexpected error during model loading\n"
            f"  Error: {e}\n"
        )
        logger.error(error_msg, exc_info=True)
        raise RuntimeError(error_msg) from e


def _background_load_models():
    """Background thread function for lazy model loading."""
    try:
        _load_models_with_fallback()
    except Exception as e:
        logger.error(f"[BERT MODEL LOADER] Background loading failed: {e}")
        # Don't raise - let the status endpoint report the error


# ============================================================================
# PUBLIC API
# ============================================================================

def get_bert_tokenizer():
    """
    Get the global BERT tokenizer instance.
    
    Returns:
        Tokenizer instance, or None if loading failed/incomplete
    """
    return _TOKENIZER


def get_bert_model():
    """
    Get the global BERT model instance.
    
    Returns:
        Model instance, or None if loading failed/incomplete
    """
    return _MODEL


def get_bert_pipeline():
    """
    Get the global BERT fill-mask pipeline instance.
    
    Returns:
        Pipeline instance, or None if loading failed/incomplete
    """
    return _PIPELINE


def is_bert_available() -> bool:
    """
    Check if BERT models were loaded successfully.
    
    Returns:
        True if models are available, False otherwise
    """
    return _LOAD_SUCCESS and not _LOADING


def is_loading() -> bool:
    """
    Check if BERT models are currently being loaded.
    
    Returns:
        True if loading in progress, False otherwise
    """
    return _LOADING


def get_load_error() -> Optional[str]:
    """
    Get the error message if model loading failed.
    
    Returns:
        Error message string, or None if loading succeeded
    """
    return _LOAD_ERROR


def get_model_info() -> Dict[str, any]:
    """
    Get comprehensive information about the loaded models.
    
    Returns:
        Dictionary with model metadata, status, and diagnostics
    """
    return {
        "model_name": MODEL_NAME,
        "cache_dir": CACHE_DIR,
        "environment": ENV,
        "is_production": IS_PRODUCTION,
        "loaded": _LOAD_SUCCESS and not _LOADING,
        "loading": _LOADING,
        "mode": _LOADING_MODE,
        "network_fallback_used": _NETWORK_FALLBACK_USED,
        "error": _LOAD_ERROR,
        "tokenizer_loaded": _TOKENIZER is not None,
        "model_loaded": _MODEL is not None,
        "pipeline_loaded": _PIPELINE is not None,
    }


def start_background_loading():
    """
    Start loading BERT models in a background thread.
    This allows FastAPI to start immediately without blocking.
    """
    global _LOADING
    
    if _LOADING:
        logger.warning("[BERT MODEL LOADER] Loading already in progress")
        return
    
    if _LOAD_SUCCESS:
        logger.info("[BERT MODEL LOADER] Models already loaded")
        return
    
    logger.info("[BERT MODEL LOADER] 🚀 Starting background model loading...")
    thread = threading.Thread(target=_background_load_models, daemon=True)
    thread.start()


# ============================================================================
# INITIALIZATION
# ============================================================================

# DO NOT auto-load at import time - wait for explicit start_background_loading() call
logger.info("[BERT MODEL LOADER] ⏳ Module initialized - awaiting background load trigger")
logger.info(f"[BERT MODEL LOADER] Model: {MODEL_NAME}")
logger.info(f"[BERT MODEL LOADER] Cache: {CACHE_DIR}")
logger.info(f"[BERT MODEL LOADER] Environment: {ENV} (production={IS_PRODUCTION})")
