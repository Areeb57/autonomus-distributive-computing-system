# ADC local backend prototype

This package gives you a local FastAPI backend so `http://127.0.0.1:8000/docs` works and the current frontend has the routes it needs for project code lookup and WebRTC signaling.

## A. Start the backend on Windows

1. Extract this ZIP to a folder such as `C:\adc-backend`.
2. Open that folder in File Explorer and double-click `run_backend_windows.bat`, or run these commands in PowerShell from that folder:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

3. Keep the terminal window open. In a browser, open:
   - `http://127.0.0.1:8000/health`
   - `http://127.0.0.1:8000/docs`

   Health should return `{"status":"ok", ...}` and `/docs` should show interactive API documentation.

## B. Start the agent pointed at the backend

In another terminal, from the folder containing `adc_agent.py`:

```powershell
$env:ADC_WEBSITE_URL = "http://127.0.0.1:8000"
python adc_agent.py
```

Choose Master only after creating/putting a project online in the website. The agent registers with the backend. In this local prototype, the backend's project record holds the master's signaling token so the worker can resolve the 9-digit code.

## C. Local connection test (direct WebSocket; no website needed)

Install the WebSocket dependency once:

```powershell
py -m pip install websockets
```

Run from this folder:

```powershell
python test_local_websocket.py
```

It starts the current agent's WebSocket receiver locally on port `18766`, connects a simulated worker to `127.0.0.1`, sends a hardware-details message, and checks that the master records the worker. Expected message:

`PASS: worker connected to master on the same computer.`

This specific smoke test verifies the direct WebSocket protocol only. It does not prove that WebRTC or browser join-code flow is working.

## D. WebRTC dependencies

To use the WebRTC signaling endpoints with the current agent, install on the computer running each agent:

```powershell
py -m pip install aiortc websockets
```

Then set `ADC_WEBSITE_URL` as above. STUN attempts direct peer connectivity, but some network combinations may still need a TURN relay.

## Important limitations

- This is a **local development prototype**, not a production security design.
- Project, master and signaling data are stored in memory and are erased when the backend restarts.
- Do not expose this backend to the public internet. It has simplified development auth and returns the master's connection token to the local joining flow. Production needs real auth, scoped expiring worker tokens, a persistent database, rate limiting, HTTPS, and signaling authorization.
- Use one agent HTTP port per running agent. The website's default local agent URL is `http://127.0.0.1:8765`; for two live agents on one computer, start the second with `--port 8767` and set the second frontend instance's `VITE_AGENT_URL=http://127.0.0.1:8767`.
