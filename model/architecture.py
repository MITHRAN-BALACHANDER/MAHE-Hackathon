"""ResidualSignalNet -- multi-task residual MLP for signal prediction.

Architecture:
  Input (17) -> Projection (256) -> 4x ResidualBlock(256) -> Bottleneck (64)
  -> 3 output heads (signal, drop, handoff), each with a hidden layer.

Key design choices:
  - Residual connections: enable deeper networks without vanishing gradients
  - SiLU (Swish) activation: smoother gradients than ReLU, better for regression
  - BatchNorm + moderate dropout: regularisation without being aggressive
  - Multi-task heads share the backbone: correlated outputs benefit from
    shared feature representations
  - Lightweight (< 200K params): fast inference on GPU and CPU
"""

import torch
import torch.nn as nn
from model.config import (
    INPUT_DIM, HIDDEN_DIM, RESIDUAL_BLOCKS, BOTTLENECK_DIM,
    HEAD_HIDDEN, DROPOUT, HIDDEN_DIMS,
)


class ResidualBlock(nn.Module):
    """Pre-activation residual block: BN -> SiLU -> Linear -> BN -> SiLU -> Linear + skip."""

    def __init__(self, dim: int, dropout: float = DROPOUT):
        super().__init__()
        self.block = nn.Sequential(
            nn.BatchNorm1d(dim),
            nn.SiLU(),
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(dim, dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.block(x)


class TaskHead(nn.Module):
    """Single-task output head: hidden layer + sigmoid output."""

    def __init__(self, in_dim: int, hidden: int = HEAD_HIDDEN):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.SiLU(),
            nn.Dropout(DROPOUT * 0.5),
            nn.Linear(hidden, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


class SignalNet(nn.Module):
    """Multi-head residual MLP for signal strength, drop probability, and handoff risk.

    Outputs
    -------
    signal_strength  : (B,) in [0, 1]  -- predicted normalised signal quality
    drop_probability : (B,) in [0, 1]  -- probability of call/data drop
    handoff_risk     : (B,) in [0, 1]  -- risk of problematic tower handoff
    """

    def __init__(
        self,
        input_dim: int = INPUT_DIM,
        hidden_dims: list[int] | None = None,  # kept for backward compat
        hidden_dim: int = HIDDEN_DIM,
        n_blocks: int = RESIDUAL_BLOCKS,
        bottleneck_dim: int = BOTTLENECK_DIM,
        head_hidden: int = HEAD_HIDDEN,
        dropout: float = DROPOUT,
    ):
        super().__init__()

        # Input projection
        self.projection = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.SiLU(),
        )

        # Residual backbone
        self.backbone = nn.Sequential(
            *[ResidualBlock(hidden_dim, dropout) for _ in range(n_blocks)]
        )

        # Bottleneck
        self.bottleneck = nn.Sequential(
            nn.BatchNorm1d(hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, bottleneck_dim),
            nn.BatchNorm1d(bottleneck_dim),
            nn.SiLU(),
        )

        # Task-specific heads
        self.head_signal = TaskHead(bottleneck_dim, head_hidden)
        self.head_drop = TaskHead(bottleneck_dim, head_hidden)
        self.head_handoff = TaskHead(bottleneck_dim, head_hidden)

        # Initialise weights
        self.apply(self._init_weights)

    @staticmethod
    def _init_weights(m):
        if isinstance(m, nn.Linear):
            nn.init.kaiming_normal_(m.weight, nonlinearity="linear")
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.BatchNorm1d):
            nn.init.ones_(m.weight)
            nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor):
        h = self.projection(x)
        h = self.backbone(h)
        h = self.bottleneck(h)
        signal = self.head_signal(h)
        drop = self.head_drop(h)
        handoff = self.head_handoff(h)
        return signal, drop, handoff

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
