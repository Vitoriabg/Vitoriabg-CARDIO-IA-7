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

O EAS solicita a vinculação do projeto Expo na primeira execução. Faça login na conta Expo da equipe, gere o APK e valide a instalação, login e consulta de sinais em um dispositivo Android físico antes de divulgar o link do build. O APK e o deploy público ainda precisam dessa validação final.

Os dados e protocolos deste aplicativo são sintéticos e acadêmicos; não usar para decisões clínicas.
