"""Inferência estritamente a partir do pipeline treinado e salvo."""

from pathlib import Path

import joblib
import pandas as pd

from .config import FEATURES, TARGET, project_root
from .schemas import PatientCase, RiskPrediction


class RiskPredictor:
    def __init__(self, model_path: Path | None = None):
        model_path = model_path or project_root() / "models" / "pico_risco.joblib"
        if not model_path.is_file():
            raise FileNotFoundError("Modelo ausente. Execute: python -m cardioia treinar")
        # Carregar somente o artefato do próprio projeto: joblib usa serialização Python.
        artifact = joblib.load(model_path)
        self.pipeline, self.metadata = artifact["pipeline"], artifact["metadata"]
        if self.metadata["features"] != FEATURES or self.metadata["target"] != TARGET:
            raise ValueError("O artefato não corresponde ao contrato de features da Fase 6.")

    def predict(self, case: PatientCase) -> RiskPrediction:
        features = pd.DataFrame([case.model_dump()]).loc[:, FEATURES]
        classes = list(self.pipeline.classes_)
        probability = float(self.pipeline.predict_proba(features)[0, classes.index(1)])
        classification = "alto" if probability >= self.metadata["risk_threshold"] else "baixo"
        return RiskPrediction(probabilidade=probability, classificacao_risco=classification)

