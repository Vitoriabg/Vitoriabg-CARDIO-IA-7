import dht
import framebuf
import json
import network
import os
import select
import socket
import ssl
import sys
import time
from binascii import hexlify
from machine import ADC, I2C, Pin

DEVICE_ID = "esp32-demo-01"
INTERVALO_MS = 3000
ENVIO_MS = 2500
LIMITE_FILA = 20


class Tela:
    def __init__(self):
        self.i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
        self.memoria = bytearray(1024)
        self.pixels = framebuf.FrameBuffer(self.memoria, 128, 64, framebuf.MONO_VLSB)
        self.i2c.writeto(0x3C, bytes((0, 0xAE, 0x20, 0, 0x40, 0xA1, 0xC8, 0xA8, 63,
                                     0xD3, 0, 0xDA, 0x12, 0xD5, 0x80, 0x8D, 0x14, 0xAF)))

    def mostrar(self, *linhas):
        self.pixels.fill(0)
        for i, texto in enumerate(linhas):
            self.pixels.text(texto[:16], 0, i * 10, 1)
        self.i2c.writeto(0x3C, bytes((0, 0x21, 0, 127, 0x22, 0, 7)))
        self.i2c.writevto(0x3C, (b"\x40", self.memoria))


def bpm_do_adc(valor):
    return 40 + (max(0, min(4095, valor)) * 140 + 2047) // 4095


def dentro_da_faixa(temperatura, bpm):
    return 10 <= temperatura <= 40 and 50 <= bpm <= 150


class Fila:
    def __init__(self):
        self.itens = []
        self.aberta = False
        self.perdidas = 0

    def guardar(self, leitura):
        for dados, tentou in self.itens:
            if not tentou and dados["sequence"] != 0:
                dados["historical"] = True
        self.itens.append([leitura, False])
        if len(self.itens) > LIMITE_FILA:
            for i, (dados, tentou) in enumerate(self.itens[:-1]):
                if not tentou and (self.aberta or dados["sequence"] != 0):
                    self.itens.pop(i)
                    self.perdidas += 1
                    break

    def proxima(self):
        if not self.aberta:
            return self.itens[0]
        for item in self.itens:
            if item[1]:
                return item
        if not self.itens[-1][0]["historical"]:
            return self.itens[-1]
        return self.itens[0]

    def confirmar(self, item):
        self.itens.remove(item)
        self.aberta = True


def separar_configuracao(linha):
    campos = linha.split()
    if len(campos) != 3 or campos[0].lower() != "api":
        raise ValueError("Use: api https://HOST TOKEN")
    url, token = campos[1].rstrip("/"), campos[2]
    if not url.startswith("https://"):
        raise ValueError("Use um endereco HTTPS.")
    host = url[8:]
    if host.endswith("/api/v1"):
        host = host[:-7]
    if not host or len(host) > 253 or "." not in host or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for c in host.lower()):
        raise ValueError("Endereco invalido.")
    if not 32 <= len(token) <= 256 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in token):
        raise ValueError("Token invalido.")
    return host, token


def criar_tls():
    if time.gmtime()[0] < 2025:
        import ntptime
        ntptime.settime()
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    contexto.verify_mode = ssl.CERT_REQUIRED
    with open("ca.txt", "rb") as arquivo:
        contexto.load_verify_locations(cadata=arquivo.read())
    return contexto


def enviar(contexto, host, token, leitura):
    corpo = json.dumps(leitura).encode()
    cabecalho = ("POST /api/v1/telemetry HTTP/1.1\r\nHost: %s\r\n"
                 "X-Device-Token: %s\r\nContent-Type: application/json\r\n"
                 "Content-Length: %d\r\nConnection: close\r\n\r\n") % (host, token, len(corpo))
    endereco = socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)[0][-1]
    conexao = socket.socket()
    seguro = None
    try:
        conexao.settimeout(5)
        conexao.connect(endereco)
        seguro = contexto.wrap_socket(conexao, server_hostname=host)
        pacote = cabecalho.encode() + corpo
        while pacote:
            n = seguro.write(pacote)
            if not n:
                raise OSError("Envio interrompido")
            pacote = pacote[n:]
        status = seguro.readline().split()
        if len(status) < 2 or not status[0].startswith(b"HTTP/"):
            raise OSError("Resposta HTTP invalida")
        return int(status[1])
    finally:
        if seguro is not None:
            seguro.close()
        else:
            conexao.close()


def main():
    tela = Tela()
    sensor = dht.DHT22(Pin(15))
    pot = ADC(Pin(34), atten=ADC.ATTN_11DB)
    botao = Pin(12, Pin.IN, Pin.PULL_UP)
    verde, vermelho = Pin(25, Pin.OUT), Pin(26, Pin.OUT)
    wifi = network.WLAN(network.STA_IF)
    entrada = select.poll()
    entrada.register(sys.stdin, select.POLLIN)
    linha, destino, tls = "", None, None
    fila = Fila()
    offline, pressionado = False, False
    boot_id, sequencia = "", 0
    inicio = time.ticks_ms()
    amostra_em = envio_em = wifi_em = inicio
    debounce_em = inicio
    atraso = ENVIO_MS
    temperatura, bpm, faixa = None, None, "Inicializando"
    envio = "Modo local"
    tela_anterior = None
    uptime = 0
    anterior = inicio
    print("CardioIA Fase 7 | sinais simulados")
    print("Botao azul: alterna rede. Serial: api https://HOST TOKEN ou local.")
    while True:
        agora = time.ticks_ms()
        uptime += time.ticks_diff(agora, anterior)
        anterior = agora
        apertado = botao.value() == 0
        if apertado != pressionado and time.ticks_diff(agora, debounce_em) >= 150:
            pressionado, debounce_em = apertado, agora
            if apertado:
                offline = not offline
                print("Rede pausada" if offline else "Rede liberada")
        while entrada.poll(0):
            letra = sys.stdin.read(1)
            if not letra:
                break
            if letra in "\r\n":
                if linha:
                    if linha.strip().lower() == "local":
                        destino, tls = None, None
                        fila = Fila()
                        wifi.active(False)
                        envio = "Modo local"
                    else:
                        try:
                            destino = separar_configuracao(linha)
                        except ValueError as erro:
                            print(erro)
                        else:
                            boot_id, sequencia = "wokwi-" + hexlify(os.urandom(12)).decode(), 0
                            fila, tls = Fila(), None
                            offline = False
                            wifi.active(True)
                            envio_em = wifi_em = agora
                            atraso = ENVIO_MS
                            print("API configurada para a sessao", boot_id)
                    linha = ""
            elif letra in "\x08\x7f":
                linha = linha[:-1]
            elif len(linha) < 600 and ord(letra) >= 32:
                linha += letra
        if time.ticks_diff(agora, amostra_em) >= 0:
            amostra_em = time.ticks_add(agora, INTERVALO_MS)
            try:
                sensor.measure()
                temperatura = sensor.temperature()
                if not -40 <= temperatura <= 80:
                    raise ValueError("DHT22 fora da faixa")
                bpm = bpm_do_adc(pot.read())
                faixa = "Faixa modelo" if dentro_da_faixa(temperatura, bpm) else "Fora da faixa"
                print("DHT22 %.1f C | %d BPM | %s" % (temperatura, bpm, faixa))
                if destino:
                    fila.guardar({"schema_version": 1, "device_id": DEVICE_ID, "boot_id": boot_id,
                                  "sequence": sequencia, "measured_at": None, "uptime_ms": uptime,
                                  "temperatura": temperatura, "bpm": bpm, "historical": False})
                    sequencia += 1
            except (OSError, ValueError):
                temperatura, bpm, faixa = None, None, "Falha no DHT22"
                print("Falha na leitura; nenhum dado inventado.")
        if destino and not offline:
            if not wifi.isconnected():
                envio = "Conectando WiFi"
                if time.ticks_diff(agora, wifi_em) >= 0:
                    wifi_em = time.ticks_add(agora, 10000)
                    try:
                        wifi.connect("Wokwi-GUEST", "")
                    except OSError:
                        pass
            elif fila.itens and time.ticks_diff(agora, envio_em) >= 0:
                item = fila.proxima()
                dados = item[0]
                item[1] = True  # Uma tentativa ambigua deve reenviar o mesmo JSON.
                try:
                    if tls is None:
                        tls = criar_tls()
                    status = enviar(tls, destino[0], destino[1], dados)
                    envio = "API HTTP %d" % status
                    print("API %d | %s seq=%d historico=%s" % (status, boot_id, dados["sequence"], dados["historical"]))
                    if status in (200, 201):
                        fila.confirmar(item)
                        atraso = ENVIO_MS
                    elif status in (401, 403, 404, 409, 422) or 300 <= status < 400:
                        offline = True
                        print("Envio pausado; confira a API e reconfigure pelo serial.")
                    else:
                        atraso = min(30000, atraso * 2)
                except (OSError, ValueError, ImportError, AttributeError) as erro:
                    envio = "Falha HTTPS"
                    print("Falha HTTPS:", type(erro).__name__, getattr(erro, "errno", None))
                    atraso = min(30000, atraso * 2)
                envio_em = time.ticks_add(time.ticks_ms(), atraso)
        verde.value(faixa == "Faixa modelo")
        vermelho.value(faixa != "Faixa modelo")
        linhas = ("CardioIA Fase 7", "TEMP --" if temperatura is None else "TEMP %.1f C" % temperatura,
                  "BPM --" if bpm is None else "BPM %d" % bpm, faixa,
                  "Rede pausada" if offline else envio, "Fila %d/%d P:%d" % (len(fila.itens), LIMITE_FILA, fila.perdidas))
        if linhas != tela_anterior:
            tela.mostrar(*linhas)
            tela_anterior = linhas
        time.sleep_ms(50)


if __name__ == "__main__":
    main()
