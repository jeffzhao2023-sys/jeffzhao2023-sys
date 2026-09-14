"""Process dashboard publish markers with one cross-process worker."""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
QUEUE = ROOT / ".publish_queue"
LOCK = ROOT / ".publish_worker.lock"
LOG = ROOT / "publisher.log"
DATA_FILES = ("dashboard.html", "alpha_funds_data.js", "highest_data.js", "dildj_data.js", "lianban_data.js")
MAX_PUSH_TRIES = 5


def log(message):
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), message))


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


def acquire_lock():
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        return fd
    except FileExistsError:
        try:
            if time.time() - LOCK.stat().st_mtime > 600:
                LOCK.unlink()
                return acquire_lock()
        except OSError:
            pass
        return None


def push():
    for attempt in range(1, MAX_PUSH_TRIES + 1):
        result = git("push", "origin", "main")
        if result.returncode == 0:
            return True
        log("push failed %d/%d: %s" % (attempt, MAX_PUSH_TRIES, (result.stderr or result.stdout).strip()[-500:]))
        if attempt < MAX_PUSH_TRIES:
            time.sleep(min(30, attempt * 5))
    return False


def main():
    QUEUE.mkdir(exist_ok=True)
    fd = acquire_lock()
    if fd is None:
        return 0
    try:
        while True:
            markers = sorted(QUEUE.glob("*.json"))
            if not markers:
                return 0
            if not git("config", "user.name").stdout.strip():
                git("config", "user.name", "dashboard-publisher")
                git("config", "user.email", "dashboard@localhost")
            added = git("add", "--", *DATA_FILES)
            if added.returncode:
                log("git add failed: %s" % added.stderr.strip())
                return added.returncode
            status = git("status", "--porcelain", "--", *DATA_FILES)
            if status.stdout.strip():
                commit = git("commit", "-m", "auto update dashboard")
                if commit.returncode:
                    log("git commit failed: %s" % (commit.stderr or commit.stdout).strip()[-500:])
                    return commit.returncode
            if not push():
                return 1
            for marker in markers:
                marker.unlink(missing_ok=True)
            log("published %d queue item(s)" % len(markers))
    finally:
        os.close(fd)
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
