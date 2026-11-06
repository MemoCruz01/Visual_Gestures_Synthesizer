"""
Entry Point für Visual Gestures Synthesizer

Starten Sie die Anwendung mit:
    python main.py
"""

import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)

# Import UI
try:
    from .ui import run_ui
except ImportError:
    # Fallback wenn relative imports nicht funktionieren
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from ui import run_ui


def main() -> int:
    """Haupteinstiegspunkt"""
    logger.info("=" * 60)
    logger.info("Visual Gestures Synthesizer - Starting... ;) 😎")
    logger.info("=" * 60)

    try:
        exit_code = run_ui()
        logger.info("Application closed successfully")
        return exit_code
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    finally:
        logger.info("=" * 60)
        logger.info("Visual Gestures Synthesizer - Shutdown")
        logger.info("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
