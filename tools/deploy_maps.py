#!/usr/bin/env python3
"""Add/update hosted .sd7 maps from the repository manifest without deleting existing maps."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import tempfile
from urllib.request import Request, urlopen
from urllib.parse import urlparse

MAP_DIR = Path("/srv/moddedbar-maps/maps")
CATALOG = Path("/srv/moddedbar-maps/service/maps.json")
INDEX_SERVICE = "moddedbar-map-indexer.service"
LOCK_FILE = "/tmp/moddedbar-map-deploy.lock"

def read_url(url, output):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Map download URL must use HTTPS")
    req = Request(url, headers={"User-Agent": "ModdedBAR-MapDeploy/1.0"})
    with urlopen(req, timeout=120) as response:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def deploy(manifest):
    entries = json.loads(Path(manifest).read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("maps.json must be a JSON array")
    MAP_DIR.mkdir(parents=True, exist_ok=True)
    changed = []
    for entry in entries:
        name = entry["file"]
        if Path(name).name != name or not name.lower().endswith(".sd7"):
            raise ValueError(f"Invalid or unsupported archive name: {name}")
        url = entry["download_url"]
        target = MAP_DIR / name
        fd, temp_name = tempfile.mkstemp(prefix="moddedbar-incoming-", suffix=".download")
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as out:
                read_url(url, out)
                out.flush()
                os.fsync(out.fileno())
            if temp.stat().st_size == 0:
                raise ValueError(f"Empty download: {name}")
            if entry.get("sha256") and digest(temp).lower() != entry["sha256"].lower():
                raise ValueError(f"SHA256 mismatch: {name}")
            if target.exists() and digest(target) == digest(temp):
                print(f"Unchanged: {name}", flush=True)
                continue
            os.chmod(temp, 0o644)
            # Copy to a staging filename without .sd7 inside the watched\n            # directory, then atomically publish the completed archive.\n            staging = MAP_DIR / (".staging-" + name + ".tmp")\n            try:\n                with temp.open("rb") as source, staging.open("wb") as dest:\n                    import shutil\n                    shutil.copyfileobj(source, dest)\n                    dest.flush()\n                    os.fsync(dest.fileno())\n                os.chmod(staging, 0o644)\n                os.replace(staging, target)\n            finally:\n                staging.unlink(missing_ok=True)
            changed.append(name)
            print(f"Installed: {name}", flush=True)
        finally:
            temp.unlink(missing_ok=True)
    if entries:
        # PathChanged may not fire for an atomic rename, so explicitly trigger
        # the existing index service as well as retaining the path watcher.
        # This does not restart the map API or other infrastructure.
        trigger = subprocess.run(
            ["systemctl", "start", INDEX_SERVICE], capture_output=True, text=True
        )
        if trigger.returncode:
            print(
                "Indexer trigger failed (checking catalog anyway): " +
                (trigger.stderr.strip() or trigger.stdout.strip()),
                flush=True,
            )
        # Always verify every declared archive, including unchanged ones.
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
                indexed = {r.get("download", {}).get("filename"): r for r in catalog}
                if all(n in indexed and indexed[n].get("download", {}).get("md5") == hashlib.md5((MAP_DIR / n).read_bytes()).hexdigest() for n in (entry["file"] for entry in entries)):
                    print("Indexed: " + ", ".join(entry["file"] for entry in entries), flush=True)
                    break
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            time.sleep(2)
        else:
            status = subprocess.run(
                ["systemctl", "status", INDEX_SERVICE, "--no-pager", "-l"],
                capture_output=True, text=True,
            )
            print("Indexer service diagnostics:\\n" + status.stdout[-4000:], flush=True)
            journal = subprocess.run(
                ["journalctl", "-u", INDEX_SERVICE, "-n", "35", "--no-pager"],
                capture_output=True, text=True,
            )
            print("Indexer recent logs:\\n" + journal.stdout[-6000:], flush=True)
            raise RuntimeError("Declared maps are missing or stale in the index after 180 seconds")
    else:
        print("No map archive changes", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    args = parser.parse_args()
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        deploy(args.manifest)
