"""Enqueue a dashboard publish and wake the single central worker."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
QUEUE = ROOT / ".publish_queue"
WORKER = ROOT / "publisher_worker.py"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def enqueue(source="unknown"):
    QUEUE.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    marker = QUEUE / ("%s_%s_%s.json" % (stamp, os.getpid(), source))
    tmp = marker.with_suffix(".tmp")
    tmp.write_text(json.dumps({"source": source, "created": time.time()}, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, marker)
    subprocess.Popen(
        [sys.executable, str(WORKER)], cwd=str(ROOT), stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=NO_WINDOW | DETACHED,
    )
    print("[publish] 已入中央队列: %s" % source)


if __name__ == "__main__":
    enqueue(sys.argv[1] if len(sys.argv) > 1 else "unknown")
