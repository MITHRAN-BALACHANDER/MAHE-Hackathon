"""Model inference: load trained weights and expose predict / predict_single."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch

from model.config import INPUT_DIM, WEIGHTS_PATH
from model.architecture import SignalNet

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_model: SignalNet | None = None
_device: torch.device | None = None


def _load_model():
    """Load the best model weights (lazily, once)."""
    global _model, _device
    if _model is not None:
        return

    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _model = SignalNet(input_dim=INPUT_DIM).to(_device)

    if WEIGHTS_PATH.exists():
        try:
            ckpt = torch.load(WEIGHTS_PATH, map_location=_device, weights_only=True)
            _model.load_state_dict(ckpt["model_state_dict"])
            _model.eval()
            print(f"[inference] Loaded model from {WEIGHTS_PATH} on {_device}")
        except RuntimeError as e:
            _model.eval()
            print(f"[inference] WARNING: Weights incompatible (likely INPUT_DIM changed) -- using random init. Re-train to fix. Error: {e}")
    else:
        _model.eval()
        print(f"[inference] WARNING: No weights at {WEIGHTS_PATH} -- using random init")


def predict(features: np.ndarray) -> dict:
    """Predict signal metrics for a batch of feature vectors.

    Parameters
    ----------
    features : (N, 17) float32 array

    Returns
    -------
    dict with keys:
        signal_strength  : (N,) array, 0-100 scale
        drop_probability : (N,) array, 0-1 scale
        handoff_risk     : (N,) array, 0-1 scale
    """
    _load_model()

    if features.ndim == 1:
        features = features.reshape(1, -1)

    x = torch.tensor(features, dtype=torch.float32).to(_device)
    with torch.no_grad():
        sig, drop, handoff = _model(x)

    return {
        "signal_strength": sig.cpu().numpy() * 100.0,
        "drop_probability": drop.cpu().numpy(),
        "handoff_risk": handoff.cpu().numpy(),
    }


def predict_single(features: np.ndarray) -> dict:
    """Predict for a single (17,) feature vector. Returns scalar values."""
    result = predict(features.reshape(1, -1))
    return {
        "signal_strength": float(result["signal_strength"][0]),
        "drop_probability": float(result["drop_probability"][0]),
        "handoff_risk": float(result["handoff_risk"][0]),
    }


def reload_model():
    """Force-reload the model (e.g. after re-training)."""
    global _model
    _model = None
    _load_model()
