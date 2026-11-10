"""Contratos tipados e validação antes de qualquer chamada externa."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ACADEMIC_NOTICE = "Simulação acadêmica com dados sintéticos; não é diagnóstico nem orientação médica."


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class PatientCase(StrictModel):
    idade_media: float = Field(ge=18, le=90)
    carga_sistema: float = Field(ge=0, le=100)
    tempo_espera: float = Field(ge=5, le=180)
    fc_media: float = Field(ge=50, le=150)
    spo2_media: float = Field(ge=70, le=100)
    pa_sistolica: float = Field(ge=80, le=200)
    temperatura: float = Field(ge=10, le=40)
    densidade_eventos: int = Field(ge=0)
    eventos_24h: int = Field(ge=0)
    disponibilidade_recursos: float = Field(ge=0, le=100)

    @model_validator(mode="before")
    @classmethod
    def normalize_resource_alias(cls, data):
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        alias = "disponibilidade recursos"
        if alias in normalized:
            value = normalized.pop(alias)
            if "disponibilidade_recursos" in normalized and normalized["disponibilidade_recursos"] != value:
                raise ValueError("Valores conflitantes para disponibilidade_recursos.")
            normalized["disponibilidade_recursos"] = value
        if any(isinstance(value, bool) for value in normalized.values()):
            raise ValueError("Campos numéricos não aceitam valores booleanos.")
        return normalized


class RiskPrediction(StrictModel):
    probabilidade: float = Field(ge=0, le=1)
    classificacao_risco: Literal["baixo", "alto"]


class ProtocolSuggestion(StrictModel):
    id: str
    condicao: str
    valor_observado: float | str
    acao: str


class FinalRecommendation(RiskPrediction):
    protocolos_sugeridos: list[ProtocolSuggestion]
    acoes_operacionais: list[str]
    aviso: Literal["Simulação acadêmica com dados sintéticos; não é diagnóstico nem orientação médica."]

    def __str__(self) -> str:
        """O SDK serializa a saída de uma tool com str(); mantém JSON no histórico."""
        return self.model_dump_json()
