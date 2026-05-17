"""
Import bridge for the Kronos model package.

Kronos is not pip-installable and is imported via `from model import KronosPredictor`
from the repo root. This bridge tries multiple import paths.

Usage: from kth.models._kronos_bridge import KronosPredictor
"""
import sys
from pathlib import Path
import os

# Paths to try (in order of priority)
_KRONOS_REPO = Path("./kronos_repo")


def _try_import():
    # 0. If kronos is already mocked (e.g. in verify_model_layer.py), use the mock
    if "kronos" in sys.modules:
        mock_kronos = sys.modules["kronos"]
        if hasattr(mock_kronos, "KronosPredictor"):
            return mock_kronos.KronosPredictor

    # 1. If kronos_repo/ exists locally, add it to path and import
    if _KRONOS_REPO.exists() and (_KRONOS_REPO / "model" / "__init__.py").exists():
        kronos_root = str(_KRONOS_REPO.resolve())
        if kronos_root not in sys.path:
            sys.path.insert(0, kronos_root)
        from model import KronosPredictor
        return KronosPredictor

    # 2. Check KTH_KRONOS_PATH environment variable
    env_path = os.environ.get("KTH_KRONOS_PATH", "")
    if env_path:
        env_root = Path(env_path)
        if (env_root / "model" / "__init__.py").exists():
            if str(env_root) not in sys.path:
                sys.path.insert(0, str(env_root))
            from model import KronosPredictor
            return KronosPredictor

    # 3. Try PyPI kronos (if installed as proper package)
    try:
        from kronos import KronosPredictor
        return KronosPredictor
    except ImportError:
        pass

    raise ImportError(
        "Cannot import KronosPredictor. Options:\n"
        "  1. Clone the Kronos repo to ./kronos_repo/:\n"
        "     git clone https://github.com/shiyu-coder/Kronos.git kronos_repo\n"
        "  2. Set KTH_KRONOS_PATH environment variable to the repo root\n"
        "  3. Install kronos via pip (if available as PyPI package)"
    )


KronosPredictor = _try_import()

# Also expose Tokenizer and base model for wrapper construction
def _try_import_aux():
    # If kronos is mocked, return the mock
    if "kronos" in sys.modules:
        mock_kronos = sys.modules["kronos"]
        if hasattr(mock_kronos, "KronosTokenizer") and hasattr(mock_kronos, "Kronos"):
            return mock_kronos.KronosTokenizer, mock_kronos.Kronos

    kronos_root = str(_KRONOS_REPO.resolve())
    if kronos_root not in sys.path:
        sys.path.insert(0, kronos_root)
    from model import KronosTokenizer, Kronos as KronosModel
    return KronosTokenizer, KronosModel

KronosTokenizer, Kronos = _try_import_aux()
