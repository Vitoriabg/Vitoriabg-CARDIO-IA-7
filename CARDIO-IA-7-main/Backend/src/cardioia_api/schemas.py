from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Identifier = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Login(Strict):
    username: Annotated[str, Field(min_length=1, max_length=100)]
    password: Annotated[str, Field(min_length=1, max_length=256)]


class Telemetry(Strict):
    schema_version: Literal[1]
    device_id: Identifier
    boot_id: Identifier
    sequence: Annotated[int, Field(ge=0)]
    measured_at: str | None
    uptime_ms: Annotated[int, Field(ge=0)]
    temperatura: Annotated[float, Field(ge=-40, le=80)]
    bpm: Annotated[float, Field(ge=40, le=180)]
    historical: bool

    @field_validator("schema_version", mode="before")
    @classmethod
    def numeric_version(cls, value):
        if type(value) is not int:
            raise ValueError("schema_version deve ser inteiro.")
        return value

    @field_validator("measured_at")
    @classmethod
    def timestamp(cls, value):
        if value is not None:
            import re
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value):
                raise ValueError("Horário deve seguir RFC 3339 com fuso.")
            if datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset() is None:
                raise ValueError("Horário sem fuso.")
        return value


class ContextValues(Strict):
    idade_media: Annotated[float, Field(ge=18, le=90)]
    carga_sistema: Annotated[float, Field(ge=0, le=100)]
    tempo_espera: Annotated[float, Field(ge=5, le=180)]
    spo2_media: Annotated[float, Field(ge=70, le=100)]
    pa_sistolica: Annotated[float, Field(ge=80, le=200)]
    densidade_eventos: Annotated[int, Field(ge=0)]
    eventos_24h: Annotated[int, Field(ge=0)]
    disponibilidade_recursos: Annotated[float, Field(ge=0, le=100)]


class ContextUpdate(Strict):
    expected_revision: Annotated[int, Field(ge=1)]
    values: ContextValues


class AnalysisRequest(Strict):
    measurement_id: Identifier
    context_revision: Annotated[int, Field(ge=1)]


class ConversationRequest(Strict):
    case_id: Identifier


class MessageRequest(Strict):
    text: Annotated[str, Field(min_length=1, max_length=2000)]

    @field_validator("text")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Mensagem vazia.")
        return value.strip()
