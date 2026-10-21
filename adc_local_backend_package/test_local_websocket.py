"""Test the existing ADC master's WebSocket receiver from this same computer.

Keep adc_agent.py in this folder, install `websockets`, then run:
    python test_local_websocket.py

This tests the direct WebSocket protocol, not WebRTC or the frontend's join-code flow.
"""
import asyncio
import json
import time
from pathlib import Path

import websockets
from adc_agent import AgentState


async def main() -> None:
    state = AgentState(
        "master", website_url=None, master_port=18766,
        project_id="local-test-project"
    )
    state.start_master_websocket()
    try:
        deadline = time.time() + 10
        while state._ws_status != "listening" and time.time() < deadline:
            if state._ws_status in {"failed", "dependency_missing"}:
                raise RuntimeError(f"Master listener failed: {state._ws_status}: {state._ws_error}")
            await asyncio.sleep(0.1)
        if state._ws_status != "listening":
            raise RuntimeError(f"Master did not start: {state._ws_status} / {state._ws_error}")

        async with websockets.connect("ws://127.0.0.1:18766") as worker:
            await worker.send(json.dumps({
                "type": "worker_hello",
                "workerId": "local-test-worker",
                "agentId": "local-test-worker",
                "projectId": "local-test-project",
                "authToken": state.connection_token,
                "details": {
                    "hostname": "same-computer",
                    "cpuCores": 4,
                    "ramAvailableGB": 0.6,
                    "gpuModel": "Not detected",
                },
            }))
            response = json.loads(await worker.recv())
            if response.get("type") != "welcome":
                raise RuntimeError(f"Worker did not receive welcome: {response}")
            await asyncio.sleep(0.1)
            records = list(state.connected_workers.values())
            if not records or not records[0].get("connected"):
                raise RuntimeError("Master did not record a connected worker")
            print("PASS: worker connected to master on the same computer.")
            print(json.dumps({"masterStatus": state._ws_status, "workerReply": response, "workerStoredByMaster": records[0]}, indent=2))
    finally:
        state.close()


if __name__ == "__main__":
    asyncio.run(main())
