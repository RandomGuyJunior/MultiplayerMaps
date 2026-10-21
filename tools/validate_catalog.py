import json
import pathlib
import urllib.parse

root = pathlib.Path(__file__).resolve().parents[1]
entries = json.loads((root/'maps.json').read_text(encoding='utf-8'))
assert isinstance(entries, list), 'maps.json must be an array'
seen = set()
for m in entries:
    for k in ('name', 'file', 'source', 'download_url', 'minimap_url', 'attribution'):
        assert isinstance(m.get(k), str) and m[k].strip(), f'missing {k}'
    assert m['file'].endswith(('.sd7','.sdz')), 'Map archive must be sd7 or sdz'
    assert '/' not in m['file'] and '\\' not in m['file'], 'Unsafe filename'
    assert m['name'] not in seen, 'duplicate name'
    seen.add(m['name'])
    for key in ('source','download_url','minimap_url'):
        p=urllib.parse.urlsplit(m[key]); assert p.scheme=='https' and p.hostname, f'Invalid HTTPS URL in {key}'
print(f'Validated {len(entries)} map(s)')
