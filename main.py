#!/usr/bin/env python3
"""
Punto de entrada principal.
Toda la logica de display esta en src/interfaces/cli.py
Para usar otra interfaz, importa desde src/interfaces/ en su lugar.
"""
import os
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"   # evita errores 401 de telemetria

from src.interfaces.cli import main

if __name__ == "__main__":
    main()