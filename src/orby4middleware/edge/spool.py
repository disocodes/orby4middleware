import json
from pathlib import Path
from datetime import datetime, timezone


class FileSpool:
    def __init__(self, directory: str):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)

    def enqueue(self, payload: dict) -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.root / f"{ts}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        return path

    def pending(self):
        return sorted(self.root.glob("*.json"))

    def ack(self, path: Path):
        path.unlink(missing_ok=True)
