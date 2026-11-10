"""Integração com modelo ML salvo e Runner real; LLM simulado, sem chamadas externas."""

import asyncio
import json
from types import SimpleNamespace
import pytest
from openai import RateLimitError

from cardioia.cli import main
from cardioia.config import project_root
from cardioia.inference import RiskPredictor
from cardioia.orchestrator import run_pipeline
from cardioia.protocols import select_protocols
from cardioia.schemas import PatientCase, RiskPrediction
from tests.sdk_double import ScriptedModel


@pytest.mark.parametrize("file,classification,ids", [
    ("novo_caso.json", "alto", ["P02", "P05", "P08", "P10"]),
    ("baixo_risco.json", "baixo", []),
])
def test_integrated_scenarios_preserve_tool_results(file, classification, ids):
    case = PatientCase.model_validate_json((project_root() / "data/exemplos" / file).read_text())
    execution = asyncio.run(run_pipeline(case, model=ScriptedModel()))
    prediction = RiskPredictor().predict(case)
    assert execution.recommendation.probabilidade == prediction.probabilidade
    assert execution.recommendation.classificacao_risco == classification
    assert [p.id for p in execution.recommendation.protocolos_sugeridos] == ids
    outputs = [json.loads(i["output"]) for i in execution.history
               if i.get("type") == "function_call_output"]
    assert outputs[-1] == execution.recommendation.model_dump()
    assert len([e for e in execution.events if e["tipo"] == "handoff"]) == 3


@pytest.mark.parametrize("field,limit,non_trigger,id", [
    ("spo2_media", 88, 89, "P01"), ("carga_sistema", 85, 84, "P02"),
    ("fc_media", 120, 119, "P03"), ("eventos_24h", 5, 4, "P04"),
    ("disponibilidade_recursos", 30, 31, "P05"), ("tempo_espera", 90, 89, "P06"),
    ("temperatura", 38, 37.9, "P07"), ("densidade_eventos", 6, 5, "P08"),
    ("pa_sistolica", 90, 91, "P09"),
])
def test_protocol_non_trigger_side(case, field, limit, non_trigger, id):
    risk = RiskPrediction(probabilidade=0.1, classificacao_risco="baixo")
    for value in [limit, non_trigger]:
        scenario = PatientCase.model_validate(case.model_dump() | {field: value})
        assert id not in [p.id for p in select_protocols(scenario, risk)]


def test_separate_runs_do_not_share_patient_history(case):
    low = PatientCase.model_validate_json((project_root() / "data/exemplos/baixo_risco.json").read_text())
    high_run = asyncio.run(run_pipeline(case, model=ScriptedModel()))
    low_run = asyncio.run(run_pipeline(low, model=ScriptedModel()))
    assert len(high_run.history) == len(low_run.history)
    assert case.model_dump_json() not in low_run.history[0]["content"]
    assert low.model_dump_json() in low_run.history[0]["content"]


def test_cli_saves_normalized_input_and_real_ml_result(tmp_path, monkeypatch, capsys):
    target = tmp_path / "evidence/result.json"
    monkeypatch.setattr("sys.argv", ["cardioia", "prever", "--saida", str(target)])
    main()
    result = json.loads(capsys.readouterr().out)
    assert json.loads(target.read_text()) == result
    assert result["modo"] == "conferencia_local_sem_agentes"
    assert result["resultado"]["classificacao_risco"] == "alto"
    assert "disponibilidade_recursos" in result["entrada"]


@pytest.mark.parametrize("mode", ["missing", "misspelled", "invalid"])
def test_cli_rejects_bad_case_before_calling_agents(case, tmp_path, monkeypatch, capsys, mode):
    data = case.model_dump()
    if mode == "missing":
        data.pop("fc_media")
    elif mode == "misspelled":
        data["disponibilidade_recurso"] = data.pop("disponibilidade_recursos")
    else:
        data["temperatura"] = "quente"
    input_file = tmp_path / "case.json"
    input_file.write_text(json.dumps(data))
    async def forbidden_call(*args, **kwargs):
        pytest.fail("Entrada inválida não pode alcançar o Runner")
    monkeypatch.setattr("cardioia.orchestrator.run_pipeline", forbidden_call)
    monkeypatch.setattr("sys.argv", ["cardioia", "agentes", "--caso", str(input_file)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert "Erro:" in capsys.readouterr().err


@pytest.mark.parametrize("code", ["credit_balance_exhausted", "rate_limit_exceeded"])
def test_cli_local_error_never_requests_paid_billing(monkeypatch, capsys, code):
    async def failing_call(*args, **kwargs):
        response = SimpleNamespace(status_code=429, request=object(), headers={})
        raise RateLimitError("conteúdo interno que não deve ser exibido", response=response, body={"code": code})
    monkeypatch.setattr("cardioia.orchestrator.run_pipeline", failing_call)
    monkeypatch.setattr("sys.argv", ["cardioia", "agentes"])
    with pytest.raises(SystemExit) as error:
        main()
    captured = capsys.readouterr()
    assert error.value.code == 1
    assert "servidor Ollama local" in captured.err
    assert "billing" not in captured.err
    assert "conteúdo interno" not in captured.err
