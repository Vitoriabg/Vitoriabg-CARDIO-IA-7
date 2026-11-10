"""Caminhos explícitos para execução a partir do checkout ou do Colab."""

import os
from pathlib import Path

FEATURES = [
    "idade_media", "carga_sistema", "tempo_espera", "fc_media", "spo2_media",
    "pa_sistolica", "temperatura", "densidade_eventos", "eventos_24h",
    "disponibilidade_recursos",
]
TARGET = "pico_risco"
SEED = 42
RISK_THRESHOLD = 0.5


def project_root() -> Path:
    """Permite definir CARDIOIA_ROOT quando o pacote não está no checkout."""
    configured = os.getenv("CARDIOIA_ROOT")
    return Path(configured).resolve() if configured else Path(__file__).resolve().parents[2]

