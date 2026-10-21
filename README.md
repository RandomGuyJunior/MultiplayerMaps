# MultiplayerMaps

Custom multiplayer maps for RandomGuy's independent Modded BAR environment.

Maps are provided as existing `.sd7` archives or source packages. This repository holds a verified map registry and a validated publication workflow; it does **not** deploy to the production `/maps.json` or `/find` endpoints automatically.

The launcher's current custom-map endpoints are `https://moddedbar.duckdns.org/maps.json` and `https://moddedbar.duckdns.org/find`. Those services must be configured to expose the same archive identities as this registry before clients can fetch these maps automatically.

## First map

- Simmering Ravine 1.5 from [danielkopko/BarMaps](https://github.com/danielkopko/BarMaps), authored as a derivative of *All That Simmers* by Nikuksis. The upstream repo contains a 52.6 MB `simmering_ravine_1.5.sd7` and a minimap image. The map is **referenced**, not copied here; redistribution rights were not established.

## Changes

Edit `maps.json` to add or update an entry. The workflow validates the catalog and tests upstream URLs, but publishing to your custom map service requires a separate server-side deployment once its contract has been inspected.
