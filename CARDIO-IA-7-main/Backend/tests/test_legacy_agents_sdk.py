import asyncio
from dataclasses import replace

import pytest
from agents import OutputGuardrailTripwireTriggered, RunContextWrapper

from cardioia.agents import CardioContext, build_agents, planejar_resposta, risk_ready
from cardioia.inference import RiskPredictor
from cardioia.orchestrator import run_pipeline
from cardioia.planning import make_recommendation
from cardioia.protocols import select_protocols
from cardioia.schemas import FinalRecommendation
from tests.sdk_double import ScriptedModel


def test_real_sdk_runs_four_agents_tools_handoffs_and_keeps_history(case):
    model = ScriptedModel()
    execution = asyncio.run(run_pipeline(case, model=model))
    prediction = RiskPredictor().predict(case)
    assert execution.recommendation == make_recommendation(prediction, select_protocols(case, prediction))
    handoffs = [event for event in execution.events if event["tipo"] == "handoff"]
    assert [(h["origem"], h["destino"]) for h in handoffs] == [
        ("Orquestrador", "Analista de Risco"),
        ("Analista de Risco", "Especialista em Protocolos"),
        ("Especialista em Protocolos", "Planejador de Resposta"),
    ]
    assert [e["nome"] for e in execution.events if e["tipo"] == "tool"] == [
        "prever_risco", "consultar_protocolos", "planejar_resposta",
    ]
    outputs = [i for i in execution.history if i.get("type") == "function_call_output"]
    assert len(outputs) == 6  # três handoffs e três chamadas das tools.
    assert len(model.inputs[-1]) > len(model.inputs[0])


@pytest.mark.parametrize("mutator", [
    lambda out: out.update(probabilidade=0.01),
    lambda out: out["protocolos_sugeridos"].pop(),
    lambda out: out["acoes_operacionais"].append("ação inventada"),
])
def test_sdk_output_guardrail_rejects_corrupted_final_tool_result(case, mutator, monkeypatch):
    async def corrupted_output(ctx, arguments):
        result = await planejar_resposta.on_invoke_tool(ctx, arguments)
        payload = result.model_dump()
        mutator(payload)
        return FinalRecommendation.model_validate(payload)
    monkeypatch.setattr("cardioia.agents.planejar_resposta",
                        replace(planejar_resposta, on_invoke_tool=corrupted_output))
    with pytest.raises(OutputGuardrailTripwireTriggered):
        asyncio.run(run_pipeline(case, model=ScriptedModel()))


def test_handoff_without_prediction_is_blocked(case):
    context = RunContextWrapper(CardioContext(case=case, predictor=RiskPredictor()))
    with pytest.raises(ValueError, match="Analista ainda não consultou"):
        asyncio.run(risk_ready(context))


def test_local_server_is_checked_before_model_call(case, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    def unavailable(config):
        raise ValueError("Ollama local indisponível")
    monkeypatch.setattr("cardioia.orchestrator.check_local_model", unavailable)
    with pytest.raises(ValueError, match="Ollama local indisponível"):
        asyncio.run(run_pipeline(case))


def test_agent_build_produces_strict_output_schema():
    root = build_agents(ScriptedModel())
    analyst = root.handoffs[0].agent_name
    assert analyst == "Analista de Risco"
