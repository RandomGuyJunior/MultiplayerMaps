#!/usr/bin/env python3
"""Validate repository-hosted and remote map declarations."""
import json
from pathlib import Path
from urllib.parse import urlsplit

root = Path(__file__).resolve().parents[1]
entries = json.loads((root / "maps.json").read_text(encoding="utf-8"))
assert isinstance(entries, list), "maps.json must be an array"
seen_names, seen_files = set(), set()
for entry in entries:
    for field in ("name", "file", "attribution"):
        assert isinstance(entry.get(field), str) and entry[field].strip(), f"missing {field}"
    name = entry["file"]
    assert name == Path(name).name and name.lower().endswith((".sd7", ".sdz")), f"invalid archive: {name}"
    assert entry["name"] not in seen_names and name not in seen_files, "duplicate name or filename"
    seen_names.add(entry["name"])
    seen_files.add(name)
    kind = entry.get("source_type")
    assert kind in ("local", "remote"), f"invalid source_type for {name}"
    if kind == "local":
        expected = f"maps/{name}"
        assert entry.get("source_path") == expected, f"local path must be {expected}"
        archive = root / expected
        assert archive.is_file() and archive.stat().st_size > 0, f"missing/empty local map: {expected}"
    else:
        url = entry.get("download_url", "")
        parsed = urlsplit(url)
        assert parsed.scheme == "https" and parsed.hostname, f"invalid remote download URL for {name}"
    if "sha256" in entry:
        assert len(entry["sha256"]) == 64 and all(c in "0123456789abcdefABCDEF" for c in entry["sha256"]), "invalid sha256"
print(f"Validated {len(entries)} map(s): {sum(e['source_type']=='local' for e in entries)} local, {sum(e['source_type']=='remote' for e in entries)} remote")
