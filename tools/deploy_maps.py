#!/usr/bin/env python3
"""Add/update hosted .sd7 maps from the repository manifest without deleting existing maps."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
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
        fd, temp_name = tempfile.mkstemp(prefix=".incoming-", suffix=".sd7", dir=MAP_DIR)
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
            os.replace(temp, target)
            changed.append(name)
            print(f"Installed: {name}", flush=True)
        finally:
            temp.unlink(missing_ok=True)
    if changed:
        # The existing systemd path unit automatically starts the indexer.
        # Wait for it to complete; don't write the generated catalog ourselves.
        import time
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
                indexed = {r.get("download", {}).get("filename"): r for r in catalog}
                if all(n in indexed and indexed[n].get("download", {}).get("md5") == hashlib.md5((MAP_DIR / n).read_bytes()).hexdigest() for n in changed):
                    print("Indexed: " + ", ".join(changed), flush=True)
                    break
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            time.sleep(2)
        else:
            raise RuntimeError("Map archives deployed, but indexer did not update the catalog within 180 seconds")
    else:
        print("No map archive changes", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    args = parser.parse_args()
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        deploy(args.manifest)
