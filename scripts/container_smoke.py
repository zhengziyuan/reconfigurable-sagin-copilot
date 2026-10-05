"""Exercise the public web origin and its API proxy, without extra dependencies."""
import json
import os
from urllib.request import Request, urlopen

BASE = os.environ.get("RSAGIN_SMOKE_URL", "http://127.0.0.1:8080")


def request(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    with urlopen(Request(BASE + path, data=data, headers={"Content-Type": "application/json"}), timeout=120) as response:
        return json.load(response)


health = request("/health")
assert health["status"] == "ok", health
demo = request("/api/demo")
scene = demo["scenario"]
scene["grid"].update(nx=6, ny=5)
run = request("/api/simulate", {"scenario": scene, "model_profile": "standards_l1", "selected_candidate_ids": []})
assert run["layers"]["rate"]["cells"], run
record = request("/api/runs/" + run["run_id"])
assert record["run"]["scenario_version_id"] == run["storage"]["scenario_version_id"]
print(f"Container smoke passed: version={health['version']}, cells={len(run['layers']['rate']['cells'])}, persisted={run['run_id']}")
