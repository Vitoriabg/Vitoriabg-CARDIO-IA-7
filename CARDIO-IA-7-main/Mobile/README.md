# CardioIA Mobile

Aplicativo React Native + Expo para autenticação e consulta do caso, dos indicadores e do histórico pela mesma API usada na Web. O identificador Android é `com.cardioia.fase7`; o perfil EAS `preview` gera APK.

## Desenvolvimento local

```bash
npm install
npx expo start
```

Defina `EXPO_PUBLIC_CONFIG_URL` como a URL do `runtime-config.json` publicado, por exemplo `https://<site-vercel>/runtime-config.json`. Esse documento contém somente `config_version` e `api_base_url` (URL base da API, sem `/api/v1`). A API deve autorizar a origem da Web; para o aplicativo nativo, configure também a política de CORS/cliente conforme o ambiente do backend. Nenhuma senha ou token é incluído no bundle ou na configuração pública.

## Gerar APK

```bash
npx eas-cli build --platform android --profile preview
```

Antes do primeiro build, autentique-se com `npx eas-cli@latest login` e vincule este app a um projeto Expo com `npx eas-cli@latest init`; isso grava o `projectId` real em `app.json`. Em seguida, gere o APK com o comando acima. A conta Expo e o projeto EAS precisam estar acessíveis; não use um ID fictício. Instale o APK e valide login e consulta de sinais em um dispositivo Android físico antes de divulgar o link do build.

Os dados e protocolos deste aplicativo são sintéticos e acadêmicos; não usar para decisões clínicas.
