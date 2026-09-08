import sys
from pathlib import Path

DAEMON_SRC = Path(__file__).resolve().parents[2] / "daemon"
if str(DAEMON_SRC) not in sys.path:
    sys.path.insert(0, str(DAEMON_SRC))
