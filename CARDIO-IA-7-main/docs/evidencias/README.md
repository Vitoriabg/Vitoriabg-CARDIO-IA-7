# Evidências do backend e IA

Validação em 10/11/2026 com FastAPI, modelo preditivo original da Fase 6 e Ollama `qwen3:0.6b`, usando apenas dados sintéticos.

| Execução | Registro |
| --- | --- |
| HTTP local | [backend_local.json](backend_local.json) |
| HTTP HTTPS público via Cloudflare Quick Tunnel | [backend_publica.json](backend_publica.json) |
| Suíte automatizada | 105 testes aprovados; inclui regressões da Fase 6 e testes unitários da API com dublês explícitos de LLM |
| Dependências | `pip check`: sem conflitos |

Cada registro HTTP contém a entrada de telemetria, os oito campos de contexto, a previsão calculada, a recomendação, os eventos de execução e uma conversa real. Cada cenário percorreu quatro agentes, três handoffs e seis chamadas ao LLM local. O acesso sem autenticação retornou `401`; as requisições seguintes usaram credenciais locais, que não estão nestes arquivos.

| Cenário | Classe calculada | Saída numérica do modelo |
| --- | --- | ---: |
| Alto | `alto` | 0.9986424786256043 |
| Baixo | `baixo` | 0.00045448698882650043 |

As saídas pertencem ao classificador experimental de risco sistêmico, treinado com dados sintéticos. Não representam probabilidade clínica individual. Os tempos registrados dependem da máquina, da fila e do modelo; não são garantia de latência.

A URL em `backend_publica.json` identifica o túnel usado nessa execução. É temporária e depende da API, Ollama, computador e túnel ativos. Não constitui hospedagem permanente. A validação de Web/Vercel, APK em Android real e envio pelo Wokwi ainda será registrada nas próximas listas; estes testes HTTP não substituem essas evidências.

Reprodução: [guia do backend](../../Backend/README.md). Os arquivos de `docs/exemplos` são fixtures de formato, separados destes registros de execução.
