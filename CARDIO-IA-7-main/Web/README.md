# CardioIA Web

Interface React + Vite integrada ao contrato em [`docs/contrato-api.md`](../docs/contrato-api.md). Inclui login, seleção de caso, painel de sinais e risco, histórico de medições, solicitação de análise e conversa assíncrona com a API.

## Desenvolvimento

```bash
npm install
npm run dev
```

Configure `public/runtime-config.json` com a URL pública da API (sem `/api/v1`), por exemplo:

```json
{"config_version":1,"api_base_url":"https://api.example.com"}
```

A API precisa autorizar a origem exata da interface em `CARDIOIA_ALLOWED_ORIGINS`. O usuário inicial `demo` e sua senha são definidos no ambiente local do backend; não há senha demonstrativa embutida na aplicação. Sem URL de API, a interface explica a configuração necessária e não usa dados de demonstração como se fossem dados reais.

## Vercel

Configure o Root Directory do projeto como `CARDIO-IA-7-main/Web`, preserve os valores padrão de build (`npm run build`, saída `dist`) e publique por integração com o repositório. `/runtime-config.json` é público e aceita somente a URL base da API; não coloque tokens ou credenciais nele. A SPA mantém o roteamento pelo `vercel.json`.

O aplicativo usa dados sintéticos acadêmicos. Não é um produto clínico e não deve apoiar diagnóstico, prescrição ou decisões sobre pacientes reais.
