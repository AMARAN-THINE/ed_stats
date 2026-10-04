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

## Login request builder (decompiled, `FUN_1409ab190` @ `0x1409ab190`, `2.0/elite/user/login`)

Decompiled and checked against the string evidence in the sections above. The function builds the login POST body by
pulling values out of a config/game-state object (via a vtable call taking a string key) and concatenating them into
the `&key=value` form already documented: confirmed keys read this way include `GameSeason` and `CqcArena`, matching
the `&season=` / `&cqcarena=` fields listed earlier. The same request-string literal (`2.0/elite/user/login`) is
stored with the same ref-counted string header pattern as every other endpoint documented in `endpoint-functions.tsv`.
The sibling function `FUN_1409b0d70` (`2.0/edserver/login`, 4,144 addresses — the per-game-server login, larger
because it also negotiates connection/session parameters) and `FUN_1409adcf0` (`2.0/server/time`, time sync) were
decompiled in the same pass; `FUN_1409adcf0`'s logic was already summarized in `function-map.md`.

This confirms the account-login and game-server-login requests are two distinct calls (matching the two hostnames
documented above), not one combined flow, and that per-request fields are pulled from a generic key/value config
store rather than being hard-coded per field.

`FUN_1409b0d70` (`2.0/edserver/login`) is confirmed to be a request-object **constructor** (allocates the object,
sets its vtable pointers, stores the path string) — the same shape as the journal/event upload constructors in
`function-map.md`, not additional login logic. The actual field-population logic for this request wasn't reached in
this pass (it happens after construction, in whatever code calls this constructor and then fills the object).

## Verification: per-endpoint vs. shared dispatcher functions

Across all 351 resolved endpoint→function mappings in `endpoint-functions.tsv`, there are **320 distinct constructor
functions**. **265 of those are used by exactly one endpoint** (a dedicated request class per REST path, as described
above), while the remaining ~31 functions are shared dispatchers serving multiple related endpoints (the
vehicle/vessel/fighter embark-dock-launch-switch example in `function-map.md` is the largest such case). This
confirms quantitatively — not just from one example — that the dominant pattern is one small class per endpoint, with
shared dispatchers being the exception for closely related state-machine actions.

## Colonisation dispatcher cluster

`FUN_1411824e0` (3,361 addresses) is a second major shared dispatcher, backing 7 colonisation endpoints:
`claim/cancel`, `claim/candidate_filters`, `claim/claimsystem`, `constructioneffort/contribute`,
`constructioneffort/planetary/create`, `constructioneffort/space/create`, `launchcolonisationbeacon`, and
`rename/renamemarket` — i.e. the colonisation claim/construction/beacon/rename actions are one state-machine-style
handler, the same pattern as the vehicle dispatcher in `function-map.md`. `FUN_141183210` (1,885 addresses) is a
second, smaller colonisation dispatcher covering `claim/deny_starsystems`, `management/architect/colonised_systems`,
and the `resources/marketlink/weighting` / `resources/optionsfulllist` read endpoints.

### Correction: colonisation dispatcher is one constructor, not a runtime action switch

Decompiling `FUN_1411824e0` shows only **3** vtable (`*param_1 = &PTR_FUN_...`) reassignments in its body — the
signature of chained MSVC multiple-inheritance base-class constructors, not a function that builds 7 separate request
objects or branches over 7 string literals. This means the earlier framing above ("one state-machine-style handler")
is **not verified** by the decompiled code and is corrected here: this is most likely a single shared request/action
*class* whose specific endpoint path is supplied by a parameter or table at the call site, not embedded as 7 literal
strings inside this function. Which caller supplies which path for which of the 7 endpoints was not traced in this
pass. The vehicle/vessel dispatcher (`FUN_1424e4fe0`) in `function-map.md` was not re-verified against this same
check and should be treated with the same caution until confirmed.

## `elite/shipyard/modules/store` (largest single-endpoint handler)

`FUN_141f10980` (8,887 addresses, 63 distinct called functions) was decompiled but yields no named-field string
literals beyond boolean constants (`"true"`/`"false"`) — unlike the request builders documented elsewhere, this
handler appears to use internal type-hash constants for field access (the same pattern seen in the `ScanOrganic`
constructor in `codex-journal.md`) rather than string-keyed fields. Its size is consistent with it handling the full
module-storage transaction (validation, inventory update, pricing) rather than just building a request. Not resolved
further in this pass — a hash-table cross-reference against the type-hash constants used elsewhere would be needed to
recover field semantics.
