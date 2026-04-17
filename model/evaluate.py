"""Comprehensive model evaluation: per-zone metrics, edge-case analysis,
confusion matrices, feature correlations, and summary report.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import torch

from model.config import (
    DATA_DIR, WEIGHTS_DIR, INPUT_DIM, SEED,
    TRAIN_SPLIT, VAL_SPLIT,
)
from model.architecture import SignalNet


def load_test_data(seed: int = SEED):
    """Load samples.csv and return only the test split as numpy arrays."""
    df = pd.read_csv(DATA_DIR / "samples.csv")
    n = len(df)
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)

    n_train = int(n * TRAIN_SPLIT)
    n_val = int(n * VAL_SPLIT)
    test_idx = perm[n_train + n_val:]

    feat_cols = [f"f{i}" for i in range(INPUT_DIM)]
    X = df[feat_cols].values[test_idx].astype(np.float32)
    y_sig = df["signal"].values[test_idx].astype(np.float32)
    y_drop = df["drop_prob"].values[test_idx].astype(np.float32)
    y_ho = df["handoff_risk"].values[test_idx].astype(np.float32)
    return X, y_sig, y_drop, y_ho


def predict_all(model, X: np.ndarray, device: torch.device):
    """Run model inference on full array and return numpy predictions."""
    model.eval()
    with torch.no_grad():
        xt = torch.tensor(X, dtype=torch.float32).to(device)
        s, d, h = model(xt)
    return s.cpu().numpy(), d.cpu().numpy(), h.cpu().numpy()


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray, name: str) -> dict:
    """Compute MAE, MSE, RMSE, R2 for a regression target."""
    err = y_pred - y_true
    mae = float(np.mean(np.abs(err)))
    mse = float(np.mean(err ** 2))
    rmse = float(np.sqrt(mse))
    ss_res = np.sum(err ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    r2 = float(1 - ss_res / max(ss_tot, 1e-8))
    return {"task": name, "MAE": mae, "MSE": mse, "RMSE": rmse, "R2": r2}


def binary_metrics(y_true: np.ndarray, y_pred: np.ndarray, name: str, threshold: float = 0.5):
    """Accuracy, precision, recall, F1 for a binary classification target."""
    yt = (y_true > threshold).astype(int)
    yp = (y_pred > threshold).astype(int)
    tp = int(np.sum((yp == 1) & (yt == 1)))
    fp = int(np.sum((yp == 1) & (yt == 0)))
    fn = int(np.sum((yp == 0) & (yt == 1)))
    tn = int(np.sum((yp == 0) & (yt == 0)))
    acc = (tp + tn) / max(tp + tn + fp + fn, 1)
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-8)
    return {
        "task": name,
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "confusion": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
    }


def signal_bucket_analysis(y_true: np.ndarray, y_pred: np.ndarray):
    """Break signal predictions into quality buckets for per-bucket analysis."""
    buckets = [
        ("Dead  (0-15%)", 0.00, 0.15),
        ("Poor  (15-35%)", 0.15, 0.35),
        ("Fair  (35-55%)", 0.35, 0.55),
        ("Good  (55-75%)", 0.55, 0.75),
        ("Great (75-100%)", 0.75, 1.01),
    ]
    rows = []
    for label, lo, hi in buckets:
        mask = (y_true >= lo) & (y_true < hi)
        n = int(mask.sum())
        if n == 0:
            rows.append({"bucket": label, "n": 0, "MAE": 0, "RMSE": 0})
            continue
        e = y_pred[mask] - y_true[mask]
        rows.append({
            "bucket": label,
            "n": n,
            "MAE": round(float(np.mean(np.abs(e))) * 100, 2),
            "RMSE": round(float(np.sqrt(np.mean(e ** 2))) * 100, 2),
        })
    return rows


def edge_zone_analysis(X: np.ndarray, y_sig: np.ndarray, pred_sig: np.ndarray):
    """Evaluate signal prediction specifically for edge-zone samples (f9 > 0)."""
    mask = X[:, 9] > 0  # terrain_type feature encodes edge-zone
    n = int(mask.sum())
    if n == 0:
        return {"n": 0, "note": "No edge-zone samples in test set"}
    err = pred_sig[mask] - y_sig[mask]
    return {
        "n": n,
        "MAE": round(float(np.mean(np.abs(err))) * 100, 2),
        "RMSE": round(float(np.sqrt(np.mean(err ** 2))) * 100, 2),
        "mean_actual": round(float(y_sig[mask].mean()) * 100, 2),
        "mean_predicted": round(float(pred_sig[mask].mean()) * 100, 2),
    }


def feature_correlation(X: np.ndarray, y: np.ndarray) -> list[tuple[str, float]]:
    """Pearson correlation between each feature and the target."""
    names = [
        "dist_nearest", "dist_2nd", "dist_3rd", "towers_500m", "towers_1km",
        "towers_2km", "avg_sig_nearby", "max_sig_nearby", "road_type",
        "terrain_type", "freq_norm", "time_sin", "time_cos", "weather",
        "speed_norm", "nearest_sig", "load_factor",
    ]
    corrs = []
    for i, name in enumerate(names):
        r = float(np.corrcoef(X[:, i], y)[0, 1]) if np.std(X[:, i]) > 1e-8 else 0.0
        corrs.append((name, round(r, 4)))
    corrs.sort(key=lambda x: abs(x[1]), reverse=True)
    return corrs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def evaluate(model_path: str | None = None):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Load model
    if model_path is None:
        model_path = str(WEIGHTS_DIR / "best_model.pt")
    ckpt = torch.load(model_path, map_location=device, weights_only=True)
    model = SignalNet(input_dim=INPUT_DIM).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    print(f"[eval] Loaded model from {model_path} (epoch {ckpt.get('epoch', '?')})")

    # Load data
    X, y_sig, y_drop, y_ho = load_test_data()
    print(f"[eval] Test samples: {len(X)}")

    # Predict
    pred_s, pred_d, pred_h = predict_all(model, X, device)

    # --- Overall metrics ---
    print("\n=== Signal Regression ===")
    sig_m = regression_metrics(y_sig, pred_s, "signal")
    print(f"  MAE:  {sig_m['MAE'] * 100:.2f}%")
    print(f"  RMSE: {sig_m['RMSE'] * 100:.2f}%")
    print(f"  R2:   {sig_m['R2']:.4f}")

    print("\n=== Drop Probability (binary @ 0.5) ===")
    drop_m = binary_metrics(y_drop, pred_d, "drop")
    print(f"  Accuracy:  {drop_m['accuracy'] * 100:.1f}%")
    print(f"  Precision: {drop_m['precision'] * 100:.1f}%")
    print(f"  Recall:    {drop_m['recall'] * 100:.1f}%")
    print(f"  F1:        {drop_m['f1'] * 100:.1f}%")
    c = drop_m["confusion"]
    print(f"  Confusion: TP={c['TP']}, FP={c['FP']}, FN={c['FN']}, TN={c['TN']}")

    print("\n=== Handoff Risk (binary @ 0.5) ===")
    ho_m = binary_metrics(y_ho, pred_h, "handoff")
    print(f"  Accuracy:  {ho_m['accuracy'] * 100:.1f}%")
    print(f"  Precision: {ho_m['precision'] * 100:.1f}%")
    print(f"  Recall:    {ho_m['recall'] * 100:.1f}%")
    print(f"  F1:        {ho_m['f1'] * 100:.1f}%")
    c = ho_m["confusion"]
    print(f"  Confusion: TP={c['TP']}, FP={c['FP']}, FN={c['FN']}, TN={c['TN']}")

    # --- Per-bucket analysis ---
    print("\n=== Signal Quality Buckets ===")
    buckets = signal_bucket_analysis(y_sig, pred_s)
    for b in buckets:
        print(f"  {b['bucket']}  n={b['n']:5d}  MAE={b['MAE']:.2f}%  RMSE={b['RMSE']:.2f}%")

    # --- Edge-zone analysis ---
    print("\n=== Edge-Zone Analysis ===")
    ez = edge_zone_analysis(X, y_sig, pred_s)
    if ez["n"] > 0:
        print(f"  Samples:  {ez['n']}")
        print(f"  MAE:      {ez['MAE']:.2f}%")
        print(f"  RMSE:     {ez['RMSE']:.2f}%")
        print(f"  Mean actual:    {ez['mean_actual']:.1f}%")
        print(f"  Mean predicted: {ez['mean_predicted']:.1f}%")
    else:
        print(f"  {ez.get('note', 'N/A')}")

    # --- Feature importance ---
    print("\n=== Feature Correlation with Signal (|r|) ===")
    corrs = feature_correlation(X, y_sig)
    for name, r in corrs:
        bar = "#" * int(abs(r) * 50)
        print(f"  {name:17s}  {r:+.4f}  {bar}")

    print("\n[eval] Done.")
    return {
        "signal": sig_m,
        "drop": drop_m,
        "handoff": ho_m,
        "buckets": buckets,
        "edge_zone": ez,
        "feature_corr": corrs,
    }


if __name__ == "__main__":
    evaluate()
