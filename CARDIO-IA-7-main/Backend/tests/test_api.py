import asyncio
import json
import time
from dataclasses import replace

import jwt
import pytest
from fastapi.testclient import TestClient

from cardioia_api.app import create_app
from cardioia_api.config import ROOT, Settings
from cardioia_api.database import pack
from cardioia_api.engine import Engine
from cardioia_api.security import PASSWORDS


@pytest.fixture
def settings(tmp_path):
    return Settings(database=tmp_path / "test.sqlite3", jwt_secret="j" * 48,
                    demo_password="senha-apenas-de-teste-123", device_token="t" * 48,
                    automatic_analysis=False)


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as value:
        yield value


def auth(client):
    response = client.post("/api/v1/auth/login", json={"username": "demo", "password": "senha-apenas-de-teste-123"})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def reading(**changes):
    return {"schema_version": 1, "device_id": "esp32-demo-01", "boot_id": "boot-test-1", "sequence": 1,
            "measured_at": None, "uptime_ms": 3000, "temperatura": 37.5, "bpm": 118,
            "historical": False, **changes}


def ingest(client, **changes):
    return client.post("/api/v1/telemetry", headers={"X-Device-Token": "t" * 48}, json=reading(**changes))


def dashboard(client, headers):
    return client.get("/api/v1/cases/caso-demo-01/dashboard", headers=headers).json()


def test_health_and_access_boundaries(client):
    assert client.get("/health").json() == {"status": "ok"}
    for route in ["/api/v1/cases", "/api/v1/cases/caso-demo-01/dashboard", "/api/v1/openapi.json"]:
        assert client.get(route).status_code == 401
    assert client.get("/docs").status_code == 404
    assert client.post("/api/v1/telemetry", json=reading()).status_code == 401


def test_login_invalid_and_empty_dashboard(client):
    bad = client.post("/api/v1/auth/login", json={"username": "demo", "password": "errada"})
    assert bad.status_code == 401
    headers = auth(client)
    data = dashboard(client, headers)
    assert data["measurement"] is None and data["prediction"] is None
    assert data["context"]["source"] == "synthetic"


def test_expired_and_wrong_audience_tokens(client, settings):
    for claims in [{"exp": 1, "aud": "cardioia-ui"}, {"exp": time.time() + 3600, "aud": "other"}]:
        token = jwt.encode({"sub": "demo", "iss": "cardioia", "iat": 1, "jti": "test", **claims}, settings.jwt_secret, algorithm="HS256")
        assert client.get("/api/v1/cases", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_real_model_and_contract(client):
    headers = auth(client)
    response = ingest(client)
    assert response.status_code == 201
    data = dashboard(client, headers)
    assert data["prediction"]["status"] == "ready"
    assert data["prediction"]["probabilidade"] == pytest.approx(0.9986424786256043)
    assert data["prediction"]["classificacao_risco"] == "alto"
    assert data["prediction"]["measurement_id"] == response.json()["measurement_id"]
    assert "model_input" not in data["prediction"]
    from jsonschema import Draft202012Validator
    schema = json.loads((ROOT.parent / "docs/contratos/previsao.schema.json").read_text())
    Draft202012Validator(schema).validate(data["prediction"])


def test_duplicate_idempotent_and_conflict(client):
    first = ingest(client)
    second = ingest(client)
    assert second.status_code == 200 and second.json()["duplicate"]
    assert first.json()["measurement_id"] == second.json()["measurement_id"]
    assert ingest(client, bpm=119).status_code == 409


@pytest.mark.parametrize("changes", [{"sequence": True}, {"bpm": 181}, {"temperatura": None},
                                     {"measured_at": "2026-11-10 10:00"}, {"case_id": "other"},
                                     {"schema_version": True}])
def test_invalid_inputs_rejected(client, changes):
    assert ingest(client, **changes).status_code == 422


def test_non_finite_input_is_not_accepted(client):
    data = json.dumps(reading()).replace('"bpm": 118', '"bpm": NaN')
    assert client.post("/api/v1/telemetry", content=data, headers={"X-Device-Token": "t" * 48, "Content-Type": "application/json"}).status_code == 422


def test_device_token_bound_to_device(client):
    assert ingest(client, device_id="other-device").status_code == 403
    assert client.post("/api/v1/telemetry", json=reading(), headers={"X-Device-Token": "wrong"}).status_code == 401


@pytest.mark.parametrize("bpm,temp", [(180, 37.5), (40, 37.5), (118, 50)])
def test_out_of_domain_keeps_reading_without_score(client, bpm, temp):
    headers = auth(client)
    assert ingest(client, bpm=bpm, temperatura=temp).status_code == 201
    data = dashboard(client, headers)
    assert data["measurement"]["bpm"] == bpm
    assert data["prediction"]["status"] == "out_of_domain"
    assert data["prediction"]["probabilidade"] is None
    result = client.post("/api/v1/cases/caso-demo-01/analyses", headers=headers,
                         json={"measurement_id": data["measurement"]["measurement_id"], "context_revision": 1})
    assert result.status_code == 422


def test_window_uses_real_samples(client, app):
    ingest(client, bpm=100)
    second = ingest(client, bpm=120, sequence=2)
    with app.state.db.connect() as db:
        row = db.execute("SELECT data FROM predictions WHERE measurement_id=?", (second.json()["measurement_id"],)).fetchone()
    prediction = json.loads(row["data"])
    assert prediction["window_samples"] == 2
    assert prediction["model_input"]["fc_media"] == 110


def test_old_sequence_and_closed_boot_do_not_override_latest(client):
    headers = auth(client)
    ingest(client)
    latest = ingest(client, sequence=3)
    ingest(client, sequence=2, bpm=90, measured_at="2099-01-01T00:00:00Z")
    assert dashboard(client, headers)["measurement"]["measurement_id"] == latest.json()["measurement_id"]
    reboot = ingest(client, boot_id="boot-test-2")
    ingest(client, sequence=4, bpm=80)
    assert dashboard(client, headers)["measurement"]["measurement_id"] == reboot.json()["measurement_id"]


def test_historical_reading_does_not_replace_live(client):
    headers = auth(client)
    latest = ingest(client)
    ingest(client, sequence=2, historical=True, bpm=90)
    assert dashboard(client, headers)["measurement"]["measurement_id"] == latest.json()["measurement_id"]


def test_context_revision_and_prediction_snapshot(client, app):
    headers = auth(client)
    mid = ingest(client).json()["measurement_id"]
    context = client.get("/api/v1/cases/caso-demo-01/context", headers=headers).json()
    changed = context["values"] | {"carga_sistema": 30.0}
    request = {"expected_revision": 1, "values": changed}
    assert client.put("/api/v1/cases/caso-demo-01/context", headers=headers, json=request).json()["context_revision"] == 2
    assert client.put("/api/v1/cases/caso-demo-01/context", headers=headers, json=request).status_code == 409
    with app.state.db.connect() as db:
        rows = db.execute("SELECT revision,data FROM predictions WHERE measurement_id=? ORDER BY revision", (mid,)).fetchall()
    assert [r["revision"] for r in rows] == [1, 2]
    assert json.loads(rows[0]["data"])["model_input"]["carga_sistema"] == 92
    assert json.loads(rows[1]["data"])["model_input"]["carga_sistema"] == 30


def test_history_cursor_has_no_duplicates(client):
    headers = auth(client)
    for seq in range(1, 5):
        ingest(client, sequence=seq)
    first = client.get("/api/v1/cases/caso-demo-01/measurements?limit=2", headers=headers).json()
    second = client.get("/api/v1/cases/caso-demo-01/measurements", params={"limit": 2, "cursor": first["next_cursor"]}, headers=headers).json()
    assert [r["sequence"] for r in first["items"] + second["items"]] == [4, 3, 2, 1]
    assert second["next_cursor"] is None


def test_users_cannot_access_other_cases_or_conversations(client, app, settings):
    with app.state.db.connect(write=True) as db:
        db.execute("INSERT INTO users VALUES ('other',?)", (PASSWORDS.hash("other-password-123"),))
        db.execute("INSERT INTO cases(case_id,owner,title) VALUES ('other-case','other','Other')")
        db.execute("INSERT INTO conversations VALUES ('other-conv','other-case','other')")
    headers = auth(client)
    assert client.get("/api/v1/cases/other-case/dashboard", headers=headers).status_code == 404
    assert client.post("/api/v1/conversations/other-conv/messages", headers=headers, json={"text": "oi"}).status_code == 404


def test_cors_and_security_headers(client):
    allowed = client.options("/api/v1/cases", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    denied = client.options("/api/v1/cases", headers={"Origin": "https://unknown.invalid", "Access-Control-Request-Method": "GET"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers
    assert client.get("/health").headers["cache-control"] == "no-store"


def test_rate_limit_login(client):
    for _ in range(10):
        assert client.post("/api/v1/auth/login", json={"username": "missing", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "missing", "password": "wrong"}).status_code == 429


def test_body_limit(settings):
    with TestClient(create_app(replace(settings, max_body=1024))) as client:
        assert client.post("/api/v1/auth/login", content="x" * 1025).status_code == 413


def test_text_module_and_image_unavailability(client):
    headers = auth(client)
    response = client.post("/api/v1/text-triage", json={"text": "sinto palpitações e fadiga"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["source"] == "fase2_triagem_textual"
    assert "palpitações" in response.json()["symptoms"]
    response = client.post("/api/v1/image-classifications", files={"image": ("x.png", b"not-an-image", "image/png")}, headers=headers)
    assert response.status_code == 503


class LocalEngineDouble(Engine):
    """Substituto do LLM para testar fila e HTTP sem chamadas ao modelo de linguagem."""
    async def analyze(self, values):
        await asyncio.sleep(0.01)
        from cardioia.schemas import PatientCase
        from cardioia.protocols import select_protocols
        from cardioia.planning import make_recommendation
        prediction = self.predictor.predict(PatientCase.model_validate(values))
        return {"recommendation": make_recommendation(prediction, select_protocols(PatientCase.model_validate(values), prediction)).model_dump(),
                "events": [], "llm": {"provedor": "substituto_de_teste"}}

    async def chat(self, text, history, snapshot):
        return {"text": "Resposta de teste", "history_size": len(history), "origin": "substituto_de_teste"}


def wait_job(client, url, headers):
    for _ in range(100):
        result = client.get(url, headers=headers).json()
        if result["status"] in {"completed", "failed"}:
            return result
        time.sleep(0.01)
    raise AssertionError("A tarefa não terminou.")


def test_queue_analysis_dedup_and_real_prediction(settings):
    with TestClient(create_app(settings, LocalEngineDouble())) as client:
        headers = auth(client)
        mid = ingest(client).json()["measurement_id"]
        body = {"measurement_id": mid, "context_revision": 1}
        first = client.post("/api/v1/cases/caso-demo-01/analyses", json=body, headers=headers).json()
        second = client.post("/api/v1/cases/caso-demo-01/analyses", json=body, headers=headers).json()
        assert first["analysis_id"] == second["analysis_id"]
        result = wait_job(client, "/api/v1/analyses/" + first["analysis_id"], headers)
        assert result["status"] == "completed"
        assert result["recommendation"]["classificacao_risco"] == "alto"


def test_conversation_history_is_isolated(settings):
    with TestClient(create_app(settings, LocalEngineDouble())) as client:
        headers = auth(client)
        conv = client.post("/api/v1/conversations", json={"case_id": "caso-demo-01"}, headers=headers).json()["conversation_id"]
        url = "/api/v1/conversations/" + conv + "/messages"
        first = client.post(url, json={"text": "Primeira mensagem"}, headers=headers).json()
        assert wait_job(client, url + "/" + first["message_id"], headers)["history_size"] == 0
        second = client.post(url, json={"text": "Segunda mensagem"}, headers=headers).json()
        assert wait_job(client, url + "/" + second["message_id"], headers)["history_size"] == 2


def test_engine_failure_has_no_fake_result(settings):
    class Failed(LocalEngineDouble):
        async def analyze(self, values):
            raise RuntimeError("segredo-interno-nao-publicar")
    with TestClient(create_app(settings, Failed())) as client:
        headers = auth(client)
        mid = ingest(client).json()["measurement_id"]
        job = client.post("/api/v1/cases/caso-demo-01/analyses", headers=headers, json={"measurement_id": mid, "context_revision": 1}).json()
        result = wait_job(client, "/api/v1/analyses/" + job["analysis_id"], headers)
        assert result["status"] == "failed" and result["recommendation"] is None
        assert "segredo-interno" not in json.dumps(result)


def test_automatic_analysis_coalesces_pending_readings(settings):
    import threading
    gate, started = threading.Event(), threading.Event()
    class Delayed(LocalEngineDouble):
        async def analyze(self, values):
            started.set()
            await asyncio.to_thread(gate.wait, 5)
            return await super().analyze(values)
    app = create_app(replace(settings, automatic_analysis=True), Delayed())
    with TestClient(app) as client:
        headers = auth(client)
        ingest(client)
        assert started.wait(2)
        ingest(client, sequence=2)
        latest = ingest(client, sequence=3)
        with app.state.db.connect() as db:
            rows = db.execute("SELECT status,error FROM jobs ORDER BY rowid").fetchall()
        assert [row["status"] for row in rows] == ["running", "failed", "queued"]
        assert json.loads(rows[1]["error"])["code"] == "superseded"
        job = dashboard(client, headers)["analysis"]
        assert job["measurement_id"] == latest.json()["measurement_id"]
        gate.set()
        result = wait_job(client, "/api/v1/analyses/" + job["analysis_id"], headers)
        assert result["status"] == "completed"


def test_restart_marks_unfinished_jobs_as_failed(settings):
    from cardioia_api.jobs import Jobs
    app = create_app(settings, LocalEngineDouble())
    queue = Jobs(app.state.db, LocalEngineDouble())
    job = queue.submit("analysis", "caso-demo-01", "demo", {"model_input": {}}, "med-test", 1)
    with TestClient(create_app(settings, LocalEngineDouble())) as client:
        result = client.get("/api/v1/analyses/" + job["analysis_id"], headers=auth(client)).json()
        assert result["status"] == "failed"
        assert result["error"]["code"] == "server_restarted"
        assert result["recommendation"] is None


def test_missing_model_never_returns_risk_class(client, app):
    app.state.core.engine.predictor = None
    app.state.core.engine.model_error = "Modelo ausente"
    ingest(client)
    prediction = dashboard(client, auth(client))["prediction"]
    assert prediction["status"] == "model_unavailable"
    assert prediction["probabilidade"] is None and prediction["classificacao_risco"] is None
