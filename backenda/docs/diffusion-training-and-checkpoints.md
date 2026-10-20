# Diffusion Training, Checkpoints, and Resumption Architecture (Phase 8)

## 1. Overview
Phase 8 delivers real PyTorch-based diffusion model training, checkpoint persistence, streaming upload validation, and training resumption capabilities for ADC.

Simulated progress, mock metrics, and fake checkpoints are prohibited. Real neural network weights are trained, serialized, stream-uploaded, verified against corruption, and resumed inside isolated sandboxes.

---

## 2. Real Diffusion Training Engine

The diffusion training engine is located in `app/training/diffusion.py`:

### `DiffusionUNet`
A lightweight yet real PyTorch U-Net with sinusoidal timestep embeddings:
- **Sinusoidal Position Embeddings**: Transforms discrete integer timesteps $t \in [0, T-1]$ into continuous high-dimensional vectors via alternating sine/cosine frequencies.
- **Time MLP**: Projects embeddings through a two-layer MLP with SiLU activations.
- **Downsampling Path**: Multiple Conv2d blocks with residual timestep conditioning and strided convolution / pooling.
- **Bottleneck**: Deep convolutional layer fusing spatial features and time embeddings.
- **Upsampling Path**: Transposed convolutions with skip connections concatenating encoder features.
- **Output Projection**: Conv2d mapping feature maps back to target image channels.

### `GaussianDiffusion`
A linear noise scheduler implementing DDPM (Denoising Diffusion Probabilistic Models):
- **Betas and Alphas**: Configurable schedules $\beta_t \in [\beta_{\text{start}}, \beta_{\text{end}}]$, precomputing $\alpha_t = 1 - \beta_t$ and $\bar{\alpha}_t = \prod_{s=1}^t \alpha_s$.
- **Forward Diffusion (`q_sample`)**:
  $$q(x_t \mid x_0) = \sqrt{\bar{\alpha}_t} x_0 + \sqrt{1 - \bar{\alpha}_t} \epsilon, \quad \epsilon \sim \mathcal{N}(0, I)$$
- **Loss Computation (`compute_loss`)**: Evaluates mean squared error (MSE) between true noise $\epsilon$ and predicted noise $\hat{\epsilon}_\theta(x_t, t)$. Gradients backpropagate directly into U-Net parameters.

---

## 3. Streaming Upload, Integrity Verification, and Atomic Storage

Model checkpoints can be hundreds of megabytes or gigabytes in size. To prevent host memory exhaustion and protect against corrupted or malicious uploads:

### Chunked Streaming
- Received as asynchronous byte chunks (default 64 KB per chunk) directly from HTTP multipart form requests.
- Streamed directly to disk in a dedicated temporary quarantine path (`checkpoints/tmp_{uuid}.pt`).

### Cryptographic Checksum
- `hashlib.sha256()` is updated incrementally as each chunk is written.
- The resulting hex digest is recorded in database metadata and returned to clients.

### PyTorch Security & Integrity Validation
- Validated via `torch.load(temp_path, weights_only=True, map_location="cpu")`.
- `weights_only=True` prevents unpickling of arbitrary Python executable code, defending against malicious pickle payloads.
- Verifies that the file is an authentic, loadable state dictionary containing expected tensor weights and training step metadata.
- If validation fails, the temporary file is deleted immediately and a `ValidationError` (HTTP 400) is returned.

### Atomic Publication
- Only upon passing validation is the file atomically moved (`temp_path.replace(final_path)`) into permanent storage:
  `{storage_root}/checkpoints/{project_id}/{checkpoint_id}.pt`.
- A database record in `checkpoints` is created with `is_validated = True`.

---

## 4. Checkpoint Resumption Protocol

Training can be resumed from any validated checkpoint:

1. **API Trigger**:
   - `POST /api/v1/projects/{project_id}/checkpoints/{checkpoint_id}/resume`
   - Authorized only for the project owner.
   - Updates `TrainingRun.current_step = checkpoint.step` and resets run status to `running`.
2. **Worker Launcher Resumption**:
   - When a worker claims a training task, it queries `GET /api/v1/projects/{project_id}/checkpoints/latest`.
   - If a validated checkpoint exists:
     1. The worker downloads the checkpoint file stream to a local path.
     2. Sets `TaskExecutionConfig.resume_checkpoint_path = downloaded_path`.
     3. Sandboxed child process receives `ADC_RESUME_CHECKPOINT=/path/to/checkpoint.pt` and `ADC_STEP_START={checkpoint.step}`.
     4. Training script calls `load_checkpoint_dict(resume_ckpt, model, optimizer)` and continues training towards target steps.

---

## 5. REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/projects/{id}/checkpoints` | Stream upload and validate checkpoint |
| `GET` | `/api/v1/projects/{id}/checkpoints` | List all validated checkpoints |
| `GET` | `/api/v1/projects/{id}/checkpoints/latest` | Retrieve latest checkpoint metadata |
| `GET` | `/api/v1/projects/{id}/checkpoints/{cid}/download` | Stream download checkpoint weights |
| `POST` | `/api/v1/projects/{id}/checkpoints/{cid}/resume` | Restore project run to checkpoint step |
