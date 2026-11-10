# Validação do IoT — 10/11/2026

O ESP32 executou o firmware em MicroPython 1.28.0 no editor Wokwi. O DHT22 foi inicializado em 26 °C. Com o potenciômetro no valor 300, o OLED mostrou 81 BPM e o LED verde acendeu. Ao mover o potenciômetro ao máximo, o monitor serial e o OLED mostraram 180 BPM e `Fora da faixa`. Esses estados descrevem a faixa de entrada do modelo, não uma avaliação clínica.

O teste da fila confirmou o limite de 20 itens, a preservação da primeira sequência, a prioridade para a leitura atual e o reenvio do mesmo payload após falha ambígua.

No [teste de transporte no computador](iot_transporte_host.json), a função de envio do firmware foi executada em CPython com adaptação da interface de socket TLS. O servidor de teste estava isolado e continha apenas dados fictícios. A API recebeu `201` para os primeiros envios e `200` para duplicatas. A leitura de 180 BPM foi registrada com `out_of_domain`; a de 81 BPM produziu previsão e análise multiagente com Ollama. O registro contém identificadores e horários sem credenciais.

O teste no computador não substitui a validação da rede do ESP32 no Wokwi. No editor do simulador, Wi-Fi, DNS e TCP conectaram, mas a negociação TLS terminou com `MBEDTLS_ERR_SSL_CONN_EOF` antes de enviar telemetria. O túnel respondia ao teste HTTPS externo no computador. A verificação de certificados foi mantida.

A publicação do link público ficou pendente de login no Wokwi. O circuito pode ser reproduzido pelo [guia](../../IoT/README.md). A conexão do simulador à API e o consumo pelas interfaces seguem pendentes.
