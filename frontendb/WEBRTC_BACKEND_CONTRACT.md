# ADC frontend ↔ WebRTC signaling backend contract

The React frontend now calls the following server routes. These routes must be implemented by the FastAPI/backend service; adding frontend code alone cannot store project mappings or relay signaling messages.

## 1. Master registration

The local `adc_agent.py` posts to `POST /api/masters/register` after the website tells it to enter Master mode. Payload includes `agentId`, `projectId`, `publicIp`, `masterPort`, `protocol`, `connectionToken`, and `supportsWebRTC`. Associate `projectId` with the 9-digit project code created by the existing project API. Return JSON (e.g. `{"ok": true}`); do not expose the master's connection token publicly.

## 2. Resolve a code

The frontend posts `POST /api/webrtc/resolve-code` with `{"code": "123456789"}`. Validate that the project exists and accepts workers. Return a worker-scoped authorization token, not the master's long-lived secret. Expected response shape:

```json
{
  "projectId": "project-id",
  "masterAgentId": "agent-id-from-registration",
  "authToken": "short-lived-worker-scoped-token",
  "projectName": "Optional project name"
}
```

The frontend stores this temporary result in `sessionStorage` and passes it to the local worker agent only after the existing project join API accepts membership.

## 3. WebRTC signaling queue

The agent requires these endpoints:

- `POST /api/webrtc/signals`: accept signaling messages with `targetAgentId`, `fromAgentId`, `signalId`, `signalType`, `sdp`, `projectId`, and `authToken`. Validate membership and token, then queue the message for its intended recipient.
- `GET /api/webrtc/signals/poll?agentId=...&role=master|worker&signalId=...`: return queued messages for that authorized agent. Example: `{"signals": []}`. Use bounded polling, expiry and per-agent/project isolation.
- `POST /api/masters/workers/update`: accept worker status/details from the master agent and publish updates to the master dashboard's existing event channel.

The `signalType` values currently used by `adc_agent.py` include `offer` and `answer`. The backend must route an offer to the target master and an answer back to the initiating worker. ICE candidates are currently included through the gathered SDP (non-trickle ICE).

## 4. Local browser ↔ agent calls

After a project goes online, the frontend posts `POST http://127.0.0.1:8765/agent/role` with `{"role":"master","projectId":"..."}`. On a worker, it posts `POST http://127.0.0.1:8765/agent/connect` with `masterAgentId`, `projectId`, `authToken`, and optional `websocketUrl`.

The local agent's CORS allowlist defaults to localhost development origins. For a deployed frontend, start the agent with `--allow-origin https://your-frontend-domain.example` (use your actual site origin). HTTPS browser-to-local-agent policies may vary by browser; test this on target browsers.

## Security notes

- Use HTTPS for the website/backend and short-lived, project-scoped worker tokens.
- Never trust a 9-digit code alone as long-lived authentication. Rate-limit attempts and expire/revoke codes.
- Authorize every signaling poll and POST; don't allow arbitrary agent IDs to read messages.
- WebRTC data-channel encryption is provided by DTLS, but authorization still belongs to the application.
- STUN cannot guarantee direct connectivity across every NAT/firewall. Add TURN only if direct attempts fail.
