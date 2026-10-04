# Network / client–server protocol notes (from strings)

Source: static strings in `EliteDangerous64.exe` (see README.md for hash). No traffic was captured and the binary was not run, so request/response bodies, auth flow ordering and field semantics are **inferred from format strings only**.

## Transport
- HTTP(S) via libcurl + OpenSSL; requests are `application/x-www-form-urlencoded` (also `application/xml` is accepted).
- Request bodies are built from `&key=value` format strings, e.g. `fTime=`, `&machineId=`, `&machineToken=`, `&authToken=`,
  `&build=`, `&protocol=`, `&connectionDetails=`, `&language=`, `&buildId=`, `&season=`, `&terrain=`, `&cqcarena=`, `&connCap=`.
- Custom headers: `Fdev-Semver`, `Fdev-Season`, `Fdev-Request-Id`, `Fdev-Invocation-Id`, `Fdev-Server-Id`, `Fdev-Retry`,
  `Fdev-Assert`, `Request-Time`, `Request-Tag`, `X-Frontier-EpicAuth`.
- Time sync against `2.0/server/time` (JSON field `unixTimestamp`); failures produce `type=badtimesync` / `type=notimesync`.
- Login result categories seen: `type=nologin&statuscode=%u`, `type=notoken`, `type=loginfailure`, `type=logout`.
- Server also hands back TURN credentials (`turnUser`, `turnPassword`) used for peer-to-peer relay; UPnP (MiniUPnPc)
  is used for NAT port mapping.
- Server IDs that appear as name prefixes: `privatetest-`, `xbox-3400-`, `ps4-pts-`, `ps4-3400-`, `asp-test-`, `boa-test-`, `cobra-test-`.
- Account endpoints: `2.0/elite/user/login`, `.../logout`, `.../linkaccount`, `.../activateaccount`; game-server login
  `2.0/edserver/login`; telemetry/event upload `2.0/elite/event` (cached locally in `TelemetryCache.log`, format `EventCache:v2`).
- A string-moderation dictionary is fetched from `2.0/elite/resources/dictionary` (blacklist/whitelist, leetspeak regexes).
- Store login: EOS (Epic) token acquisition/refresh with `[EOS SDK]` log lines; Steam detection through the registry.

## Hard-coded credentials
The binary contains a block of hard-coded Epic Online Services identifiers (a client id/secret pair, product/sandbox/
deployment ids, and a 32-digit numeric constant) near the login strings (string-table offsets around 91,6xx in a
`strings` listing). **Values are deliberately not copied here.** These are client-embedded values, not user secrets, but
should be treated as the vendor's and not republished.

## Endpoint catalogue
`server-endpoints.txt` lists the 405 distinct `2.0/...` paths (query strings stripped). By top-level group:
squadron 55, commander 44, fleetcarrier 30, colonisation 24, user 20, powerplay 20, shipyard 17, multicrew 17, vendors 16,
operations 12, survey 11, resources 10, crafting 9, starsystem 8, wing 6, initiative 6, ship 5, organic 5, crime 5,
cargo 5, then a long tail (npccrew, cqc, comms, codex, mission, mining, market, journal, news, etc.).
Noteworthy: `elite/colonisation/*` (system claim, construction effort, architect/market management),
`elite/fleetcarrier/*`, `elite/powerplay/*`, `elite/codex/*`, `elite/journal` (journal upload).

## Other services mentioned
Frontier store (password reset URL), EULA hosting URL for the Xbox build, an IRC host used for text chat, plus the
dev/internal API hostnames listed in README.md.

## Endpoint → function mapping

`endpoint-functions.tsv` maps 351 of the 405 known `2.0/...` paths to the Ghidra function whose code references that
path string (format: `endpoint<TAB>address<TAB>function-name<TAB>function-size-in-addresses`). Generated with
`tools/EndpointMap.py`. The remaining ~54 paths are built from runtime-concatenated pieces (e.g. a shared
prefix plus a per-item suffix) rather than a single literal, so they don't resolve to one containing function this way.

Several endpoints share one function, which is a single dispatcher taking a route/verb argument rather than one function
per REST path, e.g. `FUN_1424e4fe0` (7,504 addresses) backs `elite/vessel/embark`, `elite/vehicle/switch`,
`elite/vehicle/launch`, `elite/vehicle/dock`, `elite/multicrew/launchable/launch`, `elite/multicrew/launchable/dock`,
and `elite/fighter/switch` — i.e. the game's vehicle/vessel/fighter embark-dock-launch-switch flows are one state
machine. Largest single-endpoint handler found: `elite/shipyard/modules/store` at `FUN_141f10980` (8,887 addresses).
