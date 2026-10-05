import importlib.util
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit
import pytest


class Response:
    def __init__(self, status, body):
        self.status_code, self.text = status, body.decode("utf-8")

    def json(self):
        return json.loads(self.text)


class AsgiClient:
    def __init__(self, app):
        self.app = app

    def request(self, method, url, payload=None):
        async def invoke():
            parsed = urlsplit(url)
            body = json.dumps(payload).encode() if payload is not None else b""
            messages = []
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}
            async def send(message):
                messages.append(message)
            scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http", "path": parsed.path, "raw_path": parsed.path.encode(), "query_string": parsed.query.encode(), "root_path": "", "headers": [(b"content-type", b"application/json")], "server": ("test", 80), "client": ("test", 1)}
            await self.app(scope, receive, send)
            status = next(message["status"] for message in messages if message["type"] == "http.response.start")
            return Response(status, b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body"))
        return asyncio.run(invoke())

    def get(self, url):
        return self.request("GET", url)

    def post(self, url, json):
        return self.request("POST", url, json)


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("RSAGIN_DATA_DIR", str(tmp_path / "data"))
    path = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("rsagin_api_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield AsgiClient(module.app), module


def small_scene(module):
    scene = module._default_scenario.model_dump(mode="json")
    scene["grid"].update(nx=5, ny=4)
    return scene


def test_new_project_and_scene_are_scoped(api):
    client, module = api
    created = client.post("/api/projects", json={"name": "Project isolation test"})
    assert created.status_code == 200
    project_id = created.json()["project"]["id"]
    scene = small_scene(module)
    scene["id"] = "isolated_scene"
    response = client.post(f"/api/projects/{project_id}/scenarios", json={"scenario": scene})
    assert response.status_code == 200, response.text
    workspace = client.get(f"/api/workspace?project_id={project_id}&scenario_id={scene['id']}").json()
    assert workspace["active_project"]["id"] == project_id
    assert workspace["active_scenario"]["id"] == scene["id"]
    assert workspace["runs"] == []
    scene["optimization"]["budget"]["max_total_cost"] = 0
    job = client.post("/api/jobs/optimize", json={"scenario": scene, "selected_candidate_ids": [scene["candidate_nodes"][0]["id"]], "solver": "greedy_fast"}).json()
    assert job["job"]["project_id"] == project_id
    assert job["job"]["scenario_version_id"] == job["result"]["storage"]["scenario_version_id"]
    record = client.get("/api/runs/" + job["result"]["run_id"]).json()["run"]
    assert record["payload"]["scenario"]["deployment"]["selected_candidate_ids"] == job["result"]["selected_candidate_ids"]
    scene["fixed_nodes"][0]["radio"]["tx_power_dbm"] = 1000
    assert client.post("/api/scenarios/validate", json={"scenario": scene}).status_code == 422


def test_scene_version_roundtrip_and_validation(api):
    client, module = api
    scene = small_scene(module)
    scene["name"] = "Saved test scene"
    scene["deployment"] = {"selected_candidate_ids": ["ris_facade_south"]}
    project_id = client.get("/api/workspace").json()["active_project"]["id"]
    scene["id"] = "roundtrip_test"
    created = client.post(f"/api/projects/{project_id}/scenarios", json={"scenario": scene})
    assert created.status_code == 200, created.text
    scene["grid"]["weather"]["rain_rate_mm_h"] = 35
    saved = client.post(f"/api/scenarios/{scene['id']}/versions", json={"scenario": scene})
    assert saved.status_code == 200, saved.text
    loaded = client.get(f"/api/demo?scenario_id={scene['id']}").json()
    assert loaded["scenario"]["name"] == scene["name"]
    assert loaded["scenario"]["grid"]["weather"]["rain_rate_mm_h"] == 35
    assert loaded["scenario"]["deployment"] == scene["deployment"]
    assert loaded["workspace"]["active_scenario_version"]["id"] == saved.json()["version"]["id"]
    scene["fixed_nodes"][0]["position"]["lat"] = 999
    invalid = client.post("/api/scenarios/validate", json={"scenario": scene})
    assert invalid.status_code == 422, invalid.text


def test_run_snapshot_report_and_copilot_binding(api):
    client, module = api
    scene = small_scene(module)
    request = {"scenario": scene, "selected_candidate_ids": ["ris_facade_south"], "model_profile": "standards_l1"}
    run = client.post("/api/simulate", json=request)
    assert run.status_code == 200, run.text
    record = client.get("/api/runs/" + run.json()["run_id"]).json()["run"]
    assert record["payload"]["scenario"]["deployment"]["selected_candidate_ids"] == request["selected_candidate_ids"]
    assert record["scenario_version_id"] == run.json()["storage"]["scenario_version_id"]
    answer = client.post("/api/copilot/ask", json={"run_id": run.json()["run_id"], "message": "覆盖和速率"}).json()
    assert answer["mode"] == "run_bound"
    report = client.post("/api/report", json={**request, "template": "research"})
    assert report.status_code == 200, report.text
    report_data = report.json()
    assert client.get("/api/runs/" + report_data["run_id"]).status_code == 200
    download = client.get("/api/reports/" + report_data["storage"]["report_id"] + "/download")
    assert download.status_code == 200 and report_data["run_id"] in download.text
    job = client.post("/api/jobs/simulate", json=request)
    assert job.status_code == 200 and job.json()["result"]
    listed = client.get("/api/workspace").json()["jobs"]
    assert listed and all(item["result"] is None and item["request"] == {} for item in listed)
    stored_job = client.get("/api/jobs/" + job.json()["job"]["job_id"]).json()["job"]
    assert stored_job["result"]
    assert stored_job["scenario_version_id"] == job.json()["result"]["storage"]["scenario_version_id"]


def test_unknown_solver_and_unbounded_resource_request_rejected(api):
    client, module = api
    scene = small_scene(module)
    assert client.post("/api/optimize", json={"scenario": scene, "solver": "does_not_exist"}).status_code == 422
    assert client.post("/api/resource-plan", json={"scenario": scene, "max_flows": 100_000}).status_code == 422
    assert client.post("/api/simulate", json={"scenario": scene, "selected_candidate_ids": ["unknown"]}).status_code == 422
