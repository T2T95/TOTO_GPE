import sys
from pathlib import Path

# Ajoute <repo>/back/src au PYTHONPATH pour pouvoir lancer depuis back/
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
	sys.path.insert(0, str(SRC_DIR))

from src.elhomeshield.cli import run_cli


def main() -> int:
	return run_cli()


if __name__ == "__main__":
	sys.exit(main())

