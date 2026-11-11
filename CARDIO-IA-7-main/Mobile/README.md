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

Projeto EAS vinculado: [@vivibggg/cardioia-fase7](https://expo.dev/accounts/vivibggg/projects/cardioia-fase7). O `projectId` real está em `app.json` e o perfil `preview` gera APK. O [APK de teste](https://expo.dev/artifacts/eas/kwckbyNm3C6sTptddnAl8gAI4TydZLmmWoWirRrl38I.apk) já está pronto. Instale-o em um Android físico e valide login e sinais com a API pública configurada. Não inclua `EXPO_TOKEN` no código ou no Git; revogue o token após o build se não precisar de builds futuros.

Os dados e protocolos deste aplicativo são sintéticos e acadêmicos; não usar para decisões clínicas.
