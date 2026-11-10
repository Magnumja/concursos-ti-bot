"""CLI: ``python -m concursos_ti {run|digest|preview}``."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .bot import Config, digest, executar


def _carregar_env(caminho: Path = Path(".env")) -> None:
    """Lê KEY=valor do .env sem sobrescrever o ambiente."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        chave, sep, valor = linha.strip().partition("=")
        if sep and not chave.startswith("#"):
            os.environ.setdefault(chave.strip(), valor.strip().strip("\"'"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="concursos_ti", description="Bot de concursos públicos de TI")
    p.add_argument("modo", choices=["run", "digest", "preview"], help=(
        "run: bot contínuo com comandos; digest: uma rodada de envio; "
        "preview: mostra no terminal o que seria enviado"))
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    _carregar_env()
    cfg = Config.do_ambiente()

    if args.modo == "preview":
        return digest(cfg, simular=True)
    if not cfg.token:
        print("Defina TELEGRAM_BOT_TOKEN (veja o README).", file=sys.stderr)
        return 2
    if args.modo == "digest":
        digest(cfg)
    else:
        executar(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
