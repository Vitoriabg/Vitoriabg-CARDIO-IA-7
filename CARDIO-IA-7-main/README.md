# 💓 CardioIA - Coração Sob Controle

## 📋 Descrição do Projeto

O **CardioIA** evolui, na **Fase 7**, para uma **Plataforma Integrada de Inteligência Cardíaca**, conectando a captura de sinais simulados em dispositivos IoT, o processamento em Python e os recursos de inteligência artificial às interfaces Web e Mobile.

Esta etapa dá continuidade à [Fase 6 — Sistema Preditivo Multiagente](https://github.com/lab-ia-shared/CARDIO-IA-6). O foco passa da construção e orquestração dos módulos para a entrega de um **MVP funcional de ponta a ponta**, com experiência de uso acessível, publicação Web com CI/CD e distribuição de um aplicativo Android em formato APK.

**Disciplina/projeto:** 2º ano, Fase 7, Capítulo 1 — *Da Construção de Módulos à Solução Integrada*.

> **Status: backend e IA implementados.** A API Python já recebe telemetria, autentica usuários, mantém histórico e executa o modelo e os agentes da Fase 6, além da conversa com Ollama local. O circuito MicroPython já executa no Wokwi. O link público e a validação da rede do simulador seguem em andamento; Web e Mobile são as próximas etapas. Consulte a [instalação do backend](Backend/README.md) e as [evidências de execução](docs/evidencias/).

> Projeto acadêmico com dados e protocolos simulados. Os resultados não constituem diagnóstico, prescrição ou recomendação para uso clínico.

## 👨‍⚕️ Integrantes da Equipe

- [Nicolas Antonio Silva Araujo](https://www.linkedin.com/in/nicolas--araujo/) — RM **566307**
- [Vitória Pereira Bagatin](https://www.linkedin.com/in/vitoria-bagatin-31ba88266/) — RM **566519**

### Organização do trabalho

| Integrante | Frente principal |
| --- | --- |
| Nicolas | Repositório, desenvolvimento, backend, integração de IA e IoT, builds e deploy |
| Vitória | Protótipo das telas, UX, apresentação das informações e organização da documentação |

O protótipo visual pode usar dados fictícios identificados como exemplo, permitindo avançar antes da integração. Prints, links e descrições finais serão atualizados após a validação da plataforma.

O planejamento foi dividido em 22 cartões com checklists e dependências no [Trello da equipe](https://trello.com/b/xOYTjFR3/fiap).

## 📂 Estrutura de Arquivos

O backend e o firmware estão implementados. As pastas Web e Mobile contêm as orientações para as interfaces:

```text
CARDIO-IA-7/
├── Web/                    # Orientações para React + Vite; aplicação futura
├── Mobile/                 # Orientações para React Native + Expo; app futuro
├── Backend/                # API, modelo, agentes, dados, scripts e testes
├── IoT/                    # Firmware MicroPython, circuito Wokwi e guia de execução
├── docs/
│   ├── planejamento.md
│   ├── inventario.md
│   ├── arquitetura.md
│   ├── contrato-api.md
│   ├── evidencias/          # Respostas HTTP reais com dados sintéticos
│   ├── contratos/          # JSON Schemas do contrato
│   └── exemplos/           # Dados fictícios para implementação e protótipo
├── .env.example
├── .gitignore
└── README.md
```

Os nomes das pastas de backend e IoT seguem os entregáveis do enunciado. Os arquivos de configuração serão incluídos com as respectivas aplicações.

O [planejamento](docs/planejamento.md) registra escopo, sequência, responsabilidades e pendências. O [inventário](docs/inventario.md) apresenta o que existe nas seis fases e o que precisa ser adaptado. O [contrato da API](docs/contrato-api.md) e os [exemplos de dados](docs/exemplos/README.md) permitem preparar as telas antes da integração.

## 🧠 1. Continuidade da Fase 6

A [Fase 6](https://github.com/lab-ia-shared/CARDIO-IA-6) desenvolveu um classificador supervisionado de `pico_risco` sobre uma base sintética e um fluxo com quatro agentes: **Orquestrador, Analista de Risco, Especialista em Protocolos e Planejador de Resposta**.

O projeto anterior utiliza um pipeline **StandardScaler + LogisticRegression**, modelo persistido, contratos de dados, tools, handoffs e validação da saída. A execução dos agentes foi documentada com **OpenAI Agents SDK + Qwen3 no Ollama local**.

A API integra a função assíncrona `run_pipeline` em `Backend/src/cardioia/orchestrator.py`. Ela recebe um `PatientCase` validado e devolve recomendação, histórico, eventos e metadados. O modelo original é carregado após conferência do manifesto SHA-256; o backend monta suas dez features a partir dos sinais e do contexto sintético.

A suíte da Fase 7 passou em **105 testes**, incluindo regressões da Fase 6. A verificação HTTP executa dois cenários de risco e uma conversa com o Ollama real; as respostas e os eventos ficam em `docs/evidencias`. As métricas de treinamento da Fase 6 continuam documentadas no repositório anterior.

**Sem serviços IBM:** o enunciado não exige Watson. A conversa e as recomendações são executadas com o LLM local; da Fase 5 foram aproveitados somente os textos e a organização conversacional pertinentes, sem SDK, conta ou chave IBM.

O modelo da Fase 6 recebe variáveis fisiológicas e operacionais. Temperatura e batimentos do simulador não preenchem, sozinhos, todo o contrato do modelo. O [contrato](docs/contrato-api.md) documenta o mapeamento das entradas e a origem dos campos adicionais, distinguindo sinais simulados, valores de contexto e resultados da IA.

## ⚙️ 2. Arquitetura Integrada

Fluxo previsto no enunciado:

```text
Sensor simulado
      ↓
MicroPython / Wokwi
      ↓
Backend Python
      ↓
APIs e motores de IA — modelo preditivo e LLM
      ↓
Interfaces Web e Mobile
```

| Componente | Responsabilidade planejada |
| --- | --- |
| IoT / MicroPython | Capturar e processar temperatura e batimentos simulados; apresentar feedback visual por LED/OLED |
| Backend Python | Validar e integrar dados, conectar os motores de IA e disponibilizar os resultados às interfaces |
| Modelo preditivo | Calcular o risco a partir das entradas compatíveis com o modelo treinado |
| LLM / assistência conversacional | Integrar os recursos das fases anteriores e apresentar recomendações simuladas com o contexto necessário |
| Web | Disponibilizar login, dados cardíacos, indicadores de risco e recomendações pela URL pública |
| Mobile | Disponibilizar os fluxos do aplicativo Android instalado a partir do APK |

As decisões estão em [arquitetura planejada](docs/arquitetura.md): FastAPI, SQLite, sensores por HTTPS e atualização das interfaces por consulta periódica. O diagrama final refletirá a execução validada.

**Execução gratuita:** backend e Ollama no mesmo computador, com acesso externo à API por Cloudflare Quick Tunnel. Essa configuração de demonstração depende de computador ligado e túnel ativo; não é hospedagem permanente em nuvem. A URL temporária será distribuída às interfaces por configuração pública na Vercel, sem credenciais. A disponibilidade para a correção posterior precisa ser validada com o tutor.

## 🌐 3. Aplicação Web e Deploy

A aplicação Web será desenvolvida/adaptada em **React + Vite** e publicada na **Vercel**.

Entregas previstas:

- Configuração de `vercel.json` com suporte a rotas SPA.
- Conexão da interface ao backend integrador.
- Deploy automático acionado por push no GitHub (**CI/CD**).
- Validação de login e visualização dos dados cardíacos na URL pública.
- Prints comprobatórios do deploy concluído.

## 📱 4. Aplicativo Mobile

O aplicativo será desenvolvido/adaptado em **React Native + Expo**, com geração de **APK pelo Expo EAS Build**.

Entregas previstas:

- `app.json` com `android.package` em formato de domínio invertido.
- `eas.json` com perfil `preview` configurado para gerar APK.
- Link direto do build no dashboard do Expo ou QR Code.
- Instalação em dispositivo Android real, com validação de login e dados cardíacos.
- Instruções de instalação e evidências da execução.

## 🔌 5. IoT e MicroPython

O circuito anterior foi convertido para **MicroPython no ESP32**. O DHT22 e o potenciômetro alimentam as leituras de temperatura e BPM, mostradas no OLED. LEDs distinguem sinais dentro e fora da faixa de entrada do modelo. O botão azul permite pausar o envio e testar a fila em memória.

O [guia do IoT](IoT/README.md) descreve o circuito, a execução no Wokwi e a configuração da API por HTTPS. O transporte foi implementado com validação do certificado. A integração pelo gateway público do simulador ainda está em validação.

## 🎨 6. Experiência do Usuário

O trabalho de UX prioriza a leitura dos indicadores de risco e a compreensão do fluxo de informações por médico e paciente.

- Protótipo das telas de login, painel de dados e risco/recomendações.
- Organização visual, contraste, legibilidade e navegação.
- Estados de carregamento, ausência de dados e erro de comunicação.
- Verificação da interface em telas Web e Mobile.

## 🚀 7. Instalação e Execução

O [guia do backend](Backend/README.md) contém instalação com Python 3.12, geração das configurações locais, execução da API, Ollama, testes e abertura do túnel HTTPS. As dependências de execução estão fixadas em `Backend/requirements.txt`.

O [guia do IoT](IoT/README.md) descreve a reprodução do circuito. Web e Mobile receberão seus comandos quando forem implementados. O classificador visual da Fase 4 permanece indisponível enquanto os pesos e as classes não forem recuperados; a API informa esse estado com `503`.

As configurações de ambiente serão documentadas por exemplos sem credenciais. Senhas, tokens e arquivos `.env` com valores reais não devem ser incluídos no repositório.

### Instalação do APK

Após disponibilizar o build, esta seção receberá o link/QR Code, os passos de instalação e as evidências de validação em Android real.

## 🎥 8. Demonstração e Entrega Acadêmica

| Entregável | Situação inicial |
| --- | --- |
| Estrutura, inventário, arquitetura e contratos | Documentados; contrato HTTP implementado |
| Backend, modelo preditivo e conversa local | Implementados; 105 testes automatizados e validação HTTP com motores reais |
| Código completo Web, Mobile, Backend e IoT no GitHub privado | Backend e firmware disponíveis; interfaces pendentes |
| Acesso do tutor ao repositório | Convite informado pela equipe; aceitação a confirmar |
| Web pública na Vercel com CI/CD | Pendente |
| APK no Expo EAS Build | Pendente |
| Projeto público MicroPython no Wokwi | Circuito executado no editor; publicação em andamento |
| Diagrama da arquitetura final | Pendente |
| Relatório técnico PDF — **máximo de 5 páginas** | Pendente |
| Vídeo do fluxo fim a fim — **até 5 minutos** | Pendente |
| Prints do deploy e instruções de instalação | Pendentes |

O vídeo deverá demonstrar o fluxo desde o Wokwi até a atualização do dado na aplicação publicada e no APK, mostrando o processamento de IA correspondente.

### Links de entrega

| Recurso | Link / estado |
| --- | --- |
| Aplicação Web na Vercel | A publicar |
| Build APK no Expo / QR Code | A gerar |
| Simulação pública no Wokwi | A publicar |
| Relatório técnico PDF | A produzir |
| Vídeo demonstrativo | A gravar e disponibilizar |
| Planejamento no Trello | [Quadro FIAP](https://trello.com/b/xOYTjFR3/fiap) |

### Critérios de avaliação

| Critério | Pontos |
| --- | ---: |
| URLs funcionais e build mobile acessível | 3,0 |
| Unificação funcional do backend, interfaces e motores de IA | 2,5 |
| Conversão e funcionamento dos sensores no Wokwi | 1,5 |
| Clareza do diagrama e comunicação de dados | 1,5 |
| Qualidade do README, PDF e demonstração | 1,5 |
| **Total principal** | **10,0** |

O enunciado prevê 1 ponto extra para equipes de 4 a 5 integrantes. A equipe identificada neste README é composta por duas pessoas. Os desafios **Ir Além não fazem parte do escopo** deste projeto.

Prazo e formato exato da submissão serão conferidos no Portal do Aluno. O formato de entrega da Fase 6 não será aplicado automaticamente à Fase 7.

## 🛡️ Uso Responsável e Referências

O desenvolvimento utiliza simulações acadêmicas e não se destina a decisões sobre pacientes reais. As evidências finais deverão distinguir protótipos, dados simulados, resultados calculados e funcionalidades efetivamente integradas.

- [CardioIA — Fase 6](https://github.com/lab-ia-shared/CARDIO-IA-6): modelo preditivo e arquitetura multiagente que servem de base para esta evolução.
- [CardioIA — Fase 5](https://github.com/lab-ia-shared/Cardio-IA-5): etapa anterior de assistência conversacional.
- Material da FIAP: **Fase 7, Capítulo 1 — Da Construção de Módulos à Solução Integrada** e enunciado **Coração Sob Controle: Previsão de Crises com IA**.
