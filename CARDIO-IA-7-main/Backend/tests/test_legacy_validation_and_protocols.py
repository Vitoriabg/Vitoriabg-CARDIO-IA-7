import pytest
from pydantic import ValidationError

from cardioia.planning import make_recommendation, validate_recommendation
from cardioia.protocols import select_protocols
from cardioia.schemas import PatientCase, RiskPrediction


def test_alias_in_example_is_normalized(case):
    data = case.model_dump()
    data["disponibilidade recursos"] = data.pop("disponibilidade_recursos")
    assert PatientCase.model_validate(data) == case


@pytest.mark.parametrize("change", [
    {"spo2_media": 101}, {"fc_media": -1}, {"eventos_24h": 1.5},
    {"temperatura": float("nan")}, {"spo2_media": float("inf")},
    {"idade_media": True}, {"carga_sistema": "92"},
    {"campo_desconhecido": 1}, {"disponibilidade recursos": 10},
])
def test_invalid_inputs_are_rejected(case, change):
    with pytest.raises(ValidationError):
        PatientCase.model_validate(case.model_dump() | change)


def test_missing_field_is_rejected(case):
    data = case.model_dump()
    del data["spo2_media"]
    with pytest.raises(ValidationError):
        PatientCase.model_validate(data)


def test_official_example_only_activates_matching_protocols(case):
    risk = RiskPrediction(probabilidade=0.9, classificacao_risco="alto")
    assert [p.id for p in select_protocols(case, risk)] == ["P02", "P05", "P08", "P10"]


@pytest.mark.parametrize("field,limit,trigger,id", [
    ("spo2_media", 88, 87, "P01"), ("carga_sistema", 85, 86, "P02"),
    ("fc_media", 120, 121, "P03"), ("eventos_24h", 5, 6, "P04"),
    ("disponibilidade_recursos", 30, 29, "P05"), ("tempo_espera", 90, 91, "P06"),
    ("temperatura", 38, 39, "P07"), ("densidade_eventos", 6, 7, "P08"),
    ("pa_sistolica", 90, 89, "P09"),
])
def test_protocol_threshold_is_strict(case, field, limit, trigger, id):
    risk = RiskPrediction(probabilidade=0.1, classificacao_risco="baixo")
    equal = PatientCase.model_validate(case.model_dump() | {field: limit})
    above = PatientCase.model_validate(case.model_dump() | {field: trigger})
    assert id not in [p.id for p in select_protocols(equal, risk)]
    assert id in [p.id for p in select_protocols(above, risk)]


@pytest.mark.parametrize("mutation", ["score", "classe", "omissao", "duplicacao", "acao"])
def test_final_validation_blocks_fabrication(case, mutation):
    risk = RiskPrediction(probabilidade=0.9, classificacao_risco="alto")
    expected = make_recommendation(risk, select_protocols(case, risk))
    output = expected.model_copy(deep=True)
    if mutation == "score": output.probabilidade = 0.1
    elif mutation == "classe": output.classificacao_risco = "baixo"
    elif mutation == "omissao": output.protocolos_sugeridos.pop()
    elif mutation == "duplicacao": output.protocolos_sugeridos.append(output.protocolos_sugeridos[0])
    elif mutation == "acao": output.acoes_operacionais.append("ação não prevista")
    with pytest.raises(ValueError):
        validate_recommendation(output, expected)
