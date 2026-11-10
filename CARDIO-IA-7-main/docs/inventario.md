# Inventário dos módulos anteriores

Inspeção dos READMEs, árvores de arquivos e componentes indicados abaixo em 10/11/2026. A existência de um arquivo não equivale à validação de seu funcionamento no ambiente da Fase 7.

| Fase | Fonte e arquivos encontrados | Reaproveitamento | Adaptação ou lacuna |
| --- | --- | --- | --- |
| 1 — Dados | [Cardio-IA](https://github.com/lab-ia-shared/Cardio-IA): `docs/prontuario_hipertensao_01.txt`, `_02.txt`, `_03.txt`; fontes de dados no README | Textos simulados e documentação de proveniência como material do módulo textual | Bases numéricas/imagens estão referenciadas externamente. Não copiar grandes bases para o MVP nem interpretar os textos como pacientes reais. |
| 2 — Diagnóstico textual | [Cardio-IA-2](https://github.com/lab-ia-shared/Cardio-IA-2): `py/extracao_diagnostico.py`, `py/classificador_risco.py`, três bases em `docs` | Extração de sintomas e classificador de triagem textual | Encapsular funções, retirar caminhos absolutos de Windows e treino/interação de terminal da inicialização da API. O classificador textual não substitui o modelo de risco sistêmico da Fase 6. |
| 3 — IoT | [Cardio-IA-3](https://github.com/lab-ia-shared/Cardio-IA-3): `wokwi_hardware/main.cpp`, `diagram.json`, `link_wokwi`, `wokwi.toml`, `node_red_dashboard/flows.json` | ESP32, DHT22, potenciômetro, botão e regras de sinalização | Converter para MicroPython e trocar o envio MQTT pelo contrato HTTPS da API. Painel React/Expo assume a visualização hoje feita no Node-RED. |
| 4 — Imagens | [Cardio-IA-4](https://github.com/lab-ia-shared/Cardio-IA-4): `notebooks/PreProcessamento.ipynb`, `notebooks/cnn.ipynb`, relatório PDF | Pré-processamento RGB 224×224 e lógica de inferência do classificador escolhido | O notebook exporta `cardioia_vgg16_modelo.keras`; os pesos não estão no repositório. Recuperar artefato e ordem das classes, conferir normalização e validar inferência antes de expor resultado na UI. |
| 5 — Assistência | [Cardio-IA-5](https://github.com/lab-ia-shared/Cardio-IA-5): `backend/app.py`, `frontend/index.html`, `watson/cardioia-action-v1.json` | Fluxo conversacional exportado, textos e organização da conversa | Interface atual é HTML/CSS/JS, não React/Expo. Servidor Flask depende de Watson e contém credencial no fonte; não copiar essa configuração. Adaptar o conteúdo conversacional ao LLM local, registrando a migração. |
| 6 — Predição e agentes | [CARDIO-IA-6](https://github.com/lab-ia-shared/CARDIO-IA-6): pacote `src/cardioia`, `models`, `data`, testes e evidências | `RiskPredictor`, contratos, protocolos, planejamento e `run_pipeline` | Criar API, autenticação, armazenamento e adaptação das leituras. Ollama deve continuar acessível apenas em loopback no host do backend. |

## Evidências técnicas

- A Fase 2 tem `analisar_sintomas(frases, mapa)` importável. O executável usa caminho fixo de Windows, restrito ao bloco `__main__`; o adaptador deve resolver os dados pelo diretório do projeto.
- O C++ da Fase 3 lê DHT22 no GPIO 15 e potenciômetro no GPIO 34, mapeando BPM de **40 a 180**, a cada **3 segundos**. O botão está no GPIO 12. O buffer é um array em RAM de **20 leituras**; não há persistência em disco e não deve ser descrito como armazenamento permanente.
- O notebook de imagens normaliza pixels por `1/255` antes do treino e salva o modelo Keras. A inferência precisa reproduzir o pré-processamento efetivo; não basta usar o nome VGG16 para presumir `preprocess_input`.
- O backend da Fase 5 oferece `/api/message`. O fluxo exportado existe em `watson/cardioia-action-v1.json`; o caminho de backup apresentado no README não corresponde exatamente à árvore atual.
- O `RiskPredictor` da Fase 6 carrega o pipeline e metadados, confere as features e usa `predict_proba` da classe 1. O corte operacional é `0.5`.
- `run_pipeline` é assíncrona e devolve recomendação, histórico, eventos e metadados do LLM. O código mantém quatro agentes e valida a saída final.
- `local_llm.py` recusa destinos externos e modelos de nuvem. Backend e Ollama serão processos no mesmo host, evitando alterar essa restrição para acomodar a publicação.

## Rastreabilidade da inspeção

| Fonte | Identificador observado |
| --- | --- |
| Árvore Fase 1 | `0827cb8be9fcd75d3fea690c3c364648d1d97882` |
| Árvore Fase 2 | `b75e3b97fcb1489baf9421d7e12dbcd53cca3b8f` |
| Árvore Fase 3 | `c0c24c7014f25bd07e62b5a2a686160fc798c3a6` |
| Árvore Fase 4 | `62130edd1cf74fdb2b5955dfdc07975f09165e43` |
| Blob `backend/app.py` Fase 5 | `11d5f826fbb14ac5ed030507e8a367aeca9c719b` |
| Código de agentes Fase 6 observado no GitHub | Commit `928a482f88434b9963267525d25ae8a1c5f59341` |

As árvores são identificadores de árvore Git, não de commit. A análise detalhada do modelo também usou a cópia local da Fase 6 produzida na entrega anterior. Os testes legados não foram reexecutados nesta etapa de planejamento.

## O que falta construir

API integrada, camada de autenticação, SQLite, fluxo de atualização do painel, aplicação React + Vite, aplicativo Expo, simulação MicroPython e configuração de publicação. Nenhum dos repositórios inspecionados contém um aplicativo Expo pronto para ser distribuído.
