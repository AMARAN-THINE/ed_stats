# Function map (Ghidra 11.3.2, image base 0x140000000)

Addresses are virtual addresses in the loaded image. Names are **my labels**, inferred from string xrefs and the shape of the
decompiled code; the binary has no symbols for these. Decompiled bodies are not committed; regenerate them with
`tools/Xrefs.py`.

| Address | Label | Evidence |
|---|---|---|
| `0x140821410` | `JournalUploadRequest::ctor` | refs `"2.0/elite/journal"`; sets up a request object, passes the path to base ctor `FUN_14099f3f0(this+0x1e, 3, path)` |
| `0x14099ed40` | `EventUploadRequest::ctor` | refs `"2.0/elite/event"`; same request-object shape (telemetry event upload) |
| `0x14099f3f0` | `WebRequest::ctor(path)` (base) | called with path strings by the request constructors; second argument looks like an HTTP method/kind (3 for journal) |
| `0x1409adcf0` | `TimeService::sync` | refs `"2.0/server/time"`; issues the request via vtable slot +0x28 of the web service and processes `unixTimestamp` |
| `0x1409ab190` | `UserLogin::...` | refs `"2.0/elite/user/login"` (524 decompiled lines) |
| `0x1409b0d70` | `GameServerLogin::...` | refs `"2.0/edserver/login"` (842 lines) |
| `0x1409a90b0` | `Shell command: ServerToken` | refs the ServerToken usage string |
| `0x140a00200` | `Shell command: Help` | refs `"Display help on the available commands"` |
| `0x142e874a0` | `StatusJson reader` | refs `"Status.json"`; parses JSON with keys `flags`, `event`, `timestamp` (reads at most 0x1fe bytes) |
| `0x142e88380` | `ShipLocker.json handler` | refs `"ShipLocker.json"` |
| `0x141abb8a0` | `Backpack.json handler` | refs `"Backpack.json"` |
| `0x141d619a0` | `Cargo.json handler` | refs `"Cargo.json"` |
| `0x141fa6080` | `Market.json handler` | refs `"Market.json"` |
| `0x1425e78b0`, `0x142642920` | `NavRoute.json handlers` | refs `"NavRoute.json"` |

## Observations
- **Request objects.** Every REST endpoint appears to be a small class whose constructor stores a path string
  (ref-counted string: length at `+0x00`/`+0x08`, characters from `+0x14`) and chains into a common base. This pattern
  (constructor + vtable pointers like `PTR_FUN_14511a6c8` for the base, then a derived vtable) lets you enumerate all
  ~400 endpoints: xref each string in `server-endpoints.txt` and take the containing constructor.
- **JSON handling.** Status.json is parsed with a small in-house JSON reader (`FUN_144c0e4a0` parse, `FUN_144c0db70` has-key,
  `FUN_144c0db00` get-key), not a third-party DLL. It rejects files that lack `flags`, `event` or `timestamp`.
- **Stack protector.** Functions use the MSVC `/GS` cookie (`DAT_145ea6968 ^ stack`).
- **Strings are interned/ref-counted** with a 0x14-byte header, so Ghidra's string table often shows them only as
  `s_<text>_<addr>` data labels rather than inline literals.

## Tooling caveat
`tools/Xrefs.py` stopped after the first non-ASCII string (`UnicodeEncodeError` in Jython 2); it processed the targets above
before failing. If you extend it, wrap `str(d.getValue())` in `unicode(...)` handling.

## Correction/confirmation: vehicle dispatcher verified by decompilation

Following the same check applied to the colonisation dispatcher (which turned out to be a misattribution, see
`network.md`), `FUN_1424e4fe0` was decompiled and checked. Unlike the colonisation case, **this one is confirmed**:
it's a genuine runtime `switch` statement on an internal action code at `param_1+0x270`, cases `0`–`10`, with explicit
per-case endpoint construction visible in the decompiled code:

| Case | Endpoint |
|---|---|
| 1 | `2.0/elite/vehicle/launch` (and, further down the same case, `2.0/elite/multicrew/launchable/launch`) |
| 2 | `2.0/elite/vehicle/dock` (and `2.0/elite/multicrew/launchable/dock`) |
| 3 | `2.0/elite/fighter/switch` |
| 4 | `2.0/elite/vehicle/switch` |
| 6 | `2.0/elite/vessel/embark` |
| 0, 5, 8, 9, 10 | no endpoint-string construction found — likely local-only state transitions, not REST actions |
| 7 | confirmed local: vehicle transform/position setup (coordinate data, no REST call) |

This is a genuine single-function state machine handling vehicle/fighter/multicrew-launchable launch, dock, switch
and embark actions by internal action-code, exactly as originally described — the earlier correction applied to the
*colonisation* function only, not this one.
