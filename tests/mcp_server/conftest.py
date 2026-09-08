import sys
from pathlib import Path

MCP_SERVER_SRC = Path(__file__).resolve().parents[2] / "mcp_server"
if str(MCP_SERVER_SRC) not in sys.path:
    sys.path.insert(0, str(MCP_SERVER_SRC))
