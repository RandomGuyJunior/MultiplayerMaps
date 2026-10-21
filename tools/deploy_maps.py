#!/usr/bin/env python3
"""Deploy local and remote map archives without deleting unrelated maps."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MAP_DIR = Path("/srv/moddedbar-maps/maps")
CATALOG = Path("/srv/moddedbar-maps/service/maps.json")
INDEX_SERVICE = "moddedbar-map-indexer.service"
LOCK_FILE = "/tmp/moddedbar-map-deploy.lock"

def digest(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def acquire(entry, manifest_dir, destination):
    if entry["source_type"] == "local":
        name = entry["file"]
        relative = entry.get("source_path")
        if relative != f"maps/{name}":
            raise ValueError(f"Invalid local map path: {relative}")
        source = manifest_dir / relative
        if not source.is_file():
            raise FileNotFoundError(f"Missing uploaded map: {source}")
        with source.open("rb") as src, destination.open("wb") as dst:
            shutil.copyfileobj(src, dst)
    elif entry["source_type"] == "remote":
        url = entry["download_url"]
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Remote map URL must be HTTPS")
        request = Request(url, headers={"User-Agent": "ModdedBAR-MapDeploy/1.0"})
        with urlopen(request, timeout=120) as src, destination.open("wb") as dst:
            shutil.copyfileobj(src, dst)
    else:
        raise ValueError(f"Unknown source_type: {entry.get('source_type')}")

def deploy(manifest):
    manifest_dir = Path(manifest).resolve().parent
    entries = json.loads(Path(manifest).read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("maps.json must be an array")
    MAP_DIR.mkdir(parents=True, exist_ok=True)
    filenames = set()
    for entry in entries:
        name = entry["file"]
        if name != Path(name).name or not name.lower().endswith((".sd7", ".sdz")) or name in filenames:
            raise ValueError(f"Invalid or duplicate map archive: {name}")
        filenames.add(name)
        target = MAP_DIR / name
        fd, temporary = tempfile.mkstemp(prefix="moddedbar-incoming-", suffix=".download")
        temp = Path(temporary)
        try:
            os.close(fd)
            acquire(entry, manifest_dir, temp)
            if temp.stat().st_size == 0:
                raise ValueError(f"Empty map: {name}")
            checksum = digest(temp)
            if entry.get("sha256") and checksum.lower() != entry["sha256"].lower():
                raise ValueError(f"SHA256 mismatch: {name}")
            if target.exists() and digest(target) == checksum:
                print(f"Unchanged: {name}", flush=True)
                continue
            staging = MAP_DIR / (".staging-" + name + ".tmp")
            try:
                with temp.open("rb") as src, staging.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                    dst.flush()
                    os.fsync(dst.fileno())
                os.chmod(staging, 0o644)
                os.replace(staging, target)
            finally:
                staging.unlink(missing_ok=True)
            print(f"Installed: {name}", flush=True)
        finally:
            temp.unlink(missing_ok=True)
    if not entries:
        print("No declared maps", flush=True)
        return
    trigger = subprocess.run(["systemctl", "start", INDEX_SERVICE], capture_output=True, text=True)
    if trigger.returncode:
        print("Indexer start not permitted; checking catalog: " + (trigger.stderr.strip() or trigger.stdout.strip()), flush=True)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
            indexed = {r.get("download", {}).get("filename"): r for r in catalog}
            if all(name in indexed and indexed[name].get("download", {}).get("md5") == digest(MAP_DIR / name, "md5") for name in filenames):
                print("Indexed: " + ", ".join(sorted(filenames)), flush=True)
                return
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(2)
    raise RuntimeError("Map catalog missing or stale after 180 seconds; check moddedbar-map-indexer.service")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    args = parser.parse_args()
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        deploy(args.manifest)
