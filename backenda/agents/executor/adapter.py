"""
Stable training adapter interface, telemetry contracts, and CLI stdout reporter (Section 14).
"""

from __future__ import annotations

import json
import re
import sys
import time
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class TrainingTelemetry(BaseModel):
    """
    Standardized metrics emitted by training models during step execution.
    All non-core fields are explicitly optional to support arbitrary diffusion/ML architectures.
    """
    model_config = ConfigDict(populate_by_name=True)

    step: int = Field(..., ge=0)
    total_steps: Optional[int] = Field(None, alias="totalSteps")
    epoch: Optional[int] = None
    loss: Optional[float] = None
    val_loss: Optional[float] = Field(None, alias="valLoss")
    learning_rate: Optional[float] = Field(None, alias="learningRate")
    speed: Optional[float] = None  # Samples or steps per second
    elapsed_seconds: Optional[float] = Field(None, alias="elapsedSeconds")
    checkpoint_path: Optional[str] = Field(None, alias="checkpointPath")
    error: Optional[str] = None
    extra_metrics: Dict[str, Any] = Field(default_factory=dict, alias="extraMetrics")


class TrainingAdapter:
    """
    Parses real-time execution stdout streams to extract training telemetry.
    Supports both structured [ADC_METRIC] JSON tokens and common regex log patterns.
    """

    JSON_MARKER = "[ADC_METRIC]"
    CKPT_MARKER = "[ADC_CHECKPOINT]"

    # Fallback regex for common PyTorch/Diffusers log patterns:
    # e.g.: "step: 10/100, loss: 0.324, lr: 0.0001, speed: 12.5"
    REGEX_STEP = re.compile(r"(?:step|iteration)[:=\s]+(\d+)(?:/(\d+))?", re.IGNORECASE)
    REGEX_LOSS = re.compile(r"(?:loss|train_loss)[:=\s]+([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)", re.IGNORECASE)
    REGEX_LR = re.compile(r"(?:lr|learning_rate)[:=\s]+([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)", re.IGNORECASE)
    REGEX_SPEED = re.compile(r"(?:speed|it/s|samples/s)[:=\s]+([0-9]*\.?[0-9]+)", re.IGNORECASE)

    @classmethod
    def parse_stdout_line(cls, line: str) -> Optional[TrainingTelemetry]:
        """Inspect a single stdout line from child training process."""
        text = line.strip()
        if not text:
            return None

        # 1. Check for structured JSON marker
        if cls.JSON_MARKER in text:
            try:
                json_part = text.split(cls.JSON_MARKER, 1)[1].strip()
                data = json.loads(json_part)
                return TrainingTelemetry.model_validate(data)
            except Exception:
                pass

        # 2. Check for explicit checkpoint marker
        if cls.CKPT_MARKER in text:
            path_part = text.split(cls.CKPT_MARKER, 1)[1].strip()
            return TrainingTelemetry(step=0, checkpoint_path=path_part)

        # 3. Check for common regex step & loss logs
        step_match = cls.REGEX_STEP.search(text)
        if step_match:
            try:
                step = int(step_match.group(1))
                total_steps = int(step_match.group(2)) if step_match.group(2) else None

                loss_val = None
                loss_match = cls.REGEX_LOSS.search(text)
                if loss_match:
                    loss_val = float(loss_match.group(1))

                lr_val = None
                lr_match = cls.REGEX_LR.search(text)
                if lr_match:
                    lr_val = float(lr_match.group(1))

                speed_val = None
                speed_match = cls.REGEX_SPEED.search(text)
                if speed_match:
                    speed_val = float(speed_match.group(1))

                return TrainingTelemetry(
                    step=step,
                    total_steps=total_steps,
                    loss=loss_val,
                    learning_rate=lr_val,
                    speed=speed_val,
                )
            except (ValueError, TypeError):
                pass

        return None


class ADCReporter:
    """
    Lightweight Python helper for training scripts to report telemetry directly to ADC.
    Users can import this in their train.py or entry point.
    """

    def __init__(self, step_offset: int = 0) -> None:
        self.step_offset = step_offset
        self._start_time = time.time()

    def report_step(
        self,
        step: int,
        loss: Optional[float] = None,
        total_steps: Optional[int] = None,
        epoch: Optional[int] = None,
        learning_rate: Optional[float] = None,
        speed: Optional[float] = None,
        val_loss: Optional[float] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit step metrics to stdout with immediate flush."""
        elapsed = time.time() - self._start_time
        telemetry = TrainingTelemetry(
            step=step + self.step_offset,
            total_steps=total_steps,
            epoch=epoch,
            loss=loss,
            val_loss=val_loss,
            learning_rate=learning_rate,
            speed=speed,
            elapsed_seconds=elapsed,
            extra_metrics=extra or {},
        )
        line = f"{TrainingAdapter.JSON_MARKER} {telemetry.model_dump_json()}"
        print(line, file=sys.stdout, flush=True)

    def report_checkpoint(self, path: str, step: Optional[int] = None) -> None:
        """Emit checkpoint creation event."""
        telemetry = TrainingTelemetry(
            step=step if step is not None else 0,
            checkpoint_path=str(path),
        )
        line = f"{TrainingAdapter.JSON_MARKER} {telemetry.model_dump_json()}"
        print(line, file=sys.stdout, flush=True)
