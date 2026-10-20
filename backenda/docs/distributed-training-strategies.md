# Distributed Training Strategies, Rendezvous, and Relay Architecture (Phase 9)

## 1. Overview
Phase 9 implements real distributed training strategies for **ADC (Autonomous Distributed AI Trainer)**:
1. **Single Node Training** (`single_node`): Standard sequential execution on a single worker or master.
2. **Independent Jobs** (`independent_jobs`): Distribution of distinct trials, seed partitions, or hyperparameter sweeps among multiple workers without inter-worker gradient communication.
3. **Data-Parallel Training** (`data_parallel`): Synchronous model replication across workers with real parameter averaging (AllReduce) across steps. Supports both direct `torch.distributed` (Gloo/NCCL) and ADC's NAT-friendly **Parameter & Gradient Relay Aggregator**.
4. **Model-Parallel Pipeline Extension** (`model_parallel`): Layer-wise partitioning across nodes for explicitly supported architectures (such as `DiffusionUNet`), passing intermediate activations and backpropagating boundary activation gradients.

Simulated progress, mock gradients, and fake parameter updates are strictly prohibited. Every participating worker receives mathematically exact, synchronized tensor updates.

---

## 2. Network Topology & Firewall Requirements

Distributed nodes in ADC are often volunteer machines behind consumer NATs, corporate firewalls, or dynamic IP allocations. ADC explicitly defines the network requirements of each strategy and rejects incompatible deployments:

| Strategy | Direct Inter-Worker TCP | Inbound Ports | NAT Compatible | Min Bandwidth | Latency Overhead | Backends |
|---|---|---|---|---|---|---|
| `single_node` | No | None | Yes | 1.0 Mbps | 0.0 ms | `local` |
| `independent_jobs` | No | None | Yes | 2.0 Mbps | 0.0 ms | `independent_runner` |
| `data_parallel` (Relay) | No | None | Yes | 15.0 Mbps | 80.0 ms | `relay` |
| `data_parallel_ddp` | Yes | TCP 29500 (Rank 0) | No | 50.0 Mbps | 15.0 ms | `gloo`, `nccl` |
| `model_parallel` | No | None | Yes | 25.0 Mbps | 40.0 ms | `pipeline_relay` |

### The Volunteer NAT Problem and the ADC Relay Solution
Standard PyTorch `DistributedDataParallel` requires direct worker-to-worker TCP connectivity. When volunteer compute nodes reside on disparate residential networks:
- Direct inbound TCP ports cannot be opened without UPnP or manual router port-forwarding.
- Inbound connections are blocked by stateful NAT firewalls.

ADC solves this through the **Central Parameter & Gradient Relay Aggregator**:
- Workers initiate outbound HTTPS connections to the ADC Coordinator (`POST /api/v1/projects/{project_id}/distributed/sync`).
- No inbound firewall ports or public IP addresses are required on worker nodes.
- Synchronous AllReduce barrier ensures all active ranks submit step $\theta^{(r)}$ before the coordinator computes the mathematical mean:
  $$\bar{\theta} = \frac{1}{N} \sum_{r=0}^{N-1} \theta^{(r)}$$
- The coordinator broadcasts the exact averaged state dictionary back to all waiting workers.

### Bandwidth, Latency, and Memory Profile of Relay AllReduce
- **Coordinator Ingress**: $N \times M$ bytes per synchronized step (where $M$ is serialized model bytes and $N$ is world size).
- **Coordinator Egress**: $N \times M$ bytes per synchronized step.
- **Latency**: $\max_{r}(\text{compute\_time}_r + \text{RTT}_r) + \text{aggregation\_time}$.
- **Coordinator Working Memory**: $O(M)$ accumulator memory (streaming accumulation in CPU float32).

---

## 3. Data-Parallel Training & Rollback Recovery

### Invariant & Compatibility Validation
`DataParallelStrategy.validate_project_compatibility` enforces:
1. `num_eligible_workers >= 2`.
2. Global batch size must be greater than or equal to cluster world size.
3. Model architecture must be recognized and loadable.

### Rank Failure & Checkpoint Rollback
In synchronous data-parallel training, if rank $k$ disconnects or experiences a lease timeout:
1. The barrier aborts gracefully with a straggler timeout.
2. The coordinator marks the dead rank unhealthy.
3. If surviving ranks $\ge 2$:
   - The cluster reconfigures to world size $N - 1$.
   - Ranks are reassigned $0 \dots N - 2$.
   - Ranks are instructed to roll back to the latest validated checkpoint (`rollback_step = -1`) and resume training.
4. If surviving ranks $< 2$:
   - Data parallelism is halted, and the project pauses or prompts for additional worker capacity.

---

## 4. Model-Parallel Pipeline Partitioning

Model parallelism partitions deep neural networks across multiple nodes. Because arbitrary user Python code cannot be safely partitioned automatically without AST decomposition and dataflow analysis, ADC enforces strict architectural compatibility:

### Supported Pipeline Architecture: Partitioned Diffusion U-Net
- **`DiffusionStage0` (Rank 0)**:
  - Sinusoidal Timestep Embedding + Time MLP.
  - Residual downsampling blocks 1 and 2.
  - Generates intermediate skip tensors $(h_1, h_2)$, bottleneck input $h_b$, and timestep embedding $t_{\text{emb}}$.
- **`DiffusionStage1` (Rank 1)**:
  - Bottleneck block.
  - Residual upsampling blocks 1 and 2 with skip concatenation.
  - Output projection returning predicted noise $\hat{\epsilon}$.

### Pipeline Dataflow
1. **Forward Pass**: Rank 0 computes Stage 0 activations $\to$ passes tensors to Rank 1 $\to$ Rank 1 evaluates Stage 1 and computes MSE noise loss.
2. **Backward Pass**: Rank 1 computes Stage 1 parameter gradients and activation gradients $\frac{\partial \mathcal{L}}{\partial h}$ $\to$ passes activation gradients to Rank 0 $\to$ Rank 0 backpropagates through Stage 0 parameters.
3. Output and gradients are mathematically equivalent to monolithic `DiffusionUNet` execution.

---

## 5. REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/projects/{id}/distributed/strategies` | List strategies and network requirements |
| `POST` | `/api/v1/projects/{id}/distributed/rendezvous` | Deterministic rank assignment and rendezvous metadata |
| `POST` | `/api/v1/projects/{id}/distributed/sync` | Synchronous AllReduce parameter/gradient exchange |
| `POST` | `/api/v1/projects/{id}/distributed/heartbeat` | Report rank liveness and step progress |
| `GET` | `/api/v1/projects/{id}/distributed/status` | Query active cluster world size, ranks, and health |
