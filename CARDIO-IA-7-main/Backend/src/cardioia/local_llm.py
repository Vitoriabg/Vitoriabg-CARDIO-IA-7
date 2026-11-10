"""LLM local via Ollama: sem chave OpenAI e sem destino externo ou fallback pago."""

import json
import os
from dataclasses import dataclass, replace
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from agents import OpenAIChatCompletionsModel
from openai import AsyncOpenAI, DefaultAsyncHttpxClient


@dataclass(frozen=True)
class LocalLLMConfig:
    base_url: str
    model: str

    @classmethod
    def from_env(cls, model: str | None = None) -> "LocalLLMConfig":
        url = os.getenv("CARDIOIA_OLLAMA_URL", "http://127.0.0.1:11434/v1").rstrip("/")
        name = model or os.getenv("CARDIOIA_OLLAMA_MODEL", "qwen3:0.6b")
        return cls(url, name)

    def __post_init__(self) -> None:
        parsed = urlsplit(self.base_url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path != "/v1"):
            raise ValueError("CARDIOIA_OLLAMA_URL deve apontar apenas para o Ollama local: http://127.0.0.1:11434/v1")
        if not self.model.strip() or "cloud" in self.model.lower() or "/" in self.model:
            raise ValueError("Use um modelo baixado localmente, sem cloud ou provedor externo.")

    def metadata(self) -> dict:
        return {"provedor": "ollama_local", "modelo": self.model,
                "destino": self.base_url, "usa_chave_openai": False}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirecionamento recusado: o LLM deve permanecer no servidor local.")


class OllamaModel(OpenAIChatCompletionsModel):
    """Adapta o pedido ao modelo pequeno; a resposta continua sendo gerada pelo LLM."""

    async def get_response(self, system_instructions, input, model_settings, tools,
                           output_schema, handoffs, tracing, **kwargs):
        if isinstance(input, str):
            items = [{"role": "user", "content": input}]
        else:
            # O modelo pequeno confundia envelopes antigos de handoff com a tarefa
            # atual. O SDK mantém o histórico completo; o provedor recebe o caso e
            # os resultados anteriores em texto, preservando os JSONs sem alterações.
            items = [item for item in input if item.get("role") == "user"]
            results = []
            for item in input:
                if item.get("type") == "function_call_output":
                    payload = json.loads(item["output"])
                    if not (isinstance(payload, dict) and set(payload) == {"assistant"}):
                        results.append(item["output"])
            if results:
                items.append({"role": "user", "content": "Verified tool results:\n" + "\n".join(results)})
        # Reforça a etapa corrente, sem alterar resultados ou fabricar uma resposta.
        if system_instructions:
            items.append({"role": "user", "content": system_instructions})
        names = [tool.name for tool in tools] + [entry.tool_name for entry in handoffs]
        if len(names) == 1:
            model_settings = replace(model_settings, tool_choice=names[0])
            # O turno pede uma chamada de função. O JSON final é produzido pela tool
            # tipada e conferido pelo guardrail, sem competir com o schema da chamada.
            output_schema = None
        return await super().get_response(
            system_instructions=system_instructions, input=items,
            model_settings=model_settings, tools=tools, output_schema=output_schema,
            handoffs=handoffs, tracing=tracing, **kwargs,
        )


def check_local_model(config: LocalLLMConfig) -> None:
    """Confere o modelo residente antes de enviar o caso ao LLM."""
    request = Request(config.base_url.removesuffix("/v1") + "/api/show",
                      data=json.dumps({"model": config.model}).encode(),
                      headers={"Content-Type": "application/json"})
    # Ignora proxies do ambiente e recusa redirecionamento para outro destino.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=10) as response:
            info = json.load(response)
    except HTTPError as exc:
        raise ValueError(f"Modelo local indisponível. Execute: ollama pull {config.model}") from exc
    except (URLError, TimeoutError) as exc:
        raise ValueError("Ollama local não respondeu. Inicie ollama serve e confira CARDIOIA_OLLAMA_URL.") from exc
    if info.get("remote_model") or info.get("remote_host"):
        raise ValueError("Modelo remoto recusado: a execução deve usar pesos locais e custo zero de API.")
    if "tools" not in info.get("capabilities", []):
        raise ValueError("O modelo local precisa suportar tools para executar os handoffs do SDK.")


def create_local_model(config: LocalLLMConfig | None = None) -> OpenAIChatCompletionsModel:
    config = config or LocalLLMConfig.from_env()
    # Valor literal exigido pelo cliente; não é uma credencial. A chave do .env não é usada.
    client = AsyncOpenAI(base_url=config.base_url, api_key="ollama", max_retries=0, timeout=120,
                         http_client=DefaultAsyncHttpxClient(trust_env=False, follow_redirects=False))
    return OllamaModel(model=config.model, openai_client=client)
