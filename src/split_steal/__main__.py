"""Permite ejecutar la CLI con `python -m split_steal`."""
from .cli import app

# La guarda es imprescindible para ejecutar en paralelo en Windows: cada proceso
# hijo vuelve a importar este módulo, y sin ella cada hijo relanzaría la CLI.
if __name__ == "__main__":
    app()
