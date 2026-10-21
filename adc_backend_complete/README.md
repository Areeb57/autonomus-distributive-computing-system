# ADC Backend (local development)

This FastAPI service connects the existing ADC React frontend and `adc_agent.py` through project lookup and WebRTC signaling. It uses SQLite so project codes and signaling data are not lost immediately when the backend process restarts (queued signaling messages expire after 3 minutes).

## Does only the master need the backend?

No. **Run one backend service**. The React website talks to it, the master agent registers and polls it, and the worker agent resolves the project code and exchanges offer/answer messages through it. After WebRTC succeeds, the data channel can transfer worker details directly peer-to-peer. The backend does not need to relay the actual training payload unless direct ICE connectivity fails and you later add TURN/relay support.

## Local Windows startup

1. Extract this folder.
2. Double-click `run_backend_windows.bat`.
3. Keep that terminal open.
4. Open:
   - Health: http://127.0.0.1:8000/health
   - Interactive API docs: http://127.0.0.1:8000/docs
5. Start the React project in a second terminal. Its Vite config must proxy `/api` to `http://localhost:8000` and `/ws` to `ws://localhost:8000`.

The first start installs the dependencies into `.venv` and creates `adc_backend.sqlite3`.

## Connect adc_agent.py to the local backend

Install the agent-side packages in the Python environment you use for `adc_agent.py`:

```powershell
py -m pip install websockets aiortc psutil
```

Start the master (use the real project ID supplied by the website, if creating the project from the website):

```powershell
py adc_agent.py --role master --website-url http://127.0.0.1:8000 --project-id YOUR_PROJECT_ID
```

If you test two agent processes on the same computer, their local status endpoints must use different ports. For example, start the worker agent on `8767` (the master can use the default `8765`):

```powershell
py adc_agent.py --port 8767 --website-url http://127.0.0.1:8000
```

Then the worker must be told to connect using its local agent endpoint, for example by sending `POST http://127.0.0.1:8767/agent/connect` with the `projectId`, `masterAgentId`, and `authToken` returned by `POST /api/webrtc/resolve-code`. The existing website's local-agent URL defaults to port `8765`, so its worker-control URL must be configurable/changed to `8767` when testing two instances on one computer. On separate computers, both local agents can use `8765`.

If a project is created from the website, the website's `/api/v1/projects/{id}/online` endpoint creates the 9-digit code. Once Master is selected, `adc_agent.py` registers its agent ID/token against that project. If running the master without a project ID, the backend makes a standalone local test project and returns its generated code in the registration response/terminal.

## Endpoints used by current frontend/agent

- `GET /health`
- `POST /api/v1/auth/login`, `POST /api/v1/auth/register`, `GET /api/v1/auth/me`, `GET /api/v1/auth/csrf`
- `POST /api/v1/machines/register`, `POST /api/v1/machines/pairing/challenge`, `POST /api/v1/machines/pairing/complete`
- `GET/PATCH /api/v1/resources/me`
- `GET/POST /api/v1/projects`, `POST /api/v1/projects/{id}/online`, `POST /api/v1/projects/{id}/{pause|resume|stop|end}`, `POST /api/v1/projects/join-by-code`
- `POST /api/masters/register`, `POST /api/masters/workers/update`
- `POST /api/webrtc/resolve-code`, `POST /api/webrtc/signals`, `GET /api/webrtc/signals/poll`
- `WS /api/v1/ws/events`

The local demo account already exists:

- Username: `researcher_demo`
- Password: `Password123!`

Change/remove that demo account before any shared or production deployment.

## Important limitations

This is a **local-development MVP**, not a production security certification. The backend currently returns the project's shared connection token to whoever has its 9-digit invite code because the current `adc_agent.py` validates that same token on the worker data channel. Use it only for local testing. Before exposing the service publicly, change the agent/backend to use worker-scoped, revocable tokens; use HTTPS; set `ADC_REGISTRATION_TOKEN` and pass the same value to each agent with `--registration-token`; apply proxy-level rate limits; and restrict project APIs by account/ownership. Also configure TURN credentials if ICE direct connectivity fails on restrictive networks. WebRTC is an attempted direct connection, not a guarantee that no relay will ever be needed.
