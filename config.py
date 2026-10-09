import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")
def _parse_admin_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
CRYPTOBOT_TOKEN = (os.getenv("CRYPTOBOT_TOKEN") or "").strip()
XROCKET_TOKEN = (os.getenv("XROCKET_TOKEN") or "").strip()
CHANNEL_ID = (os.getenv("CHANNEL_ID") or "").strip()
ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
TARIFFS = {
    1: 3.0,
    7: 7.0,
    30: 24.0,
}