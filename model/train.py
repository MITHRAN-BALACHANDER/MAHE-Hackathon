"""Production training pipeline with mixed-precision, cosine annealing,
gradient clipping, multi-task loss, and proper train/val/test splits.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from model.config import (
    DATA_DIR, WEIGHTS_DIR, INPUT_DIM,
    EPOCHS, BATCH_SIZE, LR, WEIGHT_DECAY, WARMUP_EPOCHS,
    LABEL_SMOOTHING, GRAD_CLIP,
    LOSS_WEIGHT_SIGNAL, LOSS_WEIGHT_DROP, LOSS_WEIGHT_HANDOFF,
    TRAIN_SPLIT, VAL_SPLIT, TEST_SPLIT, SEED,
)
from model.architecture import SignalNet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_and_split(path: Path, seed: int = SEED):
    """Load samples.csv and return train/val/test tensor tuples."""
    df = pd.read_csv(path)
    n = len(df)
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)

    n_train = int(n * TRAIN_SPLIT)
    n_val = int(n * VAL_SPLIT)
    train_idx = perm[:n_train]
    val_idx = perm[n_train:n_train + n_val]
    test_idx = perm[n_train + n_val:]

    feat_cols = [f"f{i}" for i in range(INPUT_DIM)]
    X = df[feat_cols].values.astype(np.float32)
    y_sig = df["signal"].values.astype(np.float32)
    y_drop = df["drop_prob"].values.astype(np.float32)
    y_ho = df["handoff_risk"].values.astype(np.float32)

    def _to_tensors(idx):
        return (
            torch.tensor(X[idx]),
            torch.tensor(y_sig[idx]),
            torch.tensor(y_drop[idx]),
            torch.tensor(y_ho[idx]),
        )

    return _to_tensors(train_idx), _to_tensors(val_idx), _to_tensors(test_idx)


def smooth_labels(y: torch.Tensor, eps: float = LABEL_SMOOTHING) -> torch.Tensor:
    """Apply label smoothing: clip away from exact 0 and 1."""
    return y.clamp(eps, 1.0 - eps)


# ---------------------------------------------------------------------------
# Cosine warmup scheduler
# ---------------------------------------------------------------------------

class CosineWarmupScheduler(torch.optim.lr_scheduler._LRScheduler):
    """Linearly warm up for `warmup` epochs, then cosine decay to 0."""

    def __init__(self, optimizer, warmup: int, total: int, last_epoch: int = -1):
        self.warmup = warmup
        self.total = total
        super().__init__(optimizer, last_epoch)

    def get_lr(self):
        epoch = self.last_epoch
        if epoch < self.warmup:
            factor = (epoch + 1) / self.warmup
        else:
            progress = (epoch - self.warmup) / max(1, self.total - self.warmup)
            factor = 0.5 * (1 + np.cos(np.pi * progress))
        return [base * factor for base in self.base_lrs]


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

def train(
    epochs: int = EPOCHS,
    batch_size: int = BATCH_SIZE,
    lr: float = LR,
    patience: int = 35,
    device_name: str = "auto",
):
    """Full training run with early stopping on validation loss."""
    if device_name == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device_name)

    print(f"[train] Device: {device}")
    if device.type == "cuda":
        print(f"  GPU: {torch.cuda.get_device_name()}")

    # ---- data ----
    samples_path = DATA_DIR / "samples.csv"
    if not samples_path.exists():
        raise FileNotFoundError(f"{samples_path} not found. Run generate_data.py first.")

    (X_tr, y_sig_tr, y_drop_tr, y_ho_tr), \
    (X_va, y_sig_va, y_drop_va, y_ho_va), \
    (X_te, y_sig_te, y_drop_te, y_ho_te) = load_and_split(samples_path)

    y_sig_tr = smooth_labels(y_sig_tr)
    y_drop_tr = smooth_labels(y_drop_tr)
    y_ho_tr = smooth_labels(y_ho_tr)

    train_ds = TensorDataset(X_tr, y_sig_tr, y_drop_tr, y_ho_tr)
    val_ds = TensorDataset(X_va, y_sig_va, y_drop_va, y_ho_va)
    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True, drop_last=True)
    val_dl = DataLoader(val_ds, batch_size=batch_size * 2)

    print(f"[train] Splits: train={len(X_tr)}, val={len(X_va)}, test={len(X_te)}")

    # ---- model ----
    model = SignalNet(input_dim=INPUT_DIM).to(device)
    n_params = model.count_parameters()
    print(f"[train] Model: {n_params:,} parameters")

    # ---- losses ----
    mse = nn.MSELoss()
    bce = nn.BCELoss()

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=WEIGHT_DECAY)
    scheduler = CosineWarmupScheduler(optimizer, warmup=WARMUP_EPOCHS, total=epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    best_val_loss = float("inf")
    best_epoch = 0
    wait = 0
    history = {"train_loss": [], "val_loss": [], "lr": []}

    t0 = time.time()

    for epoch in range(1, epochs + 1):
        # ---- train ----
        model.train()
        running_loss = 0.0
        for xb, ys, yd, yh in train_dl:
            xb, ys, yd, yh = xb.to(device), ys.to(device), yd.to(device), yh.to(device)
            optimizer.zero_grad(set_to_none=True)

            with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                pred_s, pred_d, pred_h = model(xb)
                loss_sig = LOSS_WEIGHT_SIGNAL * mse(pred_s, ys)

            # BCE is unsafe under autocast -- compute in full precision
            loss_drop = LOSS_WEIGHT_DROP * bce(pred_d.float(), yd.float())
            loss_ho = LOSS_WEIGHT_HANDOFF * bce(pred_h.float(), yh.float())
            loss = loss_sig + loss_drop + loss_ho

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            scaler.step(optimizer)
            scaler.update()

            running_loss += loss.item() * xb.size(0)

        train_loss = running_loss / len(train_ds)
        scheduler.step()

        # ---- validate ----
        model.eval()
        val_running = 0.0
        with torch.no_grad():
            for xb, ys, yd, yh in val_dl:
                xb, ys, yd, yh = xb.to(device), ys.to(device), yd.to(device), yh.to(device)
                pred_s, pred_d, pred_h = model(xb)
                loss = (
                    LOSS_WEIGHT_SIGNAL * mse(pred_s, ys) +
                    LOSS_WEIGHT_DROP * bce(pred_d, yd) +
                    LOSS_WEIGHT_HANDOFF * bce(pred_h, yh)
                )
                val_running += loss.item() * xb.size(0)

        val_loss = val_running / len(val_ds)
        cur_lr = optimizer.param_groups[0]["lr"]
        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["lr"].append(cur_lr)

        improved = val_loss < best_val_loss
        if improved:
            best_val_loss = val_loss
            best_epoch = epoch
            wait = 0
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "val_loss": float(val_loss),
                "n_params": int(n_params),
            }, WEIGHTS_DIR / "best_model.pt")
        else:
            wait += 1

        if epoch <= 5 or epoch % 10 == 0 or improved or epoch == epochs:
            tag = " *" if improved else ""
            elapsed = time.time() - t0
            print(
                f"  Epoch {epoch:3d}/{epochs} | "
                f"train {train_loss:.5f} | val {val_loss:.5f} | "
                f"lr {cur_lr:.2e} | {elapsed:.0f}s{tag}"
            )

        if wait >= patience:
            print(f"[train] Early stopping at epoch {epoch} (no improvement for {patience} epochs)")
            break

    # ---- save final model ----
    torch.save({
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "val_loss": float(val_loss),
        "n_params": int(n_params),
    }, WEIGHTS_DIR / "final_model.pt")

    elapsed_total = time.time() - t0
    print(f"\n[train] Complete in {elapsed_total:.1f}s")
    print(f"  Best val loss: {best_val_loss:.5f} at epoch {best_epoch}")
    print(f"  Weights saved to {WEIGHTS_DIR}")

    # ---- quick test-set evaluation ----
    ckpt = torch.load(WEIGHTS_DIR / "best_model.pt", map_location=device, weights_only=True)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    with torch.no_grad():
        X_te_d = X_te.to(device)
        pred_s, pred_d, pred_h = model(X_te_d)
        pred_s = pred_s.cpu().numpy()
        pred_d = pred_d.cpu().numpy()
        pred_h = pred_h.cpu().numpy()

    y_sig_np = y_sig_te.numpy()
    y_drop_np = y_drop_te.numpy()
    y_ho_np = y_ho_te.numpy()

    sig_mae = float(np.mean(np.abs(pred_s - y_sig_np)))
    sig_mse = float(np.mean((pred_s - y_sig_np) ** 2))
    ss_res = np.sum((pred_s - y_sig_np) ** 2)
    ss_tot = np.sum((y_sig_np - y_sig_np.mean()) ** 2)
    sig_r2 = float(1 - ss_res / max(ss_tot, 1e-8))

    drop_acc = float(np.mean((pred_d > 0.5).astype(float) == (y_drop_np > 0.5).astype(float)))
    ho_acc = float(np.mean((pred_h > 0.5).astype(float) == (y_ho_np > 0.5).astype(float)))

    print(f"\n[train] Test-set metrics (best model):")
    print(f"  Signal MAE:  {sig_mae * 100:.2f}%")
    print(f"  Signal R2:   {sig_r2:.4f}")
    print(f"  Signal RMSE: {np.sqrt(sig_mse) * 100:.2f}%")
    print(f"  Drop acc:    {drop_acc * 100:.1f}%")
    print(f"  Handoff acc: {ho_acc * 100:.1f}%")

    return model, history


if __name__ == "__main__":
    train()
