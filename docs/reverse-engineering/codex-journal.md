# Codex / biology scanning — binary-confirmed schema

Directly relevant to this repo, which scans journals for `CodexEntry` biology events. Found as literal strings in
`EliteDangerous64.exe` (see README.md for hash); not run or tested against the live client.

## `CodexEntry` field schema
A literal CSV header string gives the full field list for this journal event in one place:

```
CodexEntry,EntryID,Name,SubCategory,Category,Region,System,SystemAddress,Traits,IsNewEntry,NewTraitsDiscovered,VoucherAmount,NearestDestination,BodyID
```

This matches the fields `app.py` already reads (`Region_Localised`, `System`, `BodyID`, `Name_Localised`) plus several it
doesn't currently use: `EntryID`, `SubCategory`, `SystemAddress`, `Traits`, `IsNewEntry`, `NewTraitsDiscovered`,
`VoucherAmount`, `NearestDestination`. `Category`/`SubCategory`/`Region` are localisation keys of the form
`$Codex_Category_%s;` / `$Codex_SubCategory_%s;` / `$Codex_RegionName_%s;` — the `%s` is filled at runtime from a
data table, so the actual category/subcategory code strings (e.g. `Biology`) aren't present as literals and must be
taken from observed journal files or the published journal manual.

## Organic sampling flow (server calls)
`2.0/elite/organic/log`, `2.0/elite/organic/sample`, `2.0/elite/organic/analyse`, `2.0/elite/organic/trade/list`,
`2.0/elite/organic/trade/sell`, with request field `&organicId=`.

Server-side failure strings returned to the client (useful for interpreting error states during scanning):
- "Organic Request Failed: Commander has already sold data for this organic, or you haven't logged enough samples to analyse this."
- "Organic Request Failed: Could not find a responsive EDServer. Check output for more details."
- "Organic Request Failed: Field missing or was incorrect type. Please contact gameplay."
- "Organic Request Failed: Not Possible To Find Here, new Organic not possible to log, or logging already in progress or completed."
- "Organic Request Failed: Organic/star system not found."

## Scanner UI states (`$Codex_Scanner_*`)
`ReadyToScan`, `Scanning`, `Complete`, `NothingFound`, `Hint`, `NewTraitDiscovered:#entryName=%s`,
`AllTraitsDiscovered:#entryName=%s` — the client-side states a bio-scanner composition scan passes through, matching
the in-game Genus/Species/Variant scan sequence.

## Discoveries panel fields (`$Codex_Discoveries_*`)
`ConfirmedDate`, `ConfirmedLocation`, `ReportedBy`, `ReportedDate`, `ReportedLocation`, `Discovery_Location`,
`NameHidden`, `ObservedTraits`, `AllTraitsFound`, `AdditionalTraitsExist`, plus unit labels `UnitEarthMasses`,
`UnitEarthRadii`, `UnitSolMasses`, `UnitSolRadii`, `UnitKelvin`, `UnitG`, `UnitYears` — these are the body-detail
fields shown for a codex entry once discovered.

## Not resolved
The actual `Category`/`SubCategory` value strings (e.g. `Biology`, `Geology`) and the full `Codex_Ent_<id>` catalogue
are data-driven (likely in a server-delivered or packed resource table), not literal strings in this executable, so
they are not enumerable from this binary alone.

## Journal writer internals (decompiled)

Five functions implementing the journal file writer were located and decompiled:

| Function | Role |
|---|---|
| `FUN_140833e20` (`0x140833e20`) | Builds the `Fileheader` line: pulls language, an `Odyssey` bool (rendered as literal `"true"`/`"false"`, not `1`/`0`), game version and build strings, then formats the header JSON. |
| `FUN_140832640` (`0x140832640`) | Builds the `Continued` line on file rollover: formats the current time as `"%04d-%02d-%02dT%02d:%02d:%02dZ"`, increments a `Part` counter, writes `{ "timestamp":<ts>, "event":"Continued", "Part":<n> }\r\n`, then calls `FUN_140824c70` to actually start the next file. |
| `FUN_140834990` (`0x140834990`) | Not yet read in detail; referenced alongside the other two timestamp-building calls. |
| `FUN_14082b5f0` (`JournalLogging`, 866 addresses) | Not yet read in detail. |
| `FUN_14082d860` (`0x14082d860`, `JournalFileError`) | Error-recovery path: increments a retry counter at a fixed struct offset and **gives up after 50 attempts** (`if (++count > 0x31) return;`), otherwise builds a `"message"`-keyed string via the object's own vtable `+0x30` slot (likely a `what()`/error-description call) for reporting. |

Confirms (from real code, not just strings) that the journal file format is: a `Fileheader` event on open, one JSON
line per game event terminated `\r\n`, and a `Continued` event with an incrementing `Part` number when the writer
rolls over to a new file — matching the multi-part `Journal.<timestamp>.01.log`, `.02.log` naming behavior players
observe. File-write errors are retried up to 50 times before the writer stops attempting recovery.

### Journal subsystem service registration (`FUN_14082b5f0`)

This function is not per-line logging — it's a one-time startup registration of four named global service
singletons, each via an identical lazy-init pattern (tear down existing instance if present, allocate, register with
a shared component framework): **`JournalLogging`**, **`TransmitJournal`**, **`UploadJournal`**, and
**`DisconnectionHandlerService`**. This confirms the journal pipeline is architected as four separate services —
local file writing, transmission, upload, and disconnect handling are independent components, not one monolithic
writer — matching the separate `TransmitJournal`/`UploadJournal`/`FlushUploadJournalActivity` strings noted in
`README.md`.

### Generic array/object line builder (`FUN_140834990`)

A lower-level string-builder helper used while constructing a journal/event JSON line: appends a `"timestamp"` key
and formatted ISO-8601 value, then iterates an array passed in `param_3` (count at `param_3+0x10`, element stride
`0x38` bytes), formatting and appending each element via `FUN_1408339f0`, comma-joined. This is the generic
array-serialization helper the event-builders (Fileheader/Continued and presumably the full per-event writers) call
into — it is not event-specific and doesn't reveal which event uses it without further xref work.

## CodexEntry / ScanOrganic / SAAScanComplete — decompiled construction & parsing

Four functions located via string xref and decompiled:

| Function | Role |
|---|---|
| `FUN_14112de80` (`0x14112de80`) | Writes the literal `CodexEntry,EntryID,Name,SubCategory,...,BodyID` string (the CSV header documented above) into a buffer, gated behind a condition check — consistent with a debug/CSV export path for codex entries, separate from the JSON journal line. |
| `FUN_14113f5a0` (`0x14113f5a0`) | References the `CodexEntry` string; not fully traced in this pass. |
| `FUN_1411403a0` (`0x1411403a0`) | **Parser/deserializer** for `SAAScanComplete` — string-compares incoming JSON keys against literal names `BodyName`, `ProbesUsed`, `EfficiencyTarget` to populate a result struct. This confirms these three field names against real code (not just the schema string) and shows the game reads these events back in (e.g. for session resume), not just writes them. |
| `FUN_141356520` (`0x141356520`) | Constructor for a `ScanOrganic`-related object; initializes ~12 typed fields via a shared registration call (`FUN_140869ec0`) keyed by internal type-hash constants rather than name strings in the portion decompiled — field names weren't recoverable from this function alone. |

Net result: confirmed that journal events have **two separate code paths** in this binary — JSON line writers (documented
earlier: `Fileheader`/`Continued`/`Status.json` etc.) and a **separate key-based JSON parser** used for at least
`SAAScanComplete`, which exists because the client re-reads certain event types rather than only producing them
write-only.

### Generic journal line-writer chain and the 500,000-line rollover threshold

Tracing callers from the generic array/field serializer (`FUN_140834990`) upward resolves the full write path for an
ordinary journal event line:

```
FUN_140813040 (230 addrs, reached only via indirect/vtable call — not found via direct xref)
  -> FUN_140827200 (172 addrs)
    -> FUN_140834c40 (493 addrs) -- the generic "write one line" function
         - calls FUN_140834990 to append the "timestamp" field + array contents
         - writes the line to the file handle at param_1+0x250
         - increments a per-file line counter at param_1+0xe0
         - if that counter exceeds 500000, calls FUN_140832640 (the "Continued" event
           builder documented above), triggering file rollover
```

This gives a concrete, previously undocumented number: **the journal writer rolls over to a new file after 500,000
lines**, not purely on a time or size basis. (Players observe journals rolling over roughly daily in normal play,
which is consistent with 500K lines being a high ceiling rarely hit except in very long sessions or automation.)

That `FUN_140813040` has no direct callers found by static xref, despite being clearly the generic entry point (every
specific event — `Fileheader`, `CodexEntry`, `ScanOrganic`, etc. — must eventually call into this chain to actually
write), confirms the event classes dispatch into it through a virtual function table rather than a direct call,
matching the `IJournalEntry`-style object pattern seen elsewhere in this codebase (e.g. the `JournalUploadRequest`
constructor in `function-map.md` setting vtable pointers at construction).

## System-wide pattern: hashed-field JSON (de)serialization

Decompiling the status-file handlers for `Market.json` (`FUN_141fa6080`, 5,925 addrs), `Backpack.json`
(`FUN_141abb8a0`, 2,657 addrs), `Cargo.json` (`FUN_141d619a0`, 4,359 addrs), and `ShipLocker.json`
(`FUN_142e88380`, 2,738 addrs) all show the identical shape already seen in the `ScanOrganic` constructor
(`function-map.md`) and the `elite/shipyard/modules/store` endpoint (`network.md`): **no field-name string literals
in the function body** beyond boolean constants. This confirms a system-wide pattern rather than isolated cases: the
game's JSON (de)serialization for status/inventory files is built on **compile-time-hashed field keys**, not runtime
`strcmp` against literal names — a standard performance technique (avoids string comparison on every field of every
parse) that was almost certainly applied uniformly across the whole status-file system, not per-file.

Practical implication for this repo and similar tools: the field *names* documented elsewhere in this file (from the
literal `CodexEntry` CSV header string, and from the public journal manual) are reliable — they're what actually
appears in the JSON on disk — but recovering them *from the binary's own code* requires resolving the hash table
these handlers dispatch through, which is a separate, not-yet-attempted piece of work (would need locating the
hash function and the compile-time hash→field mapping, likely generated at build time and not stored as readable
strings anywhere in the binary).
