"""API smoke test for ADC backend. Run: python -m pip install -r requirements.txt && python test_backend.py"""
import os
import tempfile
from pathlib import Path

# Give the imported application a throwaway database so the smoke test does not alter the real local DB.
_tmp = tempfile.TemporaryDirectory(prefix="adc-backend-test-")
os.environ["ADC_BACKEND_DB"] = str(Path(_tmp.name) / "test.sqlite3")

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


def run() -> None:
    health = client.get("/health")
    assert health.status_code == 200 and health.json()["status"] == "ok", health.text

    login = client.post("/api/v1/auth/login", json={"username": "researcher_demo", "password": "Password123!"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "X-Installation-Id": "test-install"}

    create = client.post("/api/v1/projects", headers=headers, json={"name": "API smoke test"})
    assert create.status_code == 200, create.text
    project_id = create.json()["id"]
    online = client.post(f"/api/v1/projects/{project_id}/online", headers=headers)
    assert online.status_code == 200, online.text
    code = online.json()["project_code"]
    assert len(code) == 9 and code.isdigit(), code

    master_id = "master-smoke"
    worker_id = "worker-smoke"
    secret = "smoke-test-project-token-1234567890"
    register = client.post("/api/masters/register", json={
        "agentId": master_id, "projectId": project_id, "role": "master",
        "publicIp": "127.0.0.1", "masterPort": 8766, "protocol": "ws",
        "hostname": "smoke-test", "connectionToken": secret,
    })
    assert register.status_code == 200, register.text

    resolve = client.post("/api/webrtc/resolve-code", json={"code": code})
    assert resolve.status_code == 200, resolve.text
    assert resolve.json()["masterAgentId"] == master_id
    assert resolve.json()["authToken"] == secret

    offer = client.post("/api/webrtc/signals", json={
        "targetAgentId": master_id, "fromAgentId": worker_id, "signalId": "session-smoke",
        "signalType": "offer", "sdp": "fake-sdp-offer", "projectId": project_id, "authToken": secret,
    })
    assert offer.status_code == 200, offer.text
    master_poll = client.get("/api/webrtc/signals/poll", params={"agentId": master_id, "role": "master"})
    assert master_poll.status_code == 200, master_poll.text
    assert master_poll.json()["signals"][0]["signalType"] == "offer"

    answer = client.post("/api/webrtc/signals", json={
        "targetAgentId": worker_id, "fromAgentId": master_id, "signalId": "session-smoke",
        "signalType": "answer", "sdp": "fake-sdp-answer", "projectId": project_id, "authToken": secret,
    })
    assert answer.status_code == 200, answer.text
    worker_poll = client.get("/api/webrtc/signals/poll", params={"agentId": worker_id, "role": "worker", "signalId": "session-smoke"})
    assert worker_poll.status_code == 200, worker_poll.text
    assert worker_poll.json()["signals"][0]["signalType"] == "answer"

    resource = client.get("/api/v1/resources/me", headers=headers)
    assert resource.status_code == 200, resource.text
    print("PASS: health, login, create/online project, 9-digit code lookup, and offer/answer signaling queue.")
    print(f"Project code generated during test: {code}")


if __name__ == "__main__":
    run()
    _tmp.cleanup()
