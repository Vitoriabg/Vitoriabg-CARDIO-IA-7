# Planejamento da Fase 7

## Escopo

Entregar um MVP integrado da CardioIA com Web React + Vite na Vercel, aplicativo React Native + Expo em APK, backend Python, inferência preditiva, assistência conversacional e simulação ESP32 em MicroPython no Wokwi. O enunciado da atividade define a entrega; o capítulo fornece o contexto das disciplinas.

Os desafios Ir Além estão fora do escopo. Mineração de processos, CBIR, benchmarks de supercomputação, novos modelos quânticos, voz e publicação em lojas não serão adicionados como entregas independentes.

## Situação em 10/11/2026

O repositório privado [Nico-Araujo/CARDIO-IA-7](https://github.com/Nico-Araujo/CARDIO-IA-7) contém o planejamento e a implementação do backend e IA. A API foi validada com o modelo e o Ollama reais; Web, Mobile e MicroPython seguem nas próximas listas. A inspeção das fases anteriores está registrada no [inventário](inventario.md).

## Fluxo demonstrável

1. Entrar na Web ou no APK com uma conta de demonstração.
2. Alterar temperatura ou potenciômetro de BPM no Wokwi.
3. Enviar a leitura para a API Python por HTTPS.
4. Validar, armazenar e converter os sinais para o contrato do modelo.
5. Atualizar o painel com a leitura, o risco calculado e a identificação da origem dos dados.
6. Executar os agentes e exibir a recomendação simulada com estado e horário próprios.
7. Consultar o assistente conversacional com a referência do caso simulado.

A integração de texto das Fases 1/2/5 e a recuperação do classificador de imagens da Fase 4 serão tratadas no backend. O modelo de imagens depende da obtenção do artefato treinado; seu resultado não será substituído por valor ilustrativo.

## Ordem de implementação

| Ordem | Lista / cartões | Resultado esperado |
| --- | --- | --- |
| 1 | Planejamento — F7-01 a F7-03 | Inventário, escopo, pastas, decisões e contratos |
| 2 | Backend e IA — F7-04 a F7-07 | API, autenticação, persistência e integração dos módulos |
| 3 | Web e Mobile — F7-08 a F7-13 | Interfaces, deploy automático, APK e teste real |
| 4 | IoT e MicroPython — F7-14 a F7-16 | Circuito convertido, feedback e envio de sinais |
| 5 | Integração e Validação — F7-17 | Fluxo Wokwi → IA → Web/APK validado |
| 6 | Documentação e Entrega — F7-18 a F7-22 | Diagrama final, PDF, README, vídeo e conferência |

F7-07 preparará a forma de disponibilização da API; a conferência externa será repetida com as interfaces publicadas. Os contratos e exemplos permitem desenvolver as telas antes de o backend estar disponível.

## Divisão de responsabilidades

| Integrante | Trabalho principal | Pode iniciar sem integração |
| --- | --- | --- |
| Nicolas Antonio Silva Araujo — RM 566307 | Repositório, API, módulos de IA, conversão IoT, integração, builds e deploy | Inventário e implementação técnica |
| Vitória Pereira Bagatin — RM 566519 | Protótipo, UX, textos das telas, organização do README e relatório | Login, painel, risco/recomendações, carregamento/erro com os exemplos do contrato |

Vitória pode preparar a documentação e o roteiro; prints, resultados, diagrama final e gravação dependem da integração. O protótipo do F7-08 pode ser produzido em paralelo à lista IoT. A implementação React/Expo, autenticação, integração com a API, Vercel e APK ficam com Nicolas. As datas serão definidas a partir do prazo publicado no Portal, ainda não informado.

## Critérios de aceite

| Entrega | Evidência necessária |
| --- | --- |
| Web e CI/CD — 3,0 pontos em conjunto com APK | URL Vercel funcional, rota SPA recarregável e deploy iniciado por push |
| Mobile | APK EAS instalável, link/QR Code e login/dados em Android real |
| Backend e motores de IA — 2,5 pontos | Respostas calculadas a partir de uma leitura recebida e interação conversacional real |
| MicroPython/Wokwi — 1,5 pontos | Script `.py`, projeto público, variação de sinais e feedback LED/OLED |
| Diagrama e fluxo — 1,5 pontos | Arquitetura coerente com a execução e origem/destino dos dados |
| Documentação e demonstração — 1,5 pontos | README com links/prints/instalação, PDF de até 5 páginas e vídeo de até 5 minutos |

## Decisões

- Custo de serviços: **zero**, conforme definido pela equipe.
- Serviços IBM e Watson não serão usados. O enunciado não os exige; o conteúdo conversacional anterior será adaptado para execução local.
- API única em FastAPI; SQLite para o MVP; contrato HTTP JSON versionado em `/api/v1`.
- Ollama e backend no mesmo computador, preservando a restrição de loopback da Fase 6.
- Acesso externo de demonstração por Cloudflare Quick Tunnel, sujeito à validação do tutor quanto à disponibilidade. Não é hospedagem permanente em nuvem.
- Web na Vercel Hobby; APK pela modalidade gratuita do EAS, respeitando as cotas disponíveis.
- ESP32 envia HTTPS a cada 3 segundos; interfaces consultam o painel a cada 3 segundos enquanto estiverem abertas.
- O painel apresenta separadamente risco preditivo, triagem textual e classificação de imagem; essas saídas não são intercambiáveis.
- Nada será marcado como testado ou publicado antes da verificação correspondente.

Detalhes: [arquitetura](arquitetura.md) e [contrato de dados e API](contrato-api.md).

## Pendências identificadas

| Pendência | Tratamento |
| --- | --- |
| Acesso do tutor | A equipe informou o envio do convite a `fiap-tutoria`. Aceitação e acesso efetivo ainda serão confirmados. |
| Participação da dupla no GitHub | A conta `Vitoriabg` aparece no histórico da Fase 6; acesso ao repositório novo ainda precisa ser conferido. |
| Credencial no código público da Fase 5 | Revogar na IBM e substituir configurações por variáveis de ambiente. O valor não será transferido. |
| Pesos da Fase 4 | O notebook salva `cardioia_vgg16_modelo.keras`, mas esse arquivo não está no GitHub. Recuperar o download/Drive ou repetir o treino e exportar também as classes. |
| Backend gratuito | Exige computador ligado e túnel ativo. O endereço muda ao reiniciar. Validar se essa disponibilidade atende à correção assíncrona; não afirmar implantação permanente. |
| Dependências | Ambiente Python 3.12 resolvido em `Backend/requirements.txt`, com 105 testes aprovados e `pip check` sem conflitos. |
| Prazo e envio | Conferir no Portal; não presumir o TXT usado na Fase 6. |

F7-02 permanece aberto até confirmar o acesso efetivo do tutor. F7-07 depende da validação com Web publicada e APK real. O planejamento não equivale à conclusão do MVP.
