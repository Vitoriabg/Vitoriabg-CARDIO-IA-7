"""Consulta determinística da base simulada; nenhum texto é executado como código."""

import json
import operator
from pathlib import Path

from .config import project_root
from .schemas import PatientCase, ProtocolSuggestion, RiskPrediction

OPERATORS = {"<": operator.lt, ">": operator.gt, "==": operator.eq}


def select_protocols(case: PatientCase, prediction: RiskPrediction, path: Path | None = None) -> list[ProtocolSuggestion]:
    path = path or project_root() / "data" / "protocolos.json"
    rules = json.loads(path.read_text(encoding="utf-8"))
    values = case.model_dump() | {"classificacao_risco": prediction.classificacao_risco}
    suggestions = []
    for rule in rules:
        observed = values[rule["campo"]]
        if OPERATORS[rule["operador"]](observed, rule["limite"]):
            suggestions.append(ProtocolSuggestion(
                id=rule["id"], condicao=rule["condicao"],
                valor_observado=observed if isinstance(observed, str) else float(observed), acao=rule["acao"],
            ))
    return suggestions

