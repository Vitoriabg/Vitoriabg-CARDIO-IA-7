"""Reprodução do gerador fornecido no enunciado da atividade."""

import numpy as np
import pandas as pd

from .config import SEED, TARGET


def generate_dataset(n: int = 5000, seed: int = SEED) -> pd.DataFrame:
    if n < 1:
        raise ValueError("O número de registros deve ser positivo.")
    # RandomState reproduz np.random.seed(42) sem alterar o RNG de outros módulos.
    rng = np.random.RandomState(seed)
    df = pd.DataFrame({
        "idade_media": rng.normal(55, 12, n).clip(18, 90),
        "carga_sistema": rng.uniform(30, 100, n),
        "tempo_espera": rng.normal(45, 20, n).clip(5, 180),
        "fc_media": rng.normal(85, 15, n).clip(50, 150),
        "spo2_media": rng.normal(95, 3, n).clip(70, 100),
        "pa_sistolica": rng.normal(125, 20, n).clip(80, 200),
        "temperatura": rng.normal(24, 5, n).clip(10, 40),
        "densidade_eventos": rng.poisson(3, n),
        "eventos_24h": rng.poisson(2, n),
        "disponibilidade_recursos": rng.uniform(20, 100, n),
    })
    risk_score = (
        (df["carga_sistema"] > 80).astype(int)
        + (df["tempo_espera"] > 60).astype(int)
        + (df["spo2_media"] < 92).astype(int)
        + (df["fc_media"] > 110).astype(int)
        + (df["eventos_24h"] > 4).astype(int)
        + (df["disponibilidade_recursos"] < 40).astype(int)
    )
    df[TARGET] = (risk_score >= 2).astype(int)
    return df

