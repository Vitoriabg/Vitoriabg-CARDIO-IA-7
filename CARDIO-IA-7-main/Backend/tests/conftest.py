import json

import pytest

from cardioia.config import project_root
from cardioia.schemas import PatientCase


@pytest.fixture
def case():
    return PatientCase.model_validate(json.loads((project_root() / "data/exemplos/novo_caso.json").read_text()))

