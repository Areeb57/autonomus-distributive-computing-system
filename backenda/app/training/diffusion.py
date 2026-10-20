"""
Real PyTorch Gaussian Diffusion model, sinusoidal embeddings, noise schedules, and checkpoints.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class SinusoidalPositionalEmbedding(nn.Module):
    """Sinusoidal timestep embedding for diffusion conditioning."""

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.dim = dim

    def forward(self, timesteps: torch.Tensor) -> torch.Tensor:
        half_dim = self.dim // 2
        emb = math.log(10000) / (half_dim - 1)
        emb = torch.exp(torch.arange(half_dim, dtype=torch.float32, device=timesteps.device) * -emb)
        emb = timesteps.float()[:, None] * emb[None, :]
        emb = torch.cat([torch.sin(emb), torch.cos(emb)], dim=-1)
        if self.dim % 2 == 1:
            emb = F.pad(emb, (0, 1))
        return emb


class ResidualBlock(nn.Module):
    """Residual convolution block with timestep embedding projection."""

    def __init__(self, in_channels: int, out_channels: int, time_dim: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1)
        self.time_mlp = nn.Linear(time_dim, out_channels)
        self.residual = nn.Conv2d(in_channels, out_channels, kernel_size=1) if in_channels != out_channels else nn.Identity()
        self.norm1 = nn.GroupNorm(min(4, out_channels), out_channels)
        self.norm2 = nn.GroupNorm(min(4, out_channels), out_channels)

    def forward(self, x: torch.Tensor, time_emb: torch.Tensor) -> torch.Tensor:
        h = F.silu(self.norm1(self.conv1(x)))
        t = F.silu(self.time_mlp(time_emb))[(..., ) + (None, ) * 2]
        h = h + t
        h = F.silu(self.norm2(self.conv2(h)))
        return h + self.residual(x)


class DiffusionUNet(nn.Module):
    """
    Parametric UNet for Denoising Diffusion Probabilistic Models (DDPM).
    Supports arbitrary image channels and spatial resolutions (e.g. 1x28x28, 3x32x32, 3x64x64).
    """

    def __init__(
        self,
        in_channels: int = 3,
        out_channels: int = 3,
        base_channels: int = 32,
        time_dim: int = 64,
    ) -> None:
        super().__init__()
        self.time_embed = nn.Sequential(
            SinusoidalPositionalEmbedding(time_dim),
            nn.Linear(time_dim, time_dim),
            nn.SiLU(),
            nn.Linear(time_dim, time_dim),
        )

        # Encoder
        self.inc = nn.Conv2d(in_channels, base_channels, kernel_size=3, padding=1)
        self.down1 = ResidualBlock(base_channels, base_channels * 2, time_dim)
        self.down2 = ResidualBlock(base_channels * 2, base_channels * 4, time_dim)
        self.pool = nn.MaxPool2d(2)

        # Bottleneck
        self.bot = ResidualBlock(base_channels * 4, base_channels * 4, time_dim)

        # Decoder
        self.up1 = nn.Upsample(scale_factor=2, mode="nearest")
        self.up_conv1 = ResidualBlock(base_channels * 8, base_channels * 2, time_dim)
        self.up2 = nn.Upsample(scale_factor=2, mode="nearest")
        self.up_conv2 = ResidualBlock(base_channels * 3, base_channels, time_dim)

        self.outc = nn.Conv2d(base_channels, out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor, timesteps: torch.Tensor) -> torch.Tensor:
        t_emb = self.time_embed(timesteps)

        # Encoder
        x1 = self.inc(x)
        d1 = self.down1(x1, t_emb)
        p1 = self.pool(d1)
        d2 = self.down2(p1, t_emb)
        p2 = self.pool(d2)

        # Bottleneck
        b = self.bot(p2, t_emb)

        # Decoder with skip connections
        u1 = self.up1(b)
        # Pad if odd dimensions
        if u1.shape[-2:] != d2.shape[-2:]:
            u1 = F.interpolate(u1, size=d2.shape[-2:], mode="nearest")
        u1 = torch.cat([u1, d2], dim=1)
        u1 = self.up_conv1(u1, t_emb)

        u2 = self.up2(u1)
        if u2.shape[-2:] != x1.shape[-2:]:
            u2 = F.interpolate(u2, size=x1.shape[-2:], mode="nearest")
        u2 = torch.cat([u2, x1], dim=1)
        u2 = self.up_conv2(u2, t_emb)

        return self.outc(u2)


class GaussianDiffusion:
    """
    Gaussian Diffusion pipeline implementing forward noise schedule and MSE loss.
    """

    def __init__(
        self,
        timesteps: int = 1000,
        beta_start: float = 0.0001,
        beta_end: float = 0.02,
        device: str = "cpu",
    ) -> None:
        self.timesteps = timesteps
        self.device = device

        # Linear beta schedule
        self.betas = torch.linspace(beta_start, beta_end, timesteps, dtype=torch.float32, device=device)
        self.alphas = 1.0 - self.betas
        self.alphas_cumprod = torch.cumprod(self.alphas, dim=0)

        # Calculations for diffusion q(x_t | x_0)
        self.sqrt_alphas_cumprod = torch.sqrt(self.alphas_cumprod)
        self.sqrt_one_minus_alphas_cumprod = torch.sqrt(1.0 - self.alphas_cumprod)

    def q_sample(
        self,
        x_start: torch.Tensor,
        t: torch.Tensor,
        noise: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Diffuse data x_0 to timestep t with added Gaussian noise."""
        if noise is None:
            noise = torch.randn_like(x_start)

        sqrt_alpha_bar = self.sqrt_alphas_cumprod[t][(..., ) + (None, ) * (len(x_start.shape) - 1)]
        sqrt_one_minus_alpha_bar = self.sqrt_one_minus_alphas_cumprod[t][(..., ) + (None, ) * (len(x_start.shape) - 1)]

        noisy_samples = sqrt_alpha_bar * x_start + sqrt_one_minus_alpha_bar * noise
        return noisy_samples, noise

    def compute_loss(
        self,
        model: nn.Module,
        x_start: torch.Tensor,
        t: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Sample random timesteps, predict noise, and compute Mean Squared Error loss."""
        batch_size = x_start.shape[0]
        if t is None:
            t = torch.randint(0, self.timesteps, (batch_size,), device=x_start.device).long()

        noisy_x, target_noise = self.q_sample(x_start, t)
        predicted_noise = model(noisy_x, t)
        return F.mse_loss(predicted_noise, target_noise)


def save_checkpoint_dict(
    model: nn.Module,
    optimizer: Optional[torch.optim.Optimizer],
    step: int,
    loss: float,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build checkpoint dictionary payload."""
    payload: Dict[str, Any] = {
        "step": step,
        "loss": float(loss),
        "model_state_dict": model.state_dict(),
        "extra": extra or {},
    }
    if optimizer is not None:
        payload["optimizer_state_dict"] = optimizer.state_dict()
    return payload


def load_checkpoint_dict(
    checkpoint_path: Path | str,
    model: nn.Module,
    optimizer: Optional[torch.optim.Optimizer] = None,
) -> int:
    """
    Safely load PyTorch checkpoint with weights_only=True and restore model and optimizer state.
    Returns the step counter at which the checkpoint was saved.
    """
    path = Path(checkpoint_path)
    data = torch.load(path, map_location="cpu", weights_only=True)
    if "model_state_dict" in data:
        model.load_state_dict(data["model_state_dict"])
    else:
        # Direct weights dict
        model.load_state_dict(data)

    if optimizer is not None and "optimizer_state_dict" in data:
        optimizer.load_state_dict(data["optimizer_state_dict"])

    return data.get("step", 0)
