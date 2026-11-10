# Contrato de dados e API — v1

Contrato implementado no backend FastAPI. Consulte [execução e validação](../Backend/README.md) para iniciar a API e disponibilizá-la por HTTPS. Os JSONs em `exemplos` são dados fictícios de formato; as respostas de execuções reais ficam em `evidencias`.

## Convenções

Base: `API_BASE_URL/api/v1`. JSON UTF-8, nomes em `snake_case`, datas RFC 3339 com fuso explícito e respostas em UTC. Identificadores de caso, medição, análise e conversa são strings opacas. O caso é simulado e não contém nome/documento de paciente.

Usuários enviam `Authorization: Bearer <access_token>`. Dispositivos usam `X-Device-Token`. Esses valores nunca entram em exemplos versionados, URLs ou configuração pública.

## Rotas

| Método / rota | Entrada | Saída / regra |
| --- | --- | --- |
| `GET /health` | Sem autenticação | `200` com estado básico; sem detalhes de infraestrutura |
| `POST /auth/login` | `username`, `password` | `200`: `access_token`, `token_type: bearer`, `expires_in: 3600`; `401` para credenciais inválidas |
| `GET /cases` | Sessão | Casos permitidos para o usuário, `items` e `next_cursor` |
| `GET /cases/{case_id}/context` | Sessão | Contexto sintético e revisão atual |
| `PUT /cases/{case_id}/context` | Contexto completo + `expected_revision` | Nova revisão; `409` se outra atualização ocorreu |
| `POST /telemetry` | [Telemetria](contratos/telemetria.schema.json), token do dispositivo | `201`: `measurement_id`, `received_at`, `duplicate: false`; reenvio idêntico retorna `200`, mesmo identificador e `duplicate: true` |
| `GET /cases/{case_id}/dashboard` | Sessão | Última medição, previsão, status/origem do contexto e última análise; `measurement: null` enquanto não houver dados |
| `GET /cases/{case_id}/measurements` | Sessão, `limit` entre 1 e 100, `cursor` opcional | Histórico ordenado por recebimento, `items` e `next_cursor` |
| `POST /cases/{case_id}/analyses` | `measurement_id`, `context_revision` | `202`: `analysis_id`, `status: queued`; não duplica tarefa da mesma entrada |
| `GET /analyses/{analysis_id}` | Sessão | Estado, referências da entrada, horários, erro ou recomendação concluída |
| `POST /conversations` | `case_id` | `201`: `conversation_id` vinculado ao usuário |
| `POST /conversations/{conversation_id}/messages` | `text` de 1 a 2000 caracteres | `202`: `message_id`, `status: queued`; processamento local assíncrono |
| `GET /conversations/{conversation_id}/messages/{message_id}` | Sessão | Estado e resposta quando concluída, sem misturar sessões |
| `POST /text-triage` | `text` de 1 a 2000 caracteres, sessão | Sintomas extraídos e triagem textual da Fase 2; campo de origem explícito |
| `POST /image-classifications` | Multipart `image`, sessão, PNG/JPEG até 5 MB | Resultado somente com artefato/classes validados; `503` enquanto indisponível |

O endpoint de imagens retorna `503`: os pesos e o mapeamento de classes da Fase 4 ainda não foram recuperados. O adaptador foi preparado, mas não validado com um modelo real. O corpo HTTP é limitado antes do processamento; a rota limita o arquivo a 5 MB e o adaptador limita a imagem a 16 milhões de pixels.

## Telemetria

Campos definidos em [telemetria.schema.json](contratos/telemetria.schema.json) e [exemplo](exemplos/telemetria.json):

| Campo | Significado |
| --- | --- |
| `schema_version` | Inteiro fixo `1` |
| `device_id` | Identificador registrado, sem dados pessoais |
| `boot_id` | Identificador gerado a cada inicialização; evita colisões ao reiniciar a sequência |
| `sequence` | Inteiro não negativo, incrementado a cada leitura |
| `measured_at` | Data com fuso se o relógio foi sincronizado; `null` quando desconhecida |
| `uptime_ms` | Tempo desde a inicialização, em milissegundos |
| `temperatura` | Graus Celsius, intervalo aceito do DHT22 de -40 a 80 |
| `bpm` | Batimentos simulados por minuto, 40 a 180 |
| `historical` | `true` quando reenviado do buffer; não deve substituir a leitura atual por um dado atrasado |

Na mesma sessão, a leitura atual é a de maior sequência aceita. Entre inicializações, o servidor mantém a sessão ativa registrada pelo dispositivo. Leituras de sessões encerradas ficam apenas no histórico; o relógio de dispositivo não decide sozinho qual dado é o mais recente.

O servidor sempre define `received_at`. O caso é obtido do cadastro do token, não de um `case_id` enviado pelo ESP32. Reenvio da mesma chave com conteúdo diferente retorna `409`. Falhas de leitura do sensor não geram número inventado.

## Contexto e entrada do modelo

[contexto.schema.json](contratos/contexto.schema.json) e [exemplo](exemplos/contexto.json) especificam os oito campos de contexto. O exemplo retoma os valores do caso da Fase 6, sem pressupor observação de paciente real.

O schema de contexto descreve a resposta armazenada. O `PUT` recebe `{ "expected_revision": 1, "values": { ... } }`, com os oito campos em `values`; a API atribui `source: synthetic` e devolve a revisão incrementada. O cliente não escolhe a nova revisão.

| Feature da Fase 6 | Origem no MVP | Faixa do contrato legado |
| --- | --- | --- |
| `idade_media` | Contexto sintético, anos | 18 a 90 |
| `carga_sistema` | Contexto sintético, % | 0 a 100 |
| `tempo_espera` | Contexto sintético, minutos | 5 a 180 |
| `fc_media` | Média de até 5 amostras recentes de BPM do mesmo dispositivo/caso | 50 a 150 |
| `spo2_media` | Contexto sintético, % | 70 a 100 |
| `pa_sistolica` | Contexto sintético, mmHg | 80 a 200 |
| `temperatura` | Última leitura do DHT22 simulado, °C | 10 a 40 |
| `densidade_eventos` | Contagem sintética conforme a base da Fase 6 | Inteiro ≥ 0 |
| `eventos_24h` | Contagem sintética em 24 h | Inteiro ≥ 0 |
| `disponibilidade_recursos` | Contexto sintético, % | 0 a 100 |

A semântica da densidade é a do experimento anterior; não será inventada uma unidade clínica. A interpretação continua sendo de **risco sistêmico simulado**, sem converter o score em probabilidade clínica individual.

Nenhuma feature será preenchida silenciosamente com zero. Ausência de contexto impede inferência e aparece como `missing_context`. O vetor é montado na ordem dos metadados do modelo. Dados extras, `NaN`, infinito e booleanos em campos numéricos são recusados na implementação.

O ESP32 pode produzir BPM de 40 a 180, enquanto o modelo foi limitado a 50 a 150. A leitura é conservada e exibida, mas a previsão fica `out_of_domain` quando a leitura atual ou uma amostra usada na média está fora dessa faixa, ou quando a temperatura está fora de 10 a 40. Não arredondar/truncar para aparentar validade.

## Previsão e análise

A [previsão](contratos/previsao.schema.json) contém `measurement_id`, `context_revision`, `computed_at`, `status`, `probabilidade`, `classificacao_risco`, `reason` e `window_samples`. Apenas `status: ready` admite score de 0 a 1 e classe `baixo`/`alto`. Nos demais estados, score e classe são nulos e o motivo é obrigatório. A classe segue o corte operacional `p >= 0.5` da Fase 6.

A recomendação mantém os campos do `FinalRecommendation` legado: `probabilidade`, `classificacao_risco`, `protocolos_sugeridos`, `acoes_operacionais` e o aviso acadêmico. A resposta da tarefa também contém `analysis_id`, `measurement_id`, `context_revision`, `requested_at`, `completed_at` e `status`. Resultado só fica disponível quando o estado for `completed`.

Por padrão, uma leitura elegível agenda a análise automaticamente. Novas leituras substituem a pendência anterior do mesmo caso, preservando a tarefa em execução. A previsão numérica é imediata; a recomendação depende do tempo do LLM local. `CARDIOIA_AUTO_ANALYSIS=false` permite usar apenas a solicitação manual.

Ao atualizar o painel, conferir os identificadores: recomendação de uma leitura anterior pode ser exibida com seu horário, mas não como recomendação da leitura atual. Se o servidor reiniciar, tarefas em andamento serão marcadas como falhas, sem resultado fictício.

## Erros

```json
{
  "error": {
    "code": "out_of_domain",
    "message": "Leitura fora do domínio do modelo preditivo.",
    "request_id": "req-exemplo-001"
  }
}
```

`401`: sessão/token ausente ou inválido; `403`: caso sem permissão; `404`: recurso ausente; `409`: revisão ou duplicata conflitante; `413`: arquivo grande; `415`: formato não aceito; `422`: payload inválido; `429`: limite/fila excedidos; `503`: motor ou artefato indisponível. Erros não devolvem segredos, traceback ou caminhos locais.

## Limites iniciais

Telemetria: até 30 envios por minuto por dispositivo. Consulta: até 60 requisições por minuto por usuário. Inferência conversacional/análise solicitada pelo usuário: até 2 pedidos por minuto, mais deduplicação. Polling do painel a cada 3 segundos e somente enquanto a tela estiver ativa. A cada erro transitório, aplicar espera progressiva até 30 segundos, sem abrir fila ilimitada.
