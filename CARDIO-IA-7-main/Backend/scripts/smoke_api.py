"""Validação HTTP com os motores reais, usando somente casos sintéticos."""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--label", choices=["local", "publica"], default="local")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    config = dotenv_values(ROOT.parent / ".env")
    session = requests.Session()
    session.trust_env = False

    def request(method, path, **kwargs):
        response = session.request(method, base + path, timeout=20, **kwargs)
        response.raise_for_status()
        return response.json()

    assert request("GET", "/health")["status"] == "ok"
    unauthenticated = session.get(base + "/api/v1/cases", timeout=20).status_code
    assert unauthenticated == 401
    login = request("POST", "/api/v1/auth/login", json={"username": config["CARDIOIA_DEMO_USERNAME"], "password": config["CARDIOIA_DEMO_PASSWORD"]})
    session.headers["Authorization"] = "Bearer " + login["access_token"]

    def wait(path):
        start = time.monotonic()
        while time.monotonic() - start < 210:
            result = request("GET", path)
            if result["status"] == "failed":
                raise RuntimeError(json.dumps(result["error"], ensure_ascii=False))
            if result["status"] == "completed":
                return result, round(time.monotonic() - start, 2)
            time.sleep(3)
        raise TimeoutError("O processamento excedeu o tempo de validação.")

    evidence = {"executed_at": datetime.now(timezone.utc).isoformat(), "base_url": base,
                "synthetic_data_only": True, "llm": "ollama_local_real", "unauthenticated_status": unauthenticated, "cases": []}
    for label, filename in [("alto", "novo_caso.json"), ("baixo", "baixo_risco.json")]:
        values = json.loads((ROOT / "data/exemplos" / filename).read_text())
        context = request("GET", "/api/v1/cases/caso-demo-01/context")
        context_values = {k: v for k, v in values.items() if k not in {"temperatura", "fc_media"}}
        if context["values"] != context_values:
            request("PUT", "/api/v1/cases/caso-demo-01/context", json={"expected_revision": context["context_revision"], "values": context_values})
        telemetry = {"schema_version": 1, "device_id": "esp32-demo-01", "boot_id": "smoke-" + uuid4().hex,
                     "sequence": 1, "measured_at": None, "uptime_ms": 3000, "temperatura": values["temperatura"],
                     "bpm": values["fc_media"], "historical": False}
        received = request("POST", "/api/v1/telemetry", headers={"X-Device-Token": config["CARDIOIA_DEVICE_TOKEN"]}, json=telemetry)
        dashboard = request("GET", "/api/v1/cases/caso-demo-01/dashboard")
        assert dashboard["prediction"]["classificacao_risco"] == label
        job = dashboard["analysis"]
        assert job and job["measurement_id"] == received["measurement_id"], "Análise automática não agendada para a leitura."
        print("Executando caso " + label + " com os agentes reais...", flush=True)
        result, seconds = wait("/api/v1/analyses/" + job["analysis_id"])
        assert result["recommendation"]["classificacao_risco"] == label
        assert result["llm"]["provedor"] == "ollama_local"
        assert sum(event["tipo"] == "handoff" for event in result["events"]) == 3
        evidence["cases"].append({"label": label, "telemetry": telemetry, "context_values": context_values,
                                  "prediction": dashboard["prediction"], "analysis": result, "wait_seconds": seconds})
        print("Caso " + label + " concluído.", flush=True)
    conversation = request("POST", "/api/v1/conversations", json={"case_id": "caso-demo-01"})["conversation_id"]
    path = "/api/v1/conversations/" + conversation + "/messages"
    question = "O que significa o indicador de risco do painel nesta simulação?"
    job = request("POST", path, json={"text": question})
    result, seconds = wait(path + "/" + job["message_id"])
    assert result["origin"] == "ollama_local" and result["text"].strip()
    evidence["conversation"] = {"question": question, "result": result, "wait_seconds": seconds}
    target = ROOT.parent / "docs/evidencias" / ("backend_" + args.label + ".json")
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print("Validação concluída; evidência salva em " + target.name)


if __name__ == "__main__":
    main()
