#!/usr/bin/env python3
"""
ADC local agent with best-effort machine resource profiling.

Run:
    python adc_agent.py
    python adc_agent.py --role worker

Status endpoint:
    http://127.0.0.1:8765/agent/status

Optional:
    pip install psutil
    On NVIDIA systems, install NVIDIA drivers/tools so `nvidia-smi` is available.
    On AMD ROCm systems, install ROCm tools so `rocm-smi` is available.

Notes:
- Hardware detection is best-effort and varies by operating system/driver.
- Internet upload/download throughput cannot be measured honestly without a
  reachable speed-test server. Those fields remain null unless a future
  dedicated test endpoint is configured; they are not fabricated.
- Network latency/loss are measured against a reachable public DNS endpoint
  when possible. This is a diagnostic, not a guarantee of internet quality.
"""

import argparse
import asyncio
import json
import os
import platform
import re
import secrets
import ssl
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "0.5.0"
VALID_ROLES = ("none", "master", "worker")
DEFAULT_ORIGINS = (
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:5174", "http://127.0.0.1:5174",
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:5175", "http://127.0.0.1:5175",
    "http://localhost:4173", "http://127.0.0.1:4173",
)

try:
    import psutil  # Optional, recommended for accurate CPU/RAM/disk metrics.
except ImportError:
    psutil = None


def _run(command, timeout=2.0):
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout,
            check=False, errors="replace"
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _gb(value):
    return round(value / (1024 ** 3), 2) if value is not None else None


def _cpu_info():
    model = platform.processor().strip() or "Unknown"
    architecture = platform.machine().strip() or "Unknown"
    physical = None
    logical = os.cpu_count() or 1

    if psutil:
        try:
            physical = psutil.cpu_count(logical=False)
            logical = psutil.cpu_count(logical=True) or logical
        except Exception:
            pass

    system = platform.system()
    if system == "Linux":
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            if model == "Unknown":
                match = re.search(r"^(?:model name|Hardware|Processor)\s*:\s*(.+)$", text, re.M | re.I)
                if match:
                    model = match.group(1).strip()
            physical_ids = set(re.findall(r"^physical id\s*:\s*(\d+)", text, re.M))
            core_pairs = set(re.findall(r"^physical id\s*:\s*(\d+)\s*$.*?^core id\s*:\s*(\d+)", text, re.M | re.S))
            if core_pairs:
                physical = len(core_pairs)
            elif physical_ids and physical is None:
                # Topology unavailable; do not pretend socket count is core count.
                physical = None
        except OSError:
            pass
    elif system == "Windows":
        output = _run([
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name"
        ])
        if output:
            model = output.splitlines()[0].strip()
        if physical is None:
            out = _run([
                "powershell", "-NoProfile", "-Command",
                "(Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum"
            ])
            try:
                physical = int(out) if out else None
            except ValueError:
                pass
    elif system == "Darwin":
        out = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        if out:
            model = out.strip()
        out = _run(["sysctl", "-n", "hw.physicalcpu"])
        try:
            physical = int(out) if out else None
        except ValueError:
            pass

    return model, architecture, physical, logical


def _memory_info():
    total = available = None
    if psutil:
        try:
            vm = psutil.virtual_memory()
            return _gb(vm.total), _gb(vm.available)
        except Exception:
            pass

    if platform.system() == "Linux":
        values = {}
        try:
            with open("/proc/meminfo", "r", encoding="ascii") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        values[parts[0].rstrip(":")] = int(parts[1]) * 1024
            total = values.get("MemTotal")
            available = values.get("MemAvailable")
        except (OSError, ValueError):
            pass
    elif platform.system() == "Windows":
        out = _run([
            "powershell", "-NoProfile", "-Command",
            "$m=Get-CimInstance Win32_OperatingSystem; "
            "[math]::Round($m.TotalVisibleMemorySize*1KB);"
            "[math]::Round($m.FreePhysicalMemory*1KB)"
        ])
        if out:
            lines = out.splitlines()
            try:
                total, available = int(lines[0]), int(lines[1])
            except (ValueError, IndexError):
                pass
    elif platform.system() == "Darwin":
        out = _run(["sysctl", "-n", "hw.memsize"])
        try:
            total = int(out) if out else None
        except ValueError:
            pass
        vm = _run(["vm_stat"])
        if vm:
            page = re.search(r"page size of (\d+) bytes", vm)
            free_pages = re.search(r"Pages free:\s+(\d+)", vm)
            inactive_pages = re.search(r"Pages inactive:\s+(\d+)", vm)
            speculative_pages = re.search(r"Pages speculative:\s+(\d+)", vm)
            if page:
                page_size = int(page.group(1))
                available = sum(int(m.group(1)) for m in (free_pages, inactive_pages, speculative_pages) if m) * page_size
    return _gb(total), _gb(available)


def _gpu_info():
    """Return (vendor, model, backend, total_vram_gb, free_vram_gb)."""
    # NVIDIA: nvidia-smi provides reliable device and VRAM readings.
    out = _run([
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.free",
        "--format=csv,noheader,nounits"
    ], timeout=2.5)
    if out:
        first = out.splitlines()[0].split(",")
        if len(first) >= 3:
            name = first[0].strip()
            total_mb, free_mb = _number(first[1].strip()), _number(first[2].strip())
            return "NVIDIA", name, "CUDA", round(total_mb / 1024, 2) if total_mb is not None else None, round(free_mb / 1024, 2) if free_mb is not None else None

    # AMD ROCm.
    out = _run(["rocm-smi", "--showproductname", "--showmeminfo", "vram", "--json"], timeout=3.0)
    if out:
        try:
            data = json.loads(out)
            flat = json.dumps(data)
            name_match = re.search(r"Card series:\s*([^,}]+)", flat, re.I)
            total_match = re.search(r"VRAM Total Memory \(B\)[^0-9]*(\d+)", flat, re.I)
            used_match = re.search(r"VRAM Total Used Memory \(B\)[^0-9]*(\d+)", flat, re.I)
            name = name_match.group(1).strip('" ') if name_match else "AMD GPU (ROCm)"
            total = int(total_match.group(1)) if total_match else None
            used = int(used_match.group(1)) if used_match else None
            free = total - used if total is not None and used is not None else None
            return "AMD", name, "ROCm", _gb(total), _gb(free)
        except (ValueError, TypeError):
            pass

    # macOS: Metal is the OS GPU API; system_profiler can identify the GPU.
    if platform.system() == "Darwin":
        out = _run(["system_profiler", "SPDisplaysDataType"], timeout=4.0)
        if out:
            chip = re.search(r"Chipset Model:\s*(.+)", out)
            vendor = "Apple" if "Apple" in (chip.group(1) if chip else "") else "Unknown"
            name = chip.group(1).strip() if chip else "GPU detected; model unavailable"
            mem = re.search(r"VRAM \(Total\):\s*(\d+)\s*MB", out, re.I)
            total = round(int(mem.group(1)) / 1024, 2) if mem else None
            return vendor, name, "Metal", total, None

    # Windows fallback: identify a GPU but do not guess VRAM/backend.
    if platform.system() == "Windows":
        out = _run([
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object -First 1 -ExpandProperty Name"
        ])
        if out:
            name = out.splitlines()[0].strip()
            vendor = "NVIDIA" if "nvidia" in name.lower() else "AMD" if any(x in name.lower() for x in ("amd", "radeon")) else "Intel" if "intel" in name.lower() else "Unknown"
            backend = "CUDA" if vendor == "NVIDIA" else "ROCm" if vendor == "AMD" else "Unknown"
            return vendor, name, backend, None, None

    # Linux fallback: lspci may identify a device without giving VRAM.
    out = _run(["sh", "-c", "command -v lspci >/dev/null 2>&1 && lspci"])
    if out:
        lines = [line for line in out.splitlines() if re.search(r"VGA compatible controller|3D controller|Display controller", line, re.I)]
        if lines:
            line = lines[0]
            vendor = "NVIDIA" if "nvidia" in line.lower() else "AMD" if any(x in line.lower() for x in ("amd", "ati", "radeon")) else "Intel" if "intel" in line.lower() else "Unknown"
            backend = "CUDA" if vendor == "NVIDIA" else "ROCm" if vendor == "AMD" else "Unknown"
            return vendor, line.split(":", 2)[-1].strip(), backend, None, None

    return "Unknown", "Not detected", "Not detected", None, None


def _disk_info():
    # Use the volume containing the agent's working directory (or system drive).
    target = os.path.abspath(os.getcwd())
    if platform.system() == "Windows":
        target = os.environ.get("SystemDrive", "C:") + "\\"
    try:
        usage = shutil.disk_usage(target)
        return _gb(usage.total), _gb(usage.free)
    except OSError:
        try:
            usage = shutil.disk_usage(os.path.expanduser("~"))
            return _gb(usage.total), _gb(usage.free)
        except OSError:
            return None, None


def _ping_once(host="1.1.1.1"):
    """Return latency in ms or None. Uses native ping and a short timeout."""
    system = platform.system()
    if system == "Windows":
        cmd = ["ping", "-n", "1", "-w", "900", host]
    else:
        cmd = ["ping", "-c", "1", "-W", "1", host]
    start = time.monotonic()
    output = _run(cmd, timeout=1.5)
    if output is None:
        return None
    match = re.search(r"time[=<]\s*([\d.]+)\s*ms", output, re.I)
    if match:
        return float(match.group(1))
    # A successful ping can report sub-millisecond latency as <1ms.
    if re.search(r"TTL=\d+", output, re.I):
        return max(0.1, (time.monotonic() - start) * 1000)
    return None


class AgentState:
    """Thread-safe role and cached machine telemetry."""

    def __init__(self, role="none", website_url=None, master_port=8766, registration_token=None, project_id=None, master_bind_host="0.0.0.0", tls_cert=None, tls_key=None):
        self._lock = threading.RLock()
        self._role = role
        self._started_at = time.time()
        self._agent_id = str(uuid.uuid4())
        self.website_url = (website_url or "").rstrip("/")
        self.master_port = int(master_port)
        self.master_bind_host = master_bind_host
        self.tls_cert = tls_cert
        self.tls_key = tls_key
        self.registration_token = registration_token
        # This token is sent to the website over HTTPS and must be returned only to approved workers.
        self.connection_token = secrets.token_urlsafe(32)
        self.connected_workers = {}
        self._ws_server_thread = None
        self._worker_thread = None
        self._worker_connection = {"url": None, "projectId": None, "authToken": None}
        self._ws_status = "stopped"
        self._ws_error = None
        # WebRTC uses the website only for signaling; data travels peer-to-peer
        # when the two networks can establish a direct ICE path.
        self._rtc_status = "stopped"
        self._rtc_error = None
        self._rtc_thread = None  # retained for compatibility with early 0.5 builds
        self._rtc_master_thread = None
        self._rtc_worker_thread = None
        self._rtc_peers = {}
        self._rtc_lock = threading.RLock()
        self._rtc_worker_config = None
        self.project_id = project_id
        self.public_ip = None
        self.registration_status = "not_configured" if not self.website_url else "not_registered"
        self.registration_error = None
        self._registration_lock = threading.Lock()
        self._connection_started = None
        self._connection_last_success = None
        self._ping_samples = []
        self._cpu_utilization = None
        self._cpu_capacity = None
        self._last_net_check = None
        self._network_up = False
        self._stop = threading.Event()

        self.cpu_model, self.cpu_architecture, self.physical_cores, self.logical_cores = _cpu_info()
        self.total_ram, self.available_ram = _memory_info()
        self.gpu_vendor, self.gpu_model, self.gpu_backend, self.total_vram, self.available_vram = _gpu_info()
        self.total_disk, self.available_disk = _disk_info()
        self.os_name = platform.system() or "Unknown"
        self.os_version = platform.version() or platform.release() or "Unknown"
        self.compatibility_status, self.compatibility_details = self._compatibility()

        self._sampler = threading.Thread(target=self._sample_loop, daemon=True)
        self._sampler.start()

    @property
    def role(self):
        with self._lock:
            return self._role

    def set_role(self, role, project_id=None):
        if role not in VALID_ROLES:
            raise ValueError(f"invalid role: {role!r}")
        with self._lock:
            self._role = role
            if project_id:
                self.project_id = str(project_id)
        if role == "master":
            self.start_master_websocket()
            threading.Thread(target=self.register_master, daemon=True).start()
            self.start_master_webrtc_signaling()
        elif role != "worker":
            self._ws_status = "stopped"
            self._rtc_status = "stopped"

    def _discover_public_ip(self):
        """Ask an external IP echo service; never substitute a private LAN IP."""
        request = urllib.request.Request(
            "https://api.ipify.org",
            headers={"User-Agent": f"ADC-Agent/{VERSION}"},
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            value = response.read(128).decode("ascii", errors="strict").strip()
        # Validate IPv4 or IPv6 and return the canonical string.
        return str(__import__("ipaddress").ip_address(value))

    def register_master(self):
        """Send the master's public address and planned worker port to the website."""
        if not self.website_url:
            with self._lock:
                self.registration_status = "not_configured"
                self.registration_error = "Website URL is not configured; use --website-url or ADC_WEBSITE_URL."
            print("[ADC] Master registration skipped: website URL is not configured.", flush=True)
            return
        if not (1 <= self.master_port <= 65535):
            with self._lock:
                self.registration_status = "failed"
                self.registration_error = "Master port must be between 1 and 65535."
            return
        if not self._registration_lock.acquire(blocking=False):
            return
        try:
            with self._lock:
                self.registration_status = "registering"
                self.registration_error = None
            public_ip = self._discover_public_ip()
            with self._lock:
                self.public_ip = public_ip
                project_id = self.project_id
            payload = {
                "agentId": self._agent_id,
                "projectId": project_id,
                "role": "master",
                "publicIp": public_ip,
                "masterPort": self.master_port,
                "hostname": socket.gethostname(),
                "protocol": "wss" if self.tls_cert and self.tls_key else "ws",
                "connectionToken": self.connection_token,
                "agentVersion": VERSION,
                "supportsWebRTC": True,
                "connectionMode": "webrtc-first",
                "signalingProtocol": "http-polling-v1",
            }
            body = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if self.registration_token:
                headers["Authorization"] = f"Bearer {self.registration_token}"
            endpoint = self.website_url + "/api/masters/register"
            request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(request, timeout=12) as response:
                response_body = response.read(4096).decode("utf-8", errors="replace")
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"Website returned HTTP {response.status}")
            with self._lock:
                self.registration_status = "registered"
                self.registration_error = None
            print(f"[ADC] Master address registered: {public_ip}:{self.master_port}", flush=True)
            if response_body.strip():
                print(f"[ADC] Website response: {response_body[:500]}", flush=True)
        except (OSError, urllib.error.URLError, ValueError, RuntimeError) as exc:
            message = str(exc) or exc.__class__.__name__
            with self._lock:
                self.registration_status = "failed"
                self.registration_error = message[:500]
            print(f"[ADC] Master registration failed: {message}", file=sys.stderr, flush=True)
        finally:
            self._registration_lock.release()

    def start_master_websocket(self):
        """Start the receiver/listener so many workers can share one port."""
        if self._ws_server_thread and self._ws_server_thread.is_alive():
            return
        self._ws_status = "starting"
        self._ws_server_thread = threading.Thread(target=self._master_ws_thread, daemon=True)
        self._ws_server_thread.start()

    def _master_ws_thread(self):
        try:
            import websockets
        except ImportError:
            self._ws_status = "dependency_missing"
            self._ws_error = "Install WebSocket dependency with: pip install websockets"
            print(f"[ADC] {self._ws_error}", file=sys.stderr, flush=True)
            return

        async def handler(websocket, path=None):
            remote = getattr(websocket, "remote_address", None)
            worker_id = None
            try:
                async for raw in websocket:
                    try:
                        message = json.loads(raw)
                    except (TypeError, json.JSONDecodeError):
                        await websocket.send(json.dumps({"type": "error", "error": "invalid_json"}))
                        continue
                    if not isinstance(message, dict):
                        await websocket.send(json.dumps({"type": "error", "error": "message_must_be_object"}))
                        continue
                    if message.get("type") in ("worker_hello", "worker_status"):
                        supplied_token = message.get("authToken")
                        if not secrets.compare_digest(str(supplied_token or ""), self.connection_token):
                            await websocket.send(json.dumps({"type": "error", "error": "unauthorized"}))
                            await websocket.close(code=1008, reason="unauthorized")
                            return
                        incoming_project = message.get("projectId")
                        if self.project_id is not None and str(incoming_project) != str(self.project_id):
                            await websocket.send(json.dumps({"type": "error", "error": "wrong_project"}))
                            await websocket.close(code=1008, reason="wrong project")
                            return
                        worker_id = str(message.get("workerId") or message.get("agentId") or uuid.uuid4())
                        details = message.get("details") if isinstance(message.get("details"), dict) else {}
                        worker_record = {
                            "workerId": worker_id,
                            "projectId": message.get("projectId"),
                            "remoteAddress": str(remote[0]) if remote else None,
                            "connected": True,
                            "lastSeen": time.time(),
                            "details": details,
                        }
                        with self._lock:
                            self.connected_workers[worker_id] = worker_record
                        await websocket.send(json.dumps({"type": "welcome", "workerId": worker_id, "projectId": self.project_id}))
                        print(f"[ADC] Worker connected: {worker_id} from {worker_record['remoteAddress']}", flush=True)
                        self._post_worker_update(worker_record)
                    elif message.get("type") == "heartbeat":
                        worker_id = str(message.get("workerId") or "unknown")
                        with self._lock:
                            if worker_id in self.connected_workers:
                                self.connected_workers[worker_id]["lastSeen"] = time.time()
                        await websocket.send(json.dumps({"type": "heartbeat_ack", "time": time.time()}))
                    else:
                        await websocket.send(json.dumps({"type": "ack", "received": message.get("type", "unknown")}))
            except Exception as exc:
                print(f"[ADC] WebSocket client ended: {exc}", flush=True)
            finally:
                # A disconnect is reflected in the next dashboard status poll.
                if worker_id:
                    with self._lock:
                        record = self.connected_workers.get(worker_id)
                        if record:
                            record["connected"] = False
                            record["lastSeen"] = time.time()

        async def run_server():
            ssl_context = None
            if self.tls_cert and self.tls_key:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(self.tls_cert, self.tls_key)
            try:
                async with websockets.serve(
                    handler, self.master_bind_host, self.master_port,
                    ssl=ssl_context, ping_interval=20, ping_timeout=20,
                    max_size=1_048_576,
                ):
                    self._ws_status = "listening"
                    protocol = "wss" if ssl_context else "ws"
                    print(f"[ADC] Master WebSocket receiver listening on {protocol}://{self.master_bind_host}:{self.master_port}", flush=True)
                    await asyncio.to_thread(self._stop.wait)
            except OSError as exc:
                self._ws_status = "failed"
                self._ws_error = str(exc)
                print(f"[ADC] Could not start master WebSocket listener on port {self.master_port}: {exc}", file=sys.stderr, flush=True)

        try:
            asyncio.run(run_server())
        except Exception as exc:
            self._ws_status = "failed"
            self._ws_error = str(exc)
            print(f"[ADC] Master WebSocket server failed: {exc}", file=sys.stderr, flush=True)

    def _website_json(self, method, path, payload=None, timeout=12):
        """Call the website's signaling API and decode its JSON response."""
        if not self.website_url:
            raise RuntimeError("Website URL is not configured; WebRTC signaling needs the website API")
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json", "User-Agent": f"ADC-Agent/{VERSION}"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.registration_token:
            headers["Authorization"] = f"Bearer {self.registration_token}"
        request = urllib.request.Request(self.website_url + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1_000_000).decode("utf-8", errors="replace")
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Website returned HTTP {response.status}")
        if not raw.strip():
            return {}
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise RuntimeError("Signaling endpoint must return a JSON object")
        return result

    def _post_rtc_signal(self, target_agent_id, signal_id, signal_type, sdp, project_id, auth_token, extra=None):
        payload = {
            "targetAgentId": target_agent_id,
            "fromAgentId": self._agent_id,
            "signalId": signal_id,
            "signalType": signal_type,
            "sdp": sdp,
            "projectId": project_id,
            "authToken": auth_token,
        }
        if extra:
            payload.update(extra)
        return self._website_json("POST", "/api/webrtc/signals", payload, timeout=15)

    def start_master_webrtc_signaling(self):
        """Poll the website for worker offers; no inbound master port is needed."""
        if not self.website_url:
            self._rtc_status = "not_configured"
            self._rtc_error = "Set ADC_WEBSITE_URL or --website-url to enable WebRTC signaling."
            return
        if self._rtc_master_thread and self._rtc_master_thread.is_alive():
            return
        self._rtc_status = "waiting_for_offers"
        self._rtc_master_thread = threading.Thread(target=self._master_webrtc_thread, daemon=True)
        self._rtc_master_thread.start()

    def _master_webrtc_thread(self):
        try:
            from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
        except ImportError:
            self._rtc_status = "dependency_missing"
            self._rtc_error = "Install WebRTC dependency with: pip install aiortc"
            print(f"[ADC] {self._rtc_error}", file=sys.stderr, flush=True)
            return

        async def wait_ice_gathering(pc, timeout=15):
            deadline = time.monotonic() + timeout
            while pc.iceGatheringState != "complete" and time.monotonic() < deadline:
                await asyncio.sleep(0.1)

        async def handle_offer(signal):
            signal_id = str(signal.get("signalId") or "")
            worker_id = str(signal.get("fromAgentId") or signal.get("workerId") or "")
            incoming_project = signal.get("projectId")
            supplied_token = str(signal.get("authToken") or "")
            if not signal_id or not worker_id or not signal.get("sdp"):
                print("[ADC] Ignoring incomplete WebRTC offer from signaling service.", flush=True)
                return
            if not secrets.compare_digest(supplied_token, self.connection_token):
                print(f"[ADC] Rejected WebRTC offer from {worker_id}: invalid project token.", flush=True)
                return
            if self.project_id is not None and str(incoming_project) != str(self.project_id):
                print(f"[ADC] Rejected WebRTC offer from {worker_id}: wrong project.", flush=True)
                return
            with self._rtc_lock:
                if signal_id in self._rtc_peers:
                    return
            pc = RTCPeerConnection(RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")]))
            with self._rtc_lock:
                self._rtc_peers[signal_id] = {"pc": pc, "workerId": worker_id, "channel": None}

            @pc.on("datachannel")
            def on_datachannel(channel):
                with self._rtc_lock:
                    if signal_id in self._rtc_peers:
                        self._rtc_peers[signal_id]["channel"] = channel

                @channel.on("message")
                def on_message(raw):
                    try:
                        message = json.loads(raw) if isinstance(raw, str) else {}
                    except json.JSONDecodeError:
                        return
                    if not isinstance(message, dict):
                        return
                    kind = message.get("type")
                    if kind in ("worker_hello", "worker_status"):
                        details = message.get("details") if isinstance(message.get("details"), dict) else {}
                        record = {
                            "workerId": worker_id,
                            "projectId": incoming_project,
                            "transport": "webrtc",
                            "connected": True,
                            "lastSeen": time.time(),
                            "details": details,
                        }
                        with self._lock:
                            self.connected_workers[worker_id] = record
                        try:
                            channel.send(json.dumps({"type": "welcome", "workerId": worker_id, "projectId": self.project_id}))
                        except Exception:
                            pass
                        self._post_worker_update(record)
                    elif kind == "heartbeat":
                        with self._lock:
                            if worker_id in self.connected_workers:
                                self.connected_workers[worker_id]["lastSeen"] = time.time()
                        try:
                            channel.send(json.dumps({"type": "heartbeat_ack", "time": time.time()}))
                        except Exception:
                            pass

            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                if pc.connectionState in ("failed", "closed", "disconnected"):
                    with self._lock:
                        record = self.connected_workers.get(worker_id)
                        if record:
                            record["connected"] = False
                            record["lastSeen"] = time.time()
                    if pc.connectionState in ("failed", "closed"):
                        with self._rtc_lock:
                            self._rtc_peers.pop(signal_id, None)
                        await pc.close()

            try:
                await pc.setRemoteDescription(RTCSessionDescription(sdp=signal["sdp"], type="offer"))
                answer = await pc.createAnswer()
                await pc.setLocalDescription(answer)
                await wait_ice_gathering(pc)
                await asyncio.to_thread(
                    self._post_rtc_signal, worker_id, signal_id, "answer",
                    pc.localDescription.sdp, incoming_project, self.connection_token,
                )
                self._rtc_status = "connected_or_negotiating"
                print(f"[ADC] Sent WebRTC answer to worker {worker_id}; waiting for direct ICE connection.", flush=True)
            except Exception as exc:
                self._rtc_error = str(exc)[:500]
                print(f"[ADC] Could not answer WebRTC offer: {exc}", file=sys.stderr, flush=True)
                with self._rtc_lock:
                    self._rtc_peers.pop(signal_id, None)
                await pc.close()

        async def poll_loop():
            self._rtc_status = "waiting_for_offers"
            while not self._stop.is_set() and self.role == "master":
                try:
                    query = urllib.parse.urlencode({"agentId": self._agent_id, "role": "master"})
                    result = await asyncio.to_thread(self._website_json, "GET", "/api/webrtc/signals/poll?" + query, None, 10)
                    signals = result.get("signals", [])
                    if isinstance(signals, list):
                        for signal in signals:
                            if isinstance(signal, dict) and signal.get("signalType") == "offer":
                                await handle_offer(signal)
                except Exception as exc:
                    self._rtc_error = str(exc)[:500]
                    self._rtc_status = "signaling_error"
                await asyncio.sleep(2)
            self._rtc_status = "stopped"

        try:
            asyncio.run(poll_loop())
        except Exception as exc:
            self._rtc_status = "failed"
            self._rtc_error = str(exc)[:500]
            print(f"[ADC] Master WebRTC signaling stopped: {exc}", file=sys.stderr, flush=True)

    def connect_worker_webrtc(self, master_agent_id, project_id=None, auth_token=None):
        if not self.website_url:
            raise ValueError("Website URL is required for WebRTC signaling")
        if not isinstance(master_agent_id, str) or not master_agent_id.strip():
            raise ValueError("masterAgentId is required; resolve the 9-digit code through the website first")
        if not auth_token:
            raise ValueError("authToken is required; website must return the project's worker connection token")
        self._rtc_worker_config = {
            "masterAgentId": master_agent_id.strip(),
            "projectId": project_id,
            "authToken": str(auth_token),
        }
        self.set_role("worker", project_id=project_id)
        if self._rtc_worker_thread and self._rtc_worker_thread.is_alive():
            return
        self._rtc_worker_thread = threading.Thread(target=self._worker_webrtc_thread, daemon=True)
        self._rtc_worker_thread.start()

    def _worker_webrtc_thread(self):
        try:
            from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
        except ImportError:
            self._rtc_status = "dependency_missing"
            self._rtc_error = "Install WebRTC dependency with: pip install aiortc"
            print(f"[ADC] {self._rtc_error}", file=sys.stderr, flush=True)
            return

        async def wait_ice_gathering(pc, timeout=15):
            deadline = time.monotonic() + timeout
            while pc.iceGatheringState != "complete" and time.monotonic() < deadline:
                await asyncio.sleep(0.1)

        async def client_loop():
            config = self._rtc_worker_config or {}
            self._rtc_status = "connecting"
            worker_id = self._agent_id
            while not self._stop.is_set():
                pc = RTCPeerConnection(RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")]))
                signal_id = str(uuid.uuid4())
                channel = pc.createDataChannel("adc-control")
                try:
                    offer = await pc.createOffer()
                    await pc.setLocalDescription(offer)
                    await wait_ice_gathering(pc)
                    await asyncio.to_thread(
                        self._post_rtc_signal, config["masterAgentId"], signal_id, "offer",
                        pc.localDescription.sdp, config.get("projectId"), config.get("authToken"),
                        {"workerId": worker_id},
                    )
                    print(f"[ADC] Sent WebRTC offer for project {config.get('projectId')} via website signaling.", flush=True)
                    answer = None
                    deadline = time.monotonic() + 90
                    while not self._stop.is_set() and time.monotonic() < deadline and answer is None:
                        query = urllib.parse.urlencode({"agentId": worker_id, "role": "worker", "signalId": signal_id})
                        result = await asyncio.to_thread(self._website_json, "GET", "/api/webrtc/signals/poll?" + query, None, 10)
                        for signal in result.get("signals", []):
                            if isinstance(signal, dict) and signal.get("signalId") == signal_id and signal.get("signalType") == "answer":
                                answer = signal
                                break
                        if answer is None:
                            await asyncio.sleep(2)
                    if answer is None:
                        raise TimeoutError("Timed out waiting for the master's WebRTC answer")
                    await pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type="answer"))
                    self._rtc_status = "negotiating"
                    opened = asyncio.Event()

                    @channel.on("open")
                    def on_open():
                        opened.set()
                        self._rtc_status = "connected"
                        self._rtc_error = None
                        channel.send(json.dumps({
                            "type": "worker_hello", "workerId": worker_id,
                            "projectId": config.get("projectId"), "details": self.snapshot(),
                        }))
                        print("[ADC] Direct WebRTC data channel connected to master.", flush=True)

                    @channel.on("message")
                    def on_message(raw):
                        try:
                            message = json.loads(raw) if isinstance(raw, str) else {}
                        except json.JSONDecodeError:
                            return
                        if isinstance(message, dict) and message.get("type") == "error":
                            self._rtc_error = str(message.get("error", "peer_error"))

                    @pc.on("connectionstatechange")
                    async def on_connectionstatechange():
                        if pc.connectionState in ("failed", "closed"):
                            self._rtc_status = "disconnected"

                    try:
                        await asyncio.wait_for(opened.wait(), timeout=90)
                        while not self._stop.is_set() and pc.connectionState not in ("failed", "closed"):
                            await asyncio.sleep(10)
                            if channel.readyState == "open":
                                channel.send(json.dumps({"type": "worker_status", "workerId": worker_id,
                                    "projectId": config.get("projectId"), "details": self.snapshot()}))
                    except asyncio.TimeoutError:
                        raise TimeoutError("WebRTC data channel did not open; direct NAT traversal may have failed")
                except Exception as exc:
                    self._rtc_status = "disconnected"
                    self._rtc_error = str(exc)[:500]
                    print(f"[ADC] WebRTC connection attempt failed: {exc}; retrying in 8 seconds", flush=True)
                finally:
                    await pc.close()
                if not self._stop.is_set():
                    await asyncio.sleep(8)

        try:
            asyncio.run(client_loop())
        except Exception as exc:
            self._rtc_status = "failed"
            self._rtc_error = str(exc)[:500]

    def connect_worker(self, websocket_url=None, project_id=None, auth_token=None, master_agent_id=None):
        """Start a WebRTC peer or legacy WebSocket client after code resolution."""
        if master_agent_id:
            self.connect_worker_webrtc(master_agent_id, project_id=project_id, auth_token=auth_token)
            return
        if not isinstance(websocket_url, str) or not websocket_url.startswith(("ws://", "wss://")):
            raise ValueError("websocketUrl must start with ws:// or wss://")
        if not auth_token:
            raise ValueError("authToken is required; the website must return the project's worker connection token")
        self._worker_connection = {"url": websocket_url, "projectId": project_id, "authToken": auth_token}
        self.set_role("worker", project_id=project_id)
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._worker_thread = threading.Thread(target=self._worker_ws_thread, daemon=True)
        self._worker_thread.start()

    def _worker_ws_thread(self):
        try:
            import websockets
        except ImportError:
            self._ws_status = "dependency_missing"
            self._ws_error = "Install WebSocket dependency with: pip install websockets"
            print(f"[ADC] {self._ws_error}", file=sys.stderr, flush=True)
            return

        async def client_loop():
            config = self._worker_connection
            url = config["url"]
            self._ws_status = "connecting"
            while not self._stop.is_set():
                try:
                    async with websockets.connect(url, ping_interval=20, ping_timeout=20, max_size=1_048_576) as websocket:
                        self._ws_status = "connected"
                        print(f"[ADC] Connected to master WebSocket: {url}", flush=True)
                        worker_id = self._agent_id
                        hello = {
                            "type": "worker_hello",
                            "workerId": worker_id,
                            "agentId": self._agent_id,
                            "projectId": config.get("projectId"),
                            "authToken": config.get("authToken"),
                            "details": self.snapshot(),
                        }
                        await websocket.send(json.dumps(hello))

                        async def send_status_periodically():
                            while not self._stop.is_set():
                                await asyncio.sleep(10)
                                await websocket.send(json.dumps({
                                    "type": "worker_status", "workerId": worker_id,
                                    "projectId": config.get("projectId"),
                                    "authToken": config.get("authToken"),
                                    "details": self.snapshot(),
                                }))

                        status_task = asyncio.create_task(send_status_periodically())
                        try:
                            async for raw in websocket:
                                try:
                                    message = json.loads(raw)
                                except (TypeError, json.JSONDecodeError):
                                    continue
                                if message.get("type") == "error":
                                    self._ws_error = str(message.get("error", "websocket_error"))
                                    print(f"[ADC] Master rejected message: {self._ws_error}", file=sys.stderr, flush=True)
                                    if self._ws_error == "unauthorized":
                                        return
                        finally:
                            status_task.cancel()
                            await asyncio.gather(status_task, return_exceptions=True)
                        self._ws_status = "disconnected"
                except Exception as exc:
                    self._ws_status = "disconnected"
                    self._ws_error = str(exc)[:500]
                    print(f"[ADC] Master connection unavailable: {exc}; retrying in 5 seconds", flush=True)
                    await asyncio.sleep(5)

        try:
            asyncio.run(client_loop())
        except Exception as exc:
            self._ws_status = "failed"
            self._ws_error = str(exc)

    def _post_worker_update(self, worker_record):
        """Best-effort dashboard update; backend must implement this endpoint."""
        if not self.website_url:
            return
        try:
            payload = {
                "agentId": self._agent_id,
                "projectId": self.project_id,
                "worker": worker_record,
                "event": "worker_connected",
            }
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if self.registration_token:
                headers["Authorization"] = f"Bearer {self.registration_token}"
            request = urllib.request.Request(
                self.website_url + "/api/masters/workers/update",
                data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                response.read(1024)
        except Exception as exc:
            print(f"[ADC] Website worker-status update not delivered (endpoint may not exist yet): {exc}", flush=True)

    def _compatibility(self):
        details = []
        if sys.version_info < (3, 8):
            details.append("Python 3.8 or newer is required.")
        if not (self.logical_cores and self.logical_cores > 0):
            details.append("CPU core count could not be detected.")
        if self.total_ram is None:
            details.append("RAM capacity could not be detected.")
        if not details:
            details.append("Basic agent checks passed; training-framework/GPU compatibility must be checked per project.")
            return "compatible_basic", details
        return "needs_attention", details

    def _sample_loop(self):
        # psutil's first CPU sample is not meaningful; prime it before the loop.
        if psutil:
            try:
                psutil.cpu_percent(interval=None)
            except Exception:
                pass
        while not self._stop.wait(2.0):
            try:
                if psutil:
                    cpu = float(psutil.cpu_percent(interval=None))
                else:
                    cpu = None
                total_ram, available_ram = _memory_info()
                total_disk, available_disk = _disk_info()
                latency = _ping_once()
                now = time.time()
                with self._lock:
                    self._cpu_utilization = round(cpu, 1) if cpu is not None else None
                    self._cpu_capacity = round(max(0.0, 100.0 - cpu), 1) if cpu is not None else None
                    self.available_ram = available_ram
                    self.total_ram = total_ram
                    self.total_disk, self.available_disk = total_disk, available_disk
                    self._last_net_check = now
                    self._network_up = latency is not None
                    if latency is not None:
                        if self._connection_started is None:
                            self._connection_started = now
                        self._connection_last_success = now
                    self._ping_samples.append(latency is not None)
                    self._ping_samples = self._ping_samples[-30:]
                    self._ping_latency = latency
            except Exception:
                # A telemetry failure must not stop the local agent.
                continue

    def snapshot(self):
        with self._lock:
            samples = list(self._ping_samples)
            stability = (
                f"{round(100 * sum(samples) / len(samples))}% successful checks (last {len(samples)})"
                if samples else "Measuring connectivity"
            )
            connection_uptime = (
                int(time.time() - self._connection_started)
                if self._connection_started is not None and self._network_up else 0
            )
            payload = {
                "agent": "adc-agent",
                "agentId": self._agent_id,
                "publicIp": self.public_ip,
                "masterPort": self.master_port,
                "registrationStatus": self.registration_status,
                "registrationError": self.registration_error,
                "websocketStatus": self._ws_status,
                "websocketError": self._ws_error,
                "webrtcStatus": self._rtc_status,
                "webrtcError": self._rtc_error,
                "webrtcConnectedPeers": len(self._rtc_peers),
                "connectedWorkers": list(self.connected_workers.values()) if self._role == "master" else [],
                "userId": None,
                "machineId": None,
                "workerId": None,
                "projectId": self.project_id,
                "version": VERSION,
                "role": self._role,
                "hostname": socket.gethostname(),
                "platform": f"{self.os_name} {self.os_version}",
                "osName": self.os_name,
                "osVersion": self.os_version,
                "cpuModel": self.cpu_model,
                "cpuArchitecture": self.cpu_architecture,
                "physicalCpuCores": self.physical_cores,
                "logicalCpuCores": self.logical_cores,
                "cpuCores": self.logical_cores,
                "cpuUtilizationPercent": self._cpu_utilization,
                "availableCpuCapacityPercent": self._cpu_capacity,
                "totalRamGB": self.total_ram,
                "availableRamGB": self.available_ram,
                "gpuVendor": self.gpu_vendor,
                "gpuModel": self.gpu_model,
                "gpuComputeBackend": self.gpu_backend,
                "totalGpuMemoryGB": self.total_vram,
                "availableGpuMemoryGB": self.available_vram,
                "totalDiskGB": self.total_disk,
                "availableDiskGB": self.available_disk,
                # Deliberately null: meaningful throughput requires a speed-test endpoint.
                "networkUploadMbps": None,
                "networkDownloadMbps": None,
                "networkLatencyMs": getattr(self, "_ping_latency", None),
                "packetLossPercent": (
                    round(100 * (1 - sum(samples) / len(samples)), 1) if samples else None
                ),
                "connectionStability": stability,
                "connectionUptimeSeconds": connection_uptime,
                "workerCompatibilityStatus": self.compatibility_status,
                "workerCompatibilityDetails": list(self.compatibility_details),
                "uptimeSeconds": int(time.time() - self._started_at),
                "metricsNotes": {
                    "cpuUtilizationPercent": "Live sample; may be null until the first sampler cycle.",
                    "gpuMemory": "VRAM readings depend on installed GPU vendor tools/drivers.",
                    "disk": "Measures the volume containing the current working directory (system drive on Windows).",
                    "networkSpeed": "Upload/download throughput is null because no dedicated speed-test server is configured.",
                    "networkLatency": "Ping to 1.1.1.1; unavailable if ICMP/ping is blocked.",
                    "compatibility": "Basic Python/CPU/RAM checks only; project-specific framework compatibility is not guaranteed."
                }
            }
            return payload

    def close(self):
        self._stop.set()
        self._ws_status = "stopping"


def _is_allowed_origin(origin, allowed_origins):
    if not origin:
        return False
    if origin in allowed_origins:
        return True
    try:
        parsed = urllib.parse.urlsplit(origin)
        if parsed.scheme in ("http", "https") and parsed.hostname in ("localhost", "127.0.0.1"):
            return True
    except Exception:
        pass
    return False


def make_handler(state, allowed_origins):
    class Handler(BaseHTTPRequestHandler):
        server_version = f"ADCAgent/{VERSION}"

        def log_message(self, *_args):
            pass

        def _send_cors(self):
            origin = self.headers.get("Origin")
            if origin and _is_allowed_origin(origin, allowed_origins):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

        def _send_json(self, code, payload):
            body = json.dumps(payload).encode("utf-8")
            try:
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self._send_cors()
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_OPTIONS(self):
            self.send_response(204)
            self._send_cors()
            self.send_header("Access-Control-Max-Age", "600")
            self.end_headers()

        def do_POST(self):
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path not in ("/agent/role", "/agent/connect"):
                self._send_json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 16_384:
                    self._send_json(400, {"error": "request body must be 1-16384 bytes"})
                    return
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("JSON body must be an object")
                if path == "/agent/connect":
                    try:
                        state.connect_worker(
                            payload.get("websocketUrl"),
                            project_id=payload.get("projectId"),
                            auth_token=payload.get("authToken"),
                            master_agent_id=payload.get("masterAgentId"),
                        )
                    except ValueError as exc:
                        self._send_json(400, {"error": str(exc)})
                        return
                    self._send_json(200, {"ok": True, "message": "Worker WebRTC/WebSocket connection starting", **state.snapshot()})
                    return
                role = payload.get("role")
                if role not in VALID_ROLES:
                    self._send_json(400, {"error": "role must be none, master, or worker"})
                    return
                project_id = payload.get("projectId")
                if project_id is not None and not isinstance(project_id, (str, int)):
                    self._send_json(400, {"error": "projectId must be a string or integer"})
                    return
                state.set_role(role, project_id=project_id)
                self._send_json(200, {"ok": True, **state.snapshot()})
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._send_json(400, {"error": str(exc)})

        def do_GET(self):
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path in ("/agent/status", "/agent/role"):
                self._send_json(200, state.snapshot())
            elif path == "/":
                self._send_json(200, {"agent": "adc-agent", "status": "/agent/status", "version": VERSION})
            else:
                self._send_json(404, {"error": "not found"})

    return Handler


MENU = """
  [1] Master   - orchestrate training
  [2] Worker   - contribute compute power
  [3] None     - disconnect (dashboard returns to the start screen)
  [q] Quit
"""
CHOICES = {"1": "master", "2": "worker", "3": "none", "master": "master", "worker": "worker", "none": "none"}


def run_menu(state):
    while True:
        print(f"\nCurrent role: {state.role.upper()}")
        print(MENU)
        try:
            choice = input("Select > ").strip().lower()
        except EOFError:
            threading.Event().wait()
            return
        if choice in ("q", "quit", "exit"):
            return
        role = CHOICES.get(choice)
        if role is None:
            print("  Please choose 1, 2, 3 or q.")
            continue
        state.set_role(role)
        print(f"  -> Role set to {role.upper()}. The dashboard will update within ~2 seconds.")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="ADC local agent with machine resource profiling")
    parser.add_argument("--role", choices=("master", "worker"), help="start directly with this role")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: localhost only)")
    parser.add_argument("--port", type=int, default=8765, help="local dashboard-status HTTP port (default: 8765)")
    parser.add_argument("--website-url", default=os.environ.get("ADC_WEBSITE_URL"),
                        help="website base URL, e.g. https://your-site.example (or ADC_WEBSITE_URL)")
    parser.add_argument("--master-port", type=int, default=int(os.environ.get("ADC_MASTER_PORT", "8766")),
                        help="port for the master WebSocket listener (default: 8766)")
    parser.add_argument("--master-bind-host", default=os.environ.get("ADC_MASTER_BIND_HOST", "0.0.0.0"),
                        help="interface for master WebSocket listener (default: all interfaces)")
    parser.add_argument("--tls-cert", default=os.environ.get("ADC_TLS_CERT"), help="TLS certificate path for direct WSS")
    parser.add_argument("--tls-key", default=os.environ.get("ADC_TLS_KEY"), help="TLS private key path for direct WSS")
    parser.add_argument("--project-id", default=os.environ.get("ADC_PROJECT_ID"),
                        help="project ID to register, if already known (or ADC_PROJECT_ID)")
    parser.add_argument("--registration-token", default=os.environ.get("ADC_REGISTRATION_TOKEN"),
                        help="optional bearer token for the website registration endpoint")
    parser.add_argument("--allow-origin", action="append", default=[], metavar="URL",
                        help="extra browser origin allowed to read status (repeatable)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if not (1 <= args.master_port <= 65535):
        print("--master-port must be between 1 and 65535", file=sys.stderr)
        return 2
    state = AgentState(
        args.role or "none",
        website_url=args.website_url,
        master_port=args.master_port,
        registration_token=args.registration_token,
        project_id=args.project_id,
        master_bind_host=args.master_bind_host,
        tls_cert=args.tls_cert,
        tls_key=args.tls_key,
    )
    origins = set(DEFAULT_ORIGINS) | set(args.allow_origin)
    try:
        server = ThreadingHTTPServer((args.host, args.port), make_handler(state, origins))
    except OSError as exc:
        state.close()
        print(f"Could not listen on {args.host}:{args.port} - {exc}\n"
              "Is another agent already running? Try --port <other>.", file=sys.stderr)
        return 1

    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"ADC agent v{VERSION} listening on http://{args.host}:{args.port}/agent/status")
    print("Hardware profiling is best-effort. Open the status URL to inspect the JSON response.")
    print("Master registration endpoint: POST <website>/api/masters/register")
    print("WebRTC signaling endpoints required: POST /api/webrtc/signals and GET /api/webrtc/signals/poll")
    print("Master WebRTC mode uses outbound signaling polling; no incoming master port is required for signaling.")
    print("Worker mode: POST masterAgentId/projectId/authToken to /agent/connect after the website resolves a join code.")
    print(f"Legacy direct WebSocket listener target: {args.master_bind_host}:{args.master_port} (also starts in Master mode).")
    if bool(args.tls_cert) != bool(args.tls_key):
        print("Both --tls-cert and --tls-key are required together for direct WSS.", file=sys.stderr)
        state.close(); server.shutdown(); server.server_close(); return 2
    if args.role == "master":
        state.start_master_websocket()
        state.register_master()
        state.start_master_webrtc_signaling()
    try:
        run_menu(state)
    except KeyboardInterrupt:
        pass
    finally:
        state.close()
        server.shutdown()
        server.server_close()
        print("\nAgent stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
