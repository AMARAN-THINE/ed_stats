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
