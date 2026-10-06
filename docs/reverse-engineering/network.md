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

### Second colonisation function confirms the multi-constructor pattern, not dispatch

`FUN_141183210` (the second colonisation "dispatcher" noted above, covering `claim/deny_starsystems`,
`management/architect/colonised_systems`, `resources/marketlink/weighting`, `resources/optionsfulllist`) was
decompiled and checked the same way. It resets `*param_1` to a **new top-level vtable twice** (two separate
`*param_1 = &PTR_FUN_...` assignments, each starting a fresh object layout, not a chained-constructor sequence) —
confirming this is a function that builds multiple distinct request-object types one after another, the same
non-dispatcher pattern already found for `FUN_1411824e0`. This generalizes the earlier correction: both large
"shared" colonisation functions are multi-object-construction code, not runtime action switches, unlike the vehicle
dispatcher (`FUN_1424e4fe0`), which is a genuine verified `switch`.

### Powerplay function confirms multi-constructor pattern generalizes further

`FUN_1425355b0` (3,611 addresses, backing `powerplay2/microresource/deliver`, `powerplay2/microresource/collect`,
`powerplay2/commander/package/claim`) was checked the same way: no `switch` statement found, and two separate
top-level vtable resets (not a chained-constructor sequence) — the same multi-object-construction pattern already
confirmed for both colonisation "dispatcher" functions. This is now observed across colonisation and Powerplay
endpoint clusters, suggesting the "one function, many endpoint strings" shape generally means multi-constructor code,
not a runtime dispatcher, with the vehicle dispatcher (`FUN_1424e4fe0`, a genuine `switch`) being the exception
rather than the rule.

### Third pattern found: single object with a homogeneous sub-element array

`FUN_141350ae0` (2,014 addresses, backing 5 `elite/survey/trade/*` endpoints) is neither a `switch` dispatcher nor a
multi-constructor function. It sets its top-level vtable **once**, then writes the **same** vtable pointer
(`PTR_FUN_1451a1560`) six times at a regular stride (0x1f dwords apart: offsets 0x41, 0x60, 0x7f, 0x9e, 0xbd, 0xdc) —
i.e. one object containing a fixed-size array of 6 identical-type sub-elements, most likely one slot per
buy/sell/multisell/list-buy/list-sell survey-trade action. This is a third distinct code shape for "one function,
several endpoint strings," alongside the verified `switch` (vehicle dispatcher) and the multi-constructor pattern
(colonisation/Powerplay). The lesson generalized across all three checks: this binary's "shared handler" functions
need to be decompiled individually to know which shape they are — the endpoint-count alone doesn't predict it.

### Crafting endpoint function also confirmed multi-constructor

`FUN_14122e2c0` (`crafting/specials`, `crafting/engineer/pin`) shows two separate top-level vtable resets after the
shared base constructor — the same multi-constructor pattern as colonisation and Powerplay, not a `switch`. This is
now confirmed across colonisation, Powerplay, and crafting endpoint clusters.

### Fourth pattern: single-object constructor serving multiple endpoints via runtime parameter

`FUN_14477bd70` (2,330 addresses, backing `npccrew/assign`, `npccrew/fire`, `npccrew/market/hire`,
`npccrew/market/list`) shows only **one** top-level vtable reset — neither the multi-constructor pattern
(colonisation/Powerplay/crafting) nor a `switch` (vehicle dispatcher) nor the homogeneous-array pattern
(survey/trade). This is a single object type whose specific action is presumably selected by a parameter passed in
at the call site (not encoded in this constructor itself) — a fourth distinct shape for "one function, several
endpoint strings" found this session, reinforcing that each shared handler needs individual verification rather
than assuming a shape from endpoint count alone.

`FUN_141e84800` (6,221 addresses, `initiative/optin`/`initiative/redeem`) also shows a single top-level vtable
reset — same single-constructor-with-parameter-selected-action shape as the npccrew handler above.

`FUN_141c09bd0` (`elite/starsystem`, 222 addresses) shows the same hashed-field pattern (no string-literal field
names), consistent with the system-wide pattern already confirmed elsewhere.

`FUN_14260d130` (`elite/starsystem`, 1,404 addresses) references `"WingNavLock"` — likely tied to the wing
nav-lock/follow-target feature (sharing a target system with wing members), otherwise uses the hashed-field pattern.

`FUN_141e89ac0` (`elite/resources/finance`, 4,755 addresses) references `"ShipShop2"` — likely an internal
UI/economy category tag for the shipyard purchase flow, otherwise hashed-field pattern.

`FUN_1421d9180` (1,870 addresses, `cqc/lobby`, `cqc/matchmaking/cancel`/`enter`/`status`) is single-constructor
pattern, consistent with npccrew/initiative handlers documented above.

`FUN_142da8ff0` (`elite/npc/kill`, 4,022 addresses) shows hashed-field pattern, no literal field names.

`FUN_1420b1c30` (`elite/mission/cargodepot/collect`, 1,050 addresses) shows hashed-field pattern, consistent with
other cargo/mission handlers.

`FUN_1412e5130` (`elite/service/limpets`, 593 addresses) shows hashed-field pattern, no literal field names.
