# MultiplayerMaps

Map archive registry and automated deployment for RandomGuyJunior's independent Modded BAR server.

Maps are served from `https://moddedbar.duckdns.org/maps.json`. The server indexes installed map archives and exposes Spring-name lookup at `/find?category=map&springname=...`. The **internal Spring map name** may differ from the archive filename or registry display name.

## Add a map: two supported sources

### Option A: Put your map directly in this repository

Best for maps you own, including **Bathtub Brawl V2**.

1. Copy the finished `.sd7` or `.sdz` archive into `maps/` and commit it. Archives in `maps/` are not ignored.
2. Add an entry to `maps.json`:

```json
{
  "name": "Bathtub Brawl V2",
  "file": "Bathtub_Brawl_V2.sd7",
  "source_type": "local",
  "source_path": "maps/Bathtub_Brawl_V2.sd7",
  "attribution": "RandomGuyJunior"
}
```

The path must be exactly `maps/<file>`. GitHub Actions transfers the actual archive to the VM and installs it into `/srv/moddedbar-maps/maps/`.

### Option B: Use an external HTTPS download URL

Best for maps hosted by other authors or in another map repository. No archive needs to be committed here.

Add an entry like:

```json
{
  "name": "Simmering Ravine 1.5",
  "file": "simmering_ravine_1.5.sd7",
  "source_type": "remote",
  "download_url": "https://raw.githubusercontent.com/danielkopko/BarMaps/main/simmering_ravine_1.5.sd7",
  "attribution": "danielkopko; based on All That Simmers by Nikuksis"
}
```

The URL must be a direct HTTPS link to the map archive, not a GitHub repository webpage. Optional metadata includes `source`, `minimap_url`, and `sha256` (a 64-character SHA-256 hex digest). A SHA-256 checksum is recommended for remote maps.

## Publish and verify

1. Run `python3 tools/validate_catalog.py` locally (or rely on the workflow validation).
2. Commit and push to `main`. Changes to `maps.json`, `maps/`, the validator, or the deployment workflow trigger **Deploy multiplayer maps** in GitHub Actions. Manual `workflow_dispatch` is also available.
3. The workflow uploads local archives and the manifest to the VM. The deploy script downloads remote archives, checks optional SHA-256 digests, publishes changed archives atomically, and verifies that each declared archive appears in the indexed catalog with the expected MD5.
4. Check `https://moddedbar.duckdns.org/maps.json` for the indexed map and query `/find?category=map&springname=ACTUAL_SPRING_NAME`.

The deployer does **not** delete existing server maps when they are removed from the manifest. Removing a manifest entry alone does not uninstall a map.

### Indexer note

The map indexer is a one-shot systemd service triggered by `moddedbar-map-indexer.path`. The deployment script attempts to start it explicitly, but the SSH deployment account may lack systemd permissions. If a map is installed but missing from the public catalog, run this on the VM:

```bash
sudo systemctl start moddedbar-map-indexer.service
sudo systemctl status moddedbar-map-indexer.service --no-pager
```

An inactive/dead state after a successful one-shot run is normal. An unchanged map can already be indexed without requiring another run.

## Repository layout

- `maps/`: actual repository-hosted map archives.
- `maps.json`: declarations for local and remote maps.
- `tools/validate_catalog.py`: validates both source types.
- `tools/deploy_maps.py`: deploys and checks the indexed catalog.
- `.github/workflows/deploy-maps.yml`: automated production deployment.

**Note:** Successful server-side discovery does not by itself prove that Chobby's multiplayer or skirmish map-selection UI lists remote maps; that integration must be tested separately.
