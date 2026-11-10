# CardioIA Fase 7 — ESP32 no Wokwi

O circuito da [Fase 3](https://github.com/lab-ia-shared/Cardio-IA-3/tree/main/wokwi_hardware) foi convertido para MicroPython. O DHT22 mede a temperatura simulada e o potenciômetro representa BPM de 40 a 180. A leitura roda a cada três segundos e aparece no OLED e no monitor serial.

| Componente | Ligação no ESP32 |
| --- | --- |
| DHT22 | GPIO 15 |
| Potenciômetro | GPIO 34 (ADC1) |
| Botão azul | GPIO 12, ativo em nível baixo |
| OLED SSD1306 | SDA GPIO 21, SCL GPIO 22, endereço `0x3c` |
| LED verde e vermelho | GPIO 25 e 26, resistores de 220 Ω |

O LED verde sinaliza que a leitura individual está na faixa de entrada do modelo (10–40 °C e 50–150 BPM). O vermelho indica leitura fora da faixa ou falha do sensor. São limites do experimento, sem significado clínico. O backend ainda considera a janela recente de BPM e os dados de contexto para calcular risco.

## Abrir a simulação

1. Crie um projeto **MicroPython on ESP32** no Wokwi. Cole o conteúdo de `main.py` e `diagram.json` nas abas existentes.
2. Em **Upload file(s)**, adicione `cardioia_iot.py` e `ca.txt`. Esses nomes são usados pelo programa. O arquivo `ca.txt` contém raízes públicas GTS Root R1/R4 e ISRG Root X1 em PEM.
3. Inicie a simulação. O OLED mostra temperatura, BPM, faixa e estado da rede. Gire o potenciômetro até o máximo para obter 180 BPM e ver o alerta. Clique no DHT22 para variar a temperatura.

O firmware inicia em modo local. Essa demonstração funciona sem API, credenciais ou serviço pago.

## Enviar ao backend

Inicie a API, o Ollama e o túnel conforme o [guia do backend](../Backend/README.md). No monitor serial, envie a linha abaixo, substituindo os dois valores. Use uma instância com dados simulados e um token de telemetria exclusivo da demonstração.

```text
api https://ENDERECO-DO-TUNEL TOKEN_DE_TELEMETRIA
```

A configuração dura apenas na memória da sessão. Não coloque tokens no código, em links, prints ou no projeto público. O firmware valida o certificado e o nome do servidor e sincroniza o relógio para TLS quando necessário. O campo `measured_at` é nulo: a API registra o recebimento, e a leitura mantém seu `uptime_ms` e sequência.

O botão azul pausa e retoma os envios. Enquanto a rede está pausada ou falha, a fila de até 20 registros continua recebendo amostras e descarta as mais antigas que ainda não foram tentadas, preservando a primeira leitura da sessão e um envio de resultado incerto. A primeira leitura abre a sessão no servidor. Depois, a leitura atual tem prioridade sobre o histórico. Uma repetição preserva os mesmos campos, para a API reconhecer duplicatas. Os reenvios respeitam o limite de requisições e recebem espera maior em caso de falha temporária. A fila não sobrevive a um reinício.

O monitor serial mostra o status HTTP e `boot_id`/sequência. Use `local` para interromper os envios e limpar a configuração em memória. O [contrato](../docs/contrato-api.md) descreve como localizar a medição e o resultado de IA no painel da API. O túnel é temporário, e o gateway público do Wokwi é para dados de teste. Veja a [documentação de Wi-Fi do Wokwi](https://docs.wokwi.com/guides/esp32-wifi) e a [documentação TLS do MicroPython](https://docs.micropython.org/en/latest/library/ssl.html).
