"""Execução do SDK com contexto de um caso, histórico e limite de turnos."""

import asyncio
from dataclasses import dataclass

from agents import Model, RunConfig, RunHooks, Runner

from .agents import CardioContext, build_agents
from .inference import RiskPredictor
from .local_llm import LocalLLMConfig, check_local_model, create_local_model
from .planning import validate_recommendation
from .schemas import FinalRecommendation, PatientCase


class PipelineHooks(RunHooks[CardioContext]):
    async def on_agent_start(self, context, agent):
        context.context.events.append({"tipo": "agente", "nome": agent.name})

    async def on_handoff(self, context, from_agent, to_agent):
        context.context.events.append({"tipo": "handoff", "origem": from_agent.name, "destino": to_agent.name})

    async def on_tool_end(self, context, agent, tool, result):
        context.context.events.append({"tipo": "tool", "agente": agent.name, "nome": tool.name})


@dataclass
class PipelineExecution:
    recommendation: FinalRecommendation
    history: list[dict]
    events: list[dict[str, str]]
    llm: dict


async def run_pipeline(
    case: PatientCase,
    predictor: RiskPredictor | None = None,
    model: str | Model | None = None,
) -> PipelineExecution:
    """Modelo injetável permite testar o Runner real sem requisitar uma API externa."""
    llm = {"provedor": "modelo_injetado"}
    if model is None or isinstance(model, str):
        config = LocalLLMConfig.from_env(model)
        await asyncio.to_thread(check_local_model, config)
        model = create_local_model(config)
        llm = config.metadata()
    context = CardioContext(case=case, predictor=predictor or RiskPredictor())
    result = await Runner.run(
        build_agents(model),
        input="Analise este caso simulado usando o pipeline completo: " + case.model_dump_json(),
        context=context, hooks=PipelineHooks(), max_turns=12,
        # O histórico permanece nesta execução. Não envia tracing adicional à nuvem.
        run_config=RunConfig(tracing_disabled=True, workflow_name="CardioIA Fase 6"),
    )
    if result.last_agent.name != "Planejador de Resposta" or not isinstance(result.final_output, FinalRecommendation):
        raise ValueError("O fluxo terminou antes de passar pelos quatro agentes.")
    if context.expected_output is None:
        raise ValueError("A tool de planejamento não foi executada.")
    validate_recommendation(result.final_output, context.expected_output)
    usage = result.context_wrapper.usage
    llm.update(chamadas_llm=usage.requests, tokens_entrada=usage.input_tokens, tokens_saida=usage.output_tokens)
    return PipelineExecution(result.final_output, result.to_input_list(), context.events, llm)
