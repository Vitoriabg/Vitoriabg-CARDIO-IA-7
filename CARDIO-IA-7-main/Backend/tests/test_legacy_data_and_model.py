import numpy as np

from cardioia.config import FEATURES
from cardioia.dataset import generate_dataset
from cardioia.inference import RiskPredictor
from cardioia.training import make_model, split_dataset


def test_generator_reproduces_official_label_and_seed():
    df = generate_dataset()
    assert len(df) == 5000 and list(df.columns) == FEATURES + ["pico_risco"]
    assert df.equals(generate_dataset())
    count = (df.carga_sistema > 80).astype(int) + (df.tempo_espera > 60).astype(int)
    count += (df.spo2_media < 92).astype(int) + (df.fc_media > 110).astype(int)
    count += (df.eventos_24h > 4).astype(int) + (df.disponibilidade_recursos < 40).astype(int)
    assert np.array_equal(df.pico_risco, (count >= 2).astype(int))
    assert df.isna().sum().sum() == 0


def test_split_and_scaler_never_use_test_rows():
    X_train, X_test, y_train, y_test = split_dataset(generate_dataset())
    assert len(X_train) == 3500 and len(X_test) == 1500
    assert not set(X_train.index) & set(X_test.index)
    assert set(X_train.index) | set(X_test.index) == set(range(5000))
    assert list(X_train.columns) == FEATURES
    model = make_model().fit(X_train, y_train)
    np.testing.assert_allclose(model["scaler"].mean_, X_train.mean().to_numpy())


def test_saved_model_matches_fresh_training(case):
    X_train, _, y_train, _ = split_dataset(generate_dataset())
    model = make_model().fit(X_train, y_train)
    saved = RiskPredictor()
    import pandas as pd
    fresh_probability = model.predict_proba(pd.DataFrame([case.model_dump()])[FEATURES])[0, 1]
    assert abs(saved.predict(case).probabilidade - fresh_probability) < 1e-10
    assert saved.predict(case).classificacao_risco == "alto"

