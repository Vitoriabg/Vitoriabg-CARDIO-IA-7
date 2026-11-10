"""Cria a configuração privada para execução local, sem substituir arquivo existente."""

import os
import secrets
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2]
    target = root / ".env"
    content = (root / ".env.example").read_text()
    for key, value in {"CARDIOIA_JWT_SECRET": secrets.token_urlsafe(48),
                       "CARDIOIA_DEMO_PASSWORD": secrets.token_urlsafe(18),
                       "CARDIOIA_DEVICE_TOKEN": secrets.token_urlsafe(32)}.items():
        content = content.replace(key + "=\n", key + "=" + value + "\n")
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("A configuração local já existe; nenhum valor foi alterado.")
        return
    with os.fdopen(descriptor, "w") as stream:
        stream.write(content)
    print("Configuração privada criada em .env na raiz. Os valores não foram exibidos.")


if __name__ == "__main__":
    main()
