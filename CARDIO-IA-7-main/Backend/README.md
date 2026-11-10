# Backend e IA

API FastAPI em Python 3.12, com autenticação JWT, SQLite, telemetria, previsão da Fase 6, análise multiagente e conversa pelo Ollama local. Não utiliza serviços IBM nem API paga de LLM.

## Instalação

Execute na pasta `Backend`, com Python 3.12 e Ollama instalados:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
python scripts/init_local.py
ollama pull qwen3:0.6b
python -m cardioia_api
```

O serviço do Ollama deve estar ativo em `127.0.0.1:11434`. A API atende em `http://127.0.0.1:8000`; `/health` permite verificar se está ativa. Execute a partir deste checkout: modelos, protocolos e bases são carregados das pastas locais do projeto.

O inicializador cria `.env` na raiz do repositório, com segredos aleatórios e permissão local restrita. Não sobrescreve arquivo existente. O usuário inicial é `demo`; a senha fica em `CARDIOIA_DEMO_PASSWORD`. O token exclusivo de telemetria fica em `CARDIOIA_DEVICE_TOKEN`. Consulte esses valores no arquivo local, sem incluí-los em prints, commits ou URLs. A senha é armazenada no banco com Argon2; o token do dispositivo, por hash. Trocar a variável de senha não altera uma conta já cadastrada no SQLite.

`requirements.txt` fixa o ambiente de execução validado. `requirements-dev.txt` acrescenta os testes. `requirements-fase6.txt` registra o ambiente anterior; não deve ser instalado por cima do novo lock.

## Fluxo implementado

1. Login retorna JWT com validade de uma hora. O usuário acessa somente seus casos simulados.
2. O dispositivo envia temperatura e BPM em `POST /api/v1/telemetry`, com token próprio, sessão de inicialização e sequência. Reenvios idênticos são idempotentes; conflitos retornam `409`.
3. A API reúne até cinco leituras recentes com os oito campos de contexto sintético e executa o pipeline `StandardScaler + LogisticRegression` original. Dados fora do domínio permanecem no histórico, com risco nulo e motivo explícito.
4. Leituras elegíveis agendam a análise real da Fase 6: quatro agentes, três handoffs e ferramentas de previsão, protocolos e planejamento. O processamento assíncrono não bloqueia o painel. A fila mantém a pendência mais recente por caso, com limite global.
5. O chat recebe o contexto verificado do caso e o histórico da conversa. As mensagens são isoladas por usuário e sessão. Falhas e timeouts são devolvidos como falhas, sem texto ou score inventado.

O painel inclui identificadores de medição e revisão de contexto. Uma recomendação anterior deve ser apresentada com sua referência e horário. Ao reiniciar o servidor, tarefas interrompidas ficam como falhas e podem ser solicitadas novamente.

Os textos da Fase 5 foram adaptados em `data/conversa.json`; seu backend Watson e suas credenciais não foram incorporados. A triagem textual experimental da Fase 2 usa as bases sintéticas em `data/`, separada da previsão numérica.

## Acesso HTTPS gratuito

Com a API e o Ollama ativos, execute em outro terminal, usando o `cloudflared` instalado conforme a documentação oficial:

```bash
cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate
```

O comando informa uma URL `https://...trycloudflare.com`. Somente a porta da API é encaminhada; o Ollama continua restrito ao loopback. A URL muda quando o túnel é recriado. Computador, internet, API, Ollama e túnel precisam permanecer ativos durante o acesso externo. Essa configuração é de demonstração e não oferece disponibilidade permanente para correção posterior.

Na etapa Web, adicionar a origem Vercel exata a `CARDIOIA_ALLOWED_ORIGINS` e reiniciar a API. A URL pública será distribuída a Web e APK por `/runtime-config.json` na Vercel, contendo apenas `config_version` e `api_base_url`; credenciais continuam privadas. A validação com Web publicada e APK real pertence às respectivas listas e ainda está pendente.

## Verificação

Com a API ativa, os comandos abaixo usam os segredos do `.env` local sem exibi-los. Eles enviam dados sintéticos, alteram o contexto do caso de demonstração, executam os dois cenários e uma conversa real:

```bash
python scripts/smoke_api.py
python scripts/smoke_api.py --url https://ENDERECO-DO-TUNEL --label publica
```

As respostas são registradas em [evidências HTTP](../docs/evidencias/). Os exemplos em `docs/exemplos` continuam sendo fixtures; não são evidências de execução.

Para os testes automatizados:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pip check
```

A suíte cobre autenticação, isolamento de casos, validação, idempotência, contexto, domínio do modelo, histórico, fila, indisponibilidade e regressões da Fase 6. Os testes unitários usam dublês explícitos de LLM; a verificação HTTP acima executa o Ollama real.

## Limitações e contratos

- [Contrato HTTP e de dados](../docs/contrato-api.md); o OpenAPI pode ser obtido autenticado em `/api/v1/openapi.json`.
- [Arquitetura e disponibilidade](../docs/arquitetura.md).
- O modelo de imagem da Fase 4 não foi encontrado no repositório anterior. O endpoint retorna `503` até recuperar e validar pesos e classes. TensorFlow não faz parte do ambiente atual; o adaptador visual não foi validado com um modelo real.
- Os artefatos preditivos confiáveis da equipe são conferidos pelo manifesto SHA-256 antes do carregamento. Não substituir por arquivos `joblib` de origem desconhecida.
- Dados, protocolos, risco e textos são experimentais e sintéticos. Não usar para diagnóstico, prescrição ou decisões sobre pacientes reais.
- O texto livre do modelo local pode conter imprecisões. As interfaces devem manter o aviso acadêmico visível; a previsão numérica e os protocolos da análise vêm dos módulos validados, sem serem recalculados pelo chat.

Referências: [FastAPI — OAuth2/JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [Agents SDK — modelos](https://openai.github.io/openai-agents-python/models/), [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
