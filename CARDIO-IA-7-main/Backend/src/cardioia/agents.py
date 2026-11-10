"""Quatro agentes especializados com tools reais, handoffs e saída tipada."""

from dataclasses import dataclass, field, replace

from agents import (
    Agent, GuardrailFunctionOutput, Model, ModelSettings, RunContextWrapper,
    function_tool, handoff, output_guardrail,
)

from .inference import RiskPredictor
from .local_llm import LocalLLMConfig, create_local_model
from .planning import make_recommendation, validate_recommendation
from .protocols import select_protocols
from .schemas import FinalRecommendation, PatientCase, ProtocolSuggestion, RiskPrediction


@dataclass
class CardioContext:
    case: PatientCase
    predictor: RiskPredictor
    prediction: RiskPrediction | None = None
    protocols: list[ProtocolSuggestion] | None = None
    expected_output: FinalRecommendation | None = None
    events: list[dict[str, str]] = field(default_factory=list)


@function_tool(failure_error_function=None)
def prever_risco(ctx: RunContextWrapper[CardioContext]) -> str:
    """Consulta o pipeline ML salvo para o caso validado do contexto e retorna probabilidade e classe."""
    ctx.context.prediction = ctx.context.predictor.predict(ctx.context.case)
    return ctx.context.prediction.model_dump_json()


@function_tool(failure_error_function=None)
def consultar_protocolos(ctx: RunContextWrapper[CardioContext]) -> str:
    """Cruza dados originais e risco calculado com as dez regras da base simulada."""
    state = ctx.context
    if state.prediction is None:
        raise ValueError("Consultar protocolos exige a execução anterior de prever_risco.")
    state.protocols = select_protocols(state.case, state.prediction)
    return "[" + ",".join(protocol.model_dump_json() for protocol in state.protocols) + "]"


@function_tool(failure_error_function=None)
def planejar_resposta(ctx: RunContextWrapper[CardioContext]) -> FinalRecommendation:
    """Consolida probabilidade, classificação, protocolos aplicáveis e ações operacionais."""
    state = ctx.context
    if state.prediction is None or state.protocols is None:
        raise ValueError("Planejar resposta exige predição e consulta de protocolos concluídas.")
    state.expected_output = make_recommendation(state.prediction, state.protocols)
    return state.expected_output


async def risk_ready(ctx: RunContextWrapper[CardioContext]) -> None:
    if ctx.context.prediction is None:
        raise ValueError("Handoff bloqueado: o Analista ainda não consultou o modelo.")


async def protocols_ready(ctx: RunContextWrapper[CardioContext]) -> None:
    if ctx.context.protocols is None:
        raise ValueError("Handoff bloqueado: o Especialista ainda não consultou os protocolos.")


@output_guardrail
async def check_final_output(
    ctx: RunContextWrapper[CardioContext], agent: Agent[CardioContext], output: FinalRecommendation,
) -> GuardrailFunctionOutput:
    try:
        if ctx.context.expected_output is None:
            raise ValueError("O Planejador não executou sua tool de consolidação.")
        validate_recommendation(output, ctx.context.expected_output)
        error = None
    except (ValueError, TypeError, AttributeError) as exc:
        error = str(exc)
    return GuardrailFunctionOutput(output_info={"erro": error}, tripwire_triggered=error is not None)


def build_agents(model: str | Model | None = None) -> Agent[CardioContext]:
    if model is None or isinstance(model, str):
        model = create_local_model(LocalLLMConfig.from_env(model))
    settings = ModelSettings(temperature=0, max_tokens=256, parallel_tool_calls=False,
                             tool_choice="required", extra_body={"reasoning_effort": "none"})
    def instruction(tool_name: str) -> str:
        # Instrução curta para o LLM pequeno; o estado controla a etapa válida.
        return f"You must call {tool_name} with empty arguments {{}}. Do not produce text. /no_think"
    planner = Agent[CardioContext](
        name="Planejador de Resposta", model=model, model_settings=settings, reset_tool_choice=False,
        handoff_description="Consolida a predição e os protocolos em uma resposta final validada.",
        instructions=instruction("planejar_resposta"),
        tools=[planejar_resposta], output_type=FinalRecommendation,
        tool_use_behavior={"stop_at_tool_names": ["planejar_resposta"]},
        output_guardrails=[check_final_output],
    )
    specialist = Agent[CardioContext](
        name="Especialista em Protocolos", model=model, model_settings=settings, reset_tool_choice=False,
        handoff_description="Consulta a base simulada após o cálculo do risco.",
        instructions=lambda ctx, agent: instruction("consultar_protocolos" if ctx.context.protocols is None
                                                     else "transferir_para_planejador"),
        tools=[replace(consultar_protocolos, is_enabled=lambda ctx, agent: ctx.context.protocols is None)],
        handoffs=[handoff(planner, tool_name_override="transferir_para_planejador", on_handoff=protocols_ready,
                          is_enabled=lambda ctx, agent: ctx.context.protocols is not None)],
    )
    analyst = Agent[CardioContext](
        name="Analista de Risco", model=model, model_settings=settings, reset_tool_choice=False,
        handoff_description="Calcula a probabilidade de pico de risco usando o modelo treinado.",
        instructions=lambda ctx, agent: instruction("prever_risco" if ctx.context.prediction is None
                                                     else "transferir_para_protocolos"),
        tools=[replace(prever_risco, is_enabled=lambda ctx, agent: ctx.context.prediction is None)],
        handoffs=[handoff(specialist, tool_name_override="transferir_para_protocolos", on_handoff=risk_ready,
                          is_enabled=lambda ctx, agent: ctx.context.prediction is not None)],
    )
    return Agent[CardioContext](
        name="Orquestrador", model=model, model_settings=settings, reset_tool_choice=False,
        instructions=instruction("transferir_para_analista"),
        handoffs=[handoff(analyst, tool_name_override="transferir_para_analista")],
    )
