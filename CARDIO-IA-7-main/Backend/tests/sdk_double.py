"""Substituto do LLM apenas para testes: o Runner, tools e handoffs são do SDK real."""

from agents import Model, ModelResponse
from agents.usage import Usage
from openai.types.responses import ResponseFunctionToolCall


class ScriptedModel(Model):
    def __init__(self, steps=None):
        self.steps = steps or [
            "transferir_para_analista", "prever_risco", "transferir_para_protocolos",
            "consultar_protocolos", "transferir_para_planejador", "planejar_resposta",
        ]
        self.index = 0
        self.inputs = []

    async def get_response(self, system_instructions, input, model_settings, tools,
                           output_schema, handoffs, tracing, **kwargs):
        self.inputs.append(input)
        step = self.steps[self.index]
        self.index += 1
        available = {tool.name for tool in tools} | {entry.tool_name for entry in handoffs}
        assert step in available, f"O SDK não expôs a tool/handoff {step}"
        output = ResponseFunctionToolCall(
            id=f"test-tool-{self.index}", type="function_call", name=step,
            call_id=f"test-call-{self.index}", arguments="{}", status="completed",
        )
        return ModelResponse(output=[output], usage=Usage(), response_id=f"test-response-{self.index}")

    async def stream_response(self, *args, **kwargs):
        if False:
            yield None
        raise NotImplementedError("Este substituto testa apenas execução sem streaming.")
