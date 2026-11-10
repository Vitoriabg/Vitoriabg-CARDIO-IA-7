import asyncio
import hashlib
import json
import unicodedata

from .config import ROOT


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


class Engine:
    def __init__(self):
        self.predictor = None
        self.model_error = None
        try:
            manifest = json.loads((ROOT / "models/manifest.json").read_text())
            for name, expected in manifest.items():
                if name not in {"pico_risco.joblib", "metadata.json"}:
                    raise ValueError("Artefato não permitido.")
                if hashlib.sha256((ROOT / "models" / name).read_bytes()).hexdigest() != expected:
                    raise ValueError("Integridade do modelo inválida.")
            from cardioia.inference import RiskPredictor
            self.predictor = RiskPredictor(ROOT / "models/pico_risco.joblib")
        except (OSError, ValueError, ImportError):
            self.model_error = "Modelo preditivo indisponível ou incompatível."
        self._triage = None

    def predict(self, values):
        if self.predictor is None:
            raise ValueError(self.model_error)
        from cardioia.schemas import PatientCase
        return self.predictor.predict(PatientCase.model_validate(values)).model_dump()

    async def analyze(self, values):
        from cardioia.local_llm import LocalLLMConfig, OllamaModel, check_local_model
        from cardioia.orchestrator import run_pipeline
        from cardioia.schemas import PatientCase
        from openai import AsyncOpenAI, DefaultAsyncHttpxClient
        config = LocalLLMConfig.from_env()
        await asyncio.to_thread(check_local_model, config)
        async with AsyncOpenAI(base_url=config.base_url, api_key="ollama", max_retries=0, timeout=120,
                               http_client=DefaultAsyncHttpxClient(trust_env=False, follow_redirects=False)) as client:
            execution = await run_pipeline(PatientCase.model_validate(values), predictor=self.predictor,
                                           model=OllamaModel(model=config.model, openai_client=client))
        metadata = execution.llm | config.metadata()
        return {"recommendation": execution.recommendation.model_dump(), "events": execution.events,
                "llm": {k: v for k, v in metadata.items() if k != "destino"}}

    async def chat(self, text, history, snapshot):
        from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, RunConfig, Runner
        from cardioia.local_llm import LocalLLMConfig, check_local_model
        from openai import AsyncOpenAI, DefaultAsyncHttpxClient

        config = LocalLLMConfig.from_env()
        await asyncio.to_thread(check_local_model, config)
        instructions = json.loads((ROOT / "data/conversa.json").read_text())["instructions"]
        instructions += "\nContexto verificado do caso simulado: " + json.dumps(snapshot, ensure_ascii=False)
        instructions += "\n/no_think"
        async with AsyncOpenAI(base_url=config.base_url, api_key="ollama", max_retries=0, timeout=120,
                               http_client=DefaultAsyncHttpxClient(trust_env=False, follow_redirects=False)) as client:
            agent = Agent(name="Assistente CardioIA", instructions=instructions,
                          model=OpenAIChatCompletionsModel(model=config.model, openai_client=client),
                          model_settings=ModelSettings(temperature=0.2, max_tokens=400,
                                                       extra_body={"reasoning_effort": "none"}))
            result = await Runner.run(agent, input=history[-8:] + [{"role": "user", "content": text}],
                                      max_turns=2, run_config=RunConfig(tracing_disabled=True))
        answer = str(result.final_output).strip()
        if not answer:
            raise ValueError("O assistente não retornou resposta.")
        return {"text": answer, "origin": "ollama_local", "model": config.model,
                "notice": "Simulação acadêmica; não substitui avaliação profissional."}

    def triage(self, text):
        import pandas as pd
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.pipeline import Pipeline
        from sklearn.tree import DecisionTreeClassifier

        if self._triage is None:
            data = pd.read_csv(ROOT / "data/triagem_risco.csv")
            self._triage = Pipeline([("tfidf", TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode")),
                                     ("tree", DecisionTreeClassifier(random_state=42))])
            self._triage.fit(data["frase"], data["situacao"])
        found = []
        mapping = pd.read_csv(ROOT / "data/mapa_conhecimento.csv")
        message = normalized(text)
        for _, row in mapping.iterrows():
            for field in ("sintoma_1", "sintoma_2"):
                symptom = str(row[field])
                if normalized(symptom) in message and symptom not in found:
                    found.append(symptom)
        return {"source": "fase2_triagem_textual", "symptoms": found,
                "text_classification": str(self._triage.predict([text])[0]),
                "notice": "Classificador textual experimental de dados sintéticos; não é diagnóstico."}

    def classify_image(self, content):
        model_path = ROOT / "models/cardioia_vgg16_modelo.keras"
        classes_path = ROOT / "models/classes-imagens.json"
        if not model_path.is_file() or not classes_path.is_file():
            raise ValueError("Modelo de imagem e mapeamento de classes ainda não disponibilizados.")
        import io
        import numpy as np
        from PIL import Image
        from tensorflow import keras

        classes = json.loads(classes_path.read_text())
        if not isinstance(classes, list) or len(classes) != 2 or len(set(classes)) != 2:
            raise ValueError("Mapeamento de classes inválido.")
        with Image.open(io.BytesIO(content)) as image:
            if image.format not in {"PNG", "JPEG"} or image.width * image.height > 16_000_000:
                raise ValueError("Imagem não suportada.")
            pixels = np.asarray(image.convert("RGB").resize((224, 224)), dtype="float32") / 255
        model = keras.models.load_model(model_path, compile=False, safe_mode=True)
        score = float(model.predict(pixels[None, ...], verbose=0)[0][0])
        if not 0 <= score <= 1:
            raise ValueError("Resultado visual inválido.")
        return {"source": "fase4_vgg16", "class": classes[int(score >= 0.5)], "score": score,
                "notice": "Classificação acadêmica de imagem; não é laudo médico."}
