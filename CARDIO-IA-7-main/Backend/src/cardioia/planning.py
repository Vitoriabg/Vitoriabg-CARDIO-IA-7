"""Consolidação e verificação do contrato final usado pelo Planejador."""

import math

from .schemas import ACADEMIC_NOTICE, FinalRecommendation, ProtocolSuggestion, RiskPrediction


def make_recommendation(prediction: RiskPrediction, protocols: list[ProtocolSuggestion]) -> FinalRecommendation:
    return FinalRecommendation(
        **prediction.model_dump(), protocolos_sugeridos=protocols,
        acoes_operacionais=[protocol.acao for protocol in protocols], aviso=ACADEMIC_NOTICE,
    )


def validate_recommendation(output: FinalRecommendation, expected: FinalRecommendation) -> None:
    """Rejeita alteração de score, omissão, duplicação ou invenção de protocolos."""
    if not math.isclose(output.probabilidade, expected.probabilidade, abs_tol=1e-6, rel_tol=0):
        raise ValueError("A probabilidade da resposta não coincide com o modelo treinado.")
    if output.classificacao_risco != expected.classificacao_risco:
        raise ValueError("Classificação de risco inconsistente com a predição.")
    if output.protocolos_sugeridos != expected.protocolos_sugeridos:
        raise ValueError("Protocolos incoerentes, omitidos ou duplicados na resposta.")
    if output.acoes_operacionais != expected.acoes_operacionais or output.aviso != expected.aviso:
        raise ValueError("Ações operacionais ou aviso inconsistentes com a base simulada.")

