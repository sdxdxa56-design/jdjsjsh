import os
import sys
import time
import socket
import subprocess
from pathlib import Path
from datetime import datetime


INTERVAL_HOURS = int(os.environ.get("ZEROHUNTER_TRAIN_INTERVAL_HOURS", "24"))


def internet_available(host: str = "1.1.1.1", port: int = 53, timeout: int = 3) -> bool:
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except OSError:
        return False


def run_cycle() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    online = internet_available()
    print(f"[{now}] Starting ZeroHunter self-training cycle (online={online})...")

    env = os.environ.copy()
    if online:
        try:
            from core.knowledge import build_curated_dataset
            build_curated_dataset()
        except Exception as exc:
            print("Online advisory refresh skipped:", exc)
        env["ZEROHUNTER_OFFLINE"] = "0"
    else:
        # Full offline mode: train purely from locally cached base weights, auto_curated.jsonl, and self_play_train.jsonl
        env["ZEROHUNTER_OFFLINE"] = "1"
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"

    if not Path("datasets/auto_curated.jsonl").exists() and not Path("datasets/self_play_train.jsonl").exists():
        print("No local datasets yet; core built-in conversations will still be refreshed.")

    subprocess.run([sys.executable, "train.py"], env=env, check=False)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Cycle finished.")


if __name__ == "__main__":
    if "--daemon" in sys.argv:
        while True:
            run_cycle()
            time.sleep(INTERVAL_HOURS * 3600)
    else:
        run_cycle()
