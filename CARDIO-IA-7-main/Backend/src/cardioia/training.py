"""Treino, avaliação e persistência do pipeline supervisionado."""

import json
import platform
from importlib.metadata import version
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, ConfusionMatrixDisplay
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import FEATURES, RISK_THRESHOLD, SEED, TARGET, project_root
from .dataset import generate_dataset


def make_model() -> Pipeline:
    # A normalização fica no pipeline: fit apenas no treino, transform no teste.
    return Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=1000, random_state=SEED)),
    ])


def split_dataset(df: pd.DataFrame):
    return train_test_split(
        df.loc[:, FEATURES], df[TARGET], test_size=0.3,
        random_state=SEED, stratify=df[TARGET],
    )


def train_and_save(root: Path | None = None) -> dict:
    root = root or project_root()
    data_dir, model_dir, metrics_dir = root / "data", root / "models", root / "docs" / "metricas"
    for directory in [data_dir, model_dir, metrics_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    df = generate_dataset()
    df.to_csv(data_dir / "base_sintetica.csv", index=False)
    X_train, X_test, y_train, y_test = split_dataset(df)
    model = make_model().fit(X_train, y_train)
    predictions = model.predict(X_test)
    matrix = confusion_matrix(y_test, predictions, labels=[0, 1])
    report = classification_report(y_test, predictions, output_dict=True, zero_division=0)
    metrics = {
        "algoritmo": "StandardScaler + LogisticRegression",
        "seed": SEED, "registros": len(df), "treino": len(X_train), "teste": len(X_test),
        "acuracia": float(accuracy_score(y_test, predictions)),
        "matriz_confusao": matrix.tolist(),
        "ordem_classes": [0, 1], "relatorio_classificacao": report,
        "distribuicao_classes": {str(k): int(v) for k, v in df[TARGET].value_counts().sort_index().items()},
    }
    versions = {name: version(name) for name in ["numpy", "pandas", "scikit-learn", "joblib"]}
    metadata = {
        "features": FEATURES, "target": TARGET, "risk_threshold": RISK_THRESHOLD,
        "seed": SEED, "test_size": 0.3, "python": platform.python_version(),
        "versions": versions, "training_indices": X_train.index.tolist(), "test_indices": X_test.index.tolist(),
        "classificacao": "alto se probabilidade >= 0.5; baixo caso contrário",
    }
    joblib.dump({"pipeline": model, "metadata": metadata}, model_dir / "pico_risco.joblib", compress=3)
    (model_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (metrics_dir / "avaliacao.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fig, ax = plt.subplots(figsize=(5.4, 4.2))
    ConfusionMatrixDisplay(matrix, display_labels=["Sem pico (0)", "Pico (1)"]).plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title("CardioIA - teste sintético (1.500 casos)")
    ax.set_xlabel("Classe prevista")
    ax.set_ylabel("Classe verdadeira")
    fig.tight_layout()
    fig.savefig(metrics_dir / "matriz_confusao.png", dpi=180)
    plt.close(fig)
    return metrics

