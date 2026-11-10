"""Contrato de custo zero: só loopback, pesos locais e nenhuma chave paga."""

import asyncio
import io
import json

import pytest
from agents import ModelSettings, OpenAIChatCompletionsModel

from cardioia.local_llm import LocalLLMConfig, check_local_model, create_local_model
from cardioia.orchestrator import run_pipeline
from tests.sdk_double import ScriptedModel


@pytest.mark.parametrize("url", [
    "https://api.openai.com/v1", "http://example.com/v1", "http://127.0.0.1.example.com/v1",
    "http://127.0.0.1@api.openai.com/v1", "http://user:pass@127.0.0.1:11434/v1",
    "http://127.0.0.1:11434/v1?token=x", "http://127.0.0.1:11434/v1#x",
    "http://127.0.0.1:11434/other",
])
def test_external_or_ambiguous_destination_is_refused(monkeypatch, url):
    monkeypatch.setenv("CARDIOIA_OLLAMA_URL", url)
    with pytest.raises(ValueError, match="apenas para o Ollama local"):
        LocalLLMConfig.from_env()


@pytest.mark.parametrize("name", ["qwen3:cloud", "gpt-oss:120b-cloud", "openai/gpt-4o-mini", ""])
def test_cloud_model_names_are_refused(monkeypatch, name):
    monkeypatch.setenv("CARDIOIA_OLLAMA_MODEL", name)
    with pytest.raises(ValueError, match="modelo baixado localmente"):
        LocalLLMConfig.from_env()


def test_openai_key_is_never_forwarded(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "credencial_de_teste_que_nao_deve_ser_usada")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    config = LocalLLMConfig.from_env()
    model = create_local_model(config)
    assert model._client.api_key == "ollama"
    assert str(model._client.base_url).startswith("http://127.0.0.1:")
    assert config.model == "qwen3:0.6b"
    assert config.metadata()["usa_chave_openai"] is False
    asyncio.run(model._client.close())


@pytest.mark.parametrize("info", [
    {"capabilities": ["tools"], "remote_model": "cloud-model"},
    {"capabilities": ["tools"], "remote_host": "https://ollama.com"},
    {"capabilities": ["completion"]},
])
def test_local_server_cannot_proxy_to_cloud_or_use_model_without_tools(monkeypatch, info):
    class Opener:
        def open(self, request, timeout):
            return io.BytesIO(json.dumps(info).encode())
    monkeypatch.setattr("cardioia.local_llm.build_opener", lambda *args: Opener())
    with pytest.raises(ValueError):
        check_local_model(LocalLLMConfig.from_env())


def test_default_pipeline_uses_local_provider_without_api_key(case, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    checked = []
    monkeypatch.setattr("cardioia.orchestrator.check_local_model", lambda config: checked.append(config))
    monkeypatch.setattr("cardioia.orchestrator.create_local_model", lambda config: ScriptedModel())
    execution = asyncio.run(run_pipeline(case))
    assert len(checked) == 1
    assert execution.llm["provedor"] == "ollama_local"
    assert execution.recommendation.classificacao_risco == "alto"


def test_local_config_constructor_also_refuses_external_url():
    with pytest.raises(ValueError):
        LocalLLMConfig("https://api.openai.com/v1", "gpt-4o-mini")


def test_ollama_adapter_preserves_tool_data_and_delegates_to_real_model(monkeypatch):
    from cardioia.agents import prever_risco
    sent = []
    sentinel = object()
    async def backend(self, **kwargs):
        sent.append(kwargs)
        return sentinel
    monkeypatch.setattr(OpenAIChatCompletionsModel, "get_response", backend)
    score = '{"probabilidade":0.9986424786256043,"classificacao_risco":"alto"}'
    history = [{"role": "user", "content": "caso sintético"},
               {"type": "function_call_output", "output": '{"assistant":"Analista de Risco"}'},
               {"type": "function_call_output", "output": score}]
    previous = json.dumps(history)
    model = create_local_model()
    async def run():
        result = await model.get_response(system_instructions="Call consultar_protocolos",
                                          input=history, model_settings=ModelSettings(), tools=[prever_risco],
                                          output_schema=object(), handoffs=[], tracing=None)
        await model._client.close()
        return result
    assert asyncio.run(run()) is sentinel
    assert json.dumps(history) == previous
    assert score in sent[0]["input"][-2]["content"]
    assert sent[0]["input"][-1]["content"] == "Call consultar_protocolos"
    assert sent[0]["model_settings"].tool_choice == "prever_risco"
    assert sent[0]["output_schema"] is None
