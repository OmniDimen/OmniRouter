import os
import socket
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("OMNIROUTER_DB_PATH", str(BASE_DIR / "omnirouter.db"))
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

HOST = os.getenv("OMNIROUTER_HOST", "0.0.0.0")
PORT = int(os.getenv("OMNIROUTER_PORT", "9090"))


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


LOCAL_IP = get_local_ip()
