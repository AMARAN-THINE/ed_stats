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

### Refinement: two separate JSON code paths (generic reader vs. hashed writer)

The `Status.json` reader (`FUN_142e874a0`, documented earlier) calls a generic string-keyed JSON library
(`FUN_144c0e4a0` parse, `FUN_144c0db70`/`FUN_144c0db00` has-key/get-key) with literal field names (`"flags"`,
`"event"`, `"timestamp"`). The four hashed-field handlers above (`Market.json`, `Backpack.json`, `Cargo.json`,
`ShipLocker.json`) call **none** of those generic JSON functions — confirming these are a genuinely separate code
path, not just a stylistic difference in the same parser. The most likely explanation: the game **reads** its own
status files back with the fast/simple generic JSON parser (it only needs a few top-level fields to decide what
changed), but **writes** them via a compile-time reflection/serialization system keyed by hashed field tags, matching
the pattern already confirmed for the `StellarForgeInput*` struct serializer in `stellar-forge-struct.md` and the
`CodexEntry`/`ScanOrganic` constructors. This is consistent, not coincidental: the same internal serialization
framework appears to be reused for Stellar Forge planet parameters, journal/codex events, and player status files
alike.

### Hash-dispatcher hypothesis: not located

An attempt to find the actual field-hash lookup/dispatch function (by checking the most frequently called helper
functions inside the `Market.json`/`Backpack.json` handlers) did not pan out: the top candidates
(`FUN_14081fc90`, `FUN_1408218a0`) turned out to be generic container utilities (a growable-array insert/resize
function with 0x38-byte elements and 1.5x growth, and a recursive tree-walk/destructor), not a hash-keyed field
setter. The actual hash dispatch mechanism for these handlers remains unlocated.

## `FSDJump` debug CSV header (`FUN_141d57660`, 549 addresses)

Same pattern as the `CodexEntry` CSV-header writer documented earlier: a gated debug/export path builds a single
large CSV header string naming every field the event can carry. Summarized by category rather than reproduced in
full here:

- **Jump/location core**: event type flags (`FSDJump`, `CarrierJump`, `Location`, `SupercruiseEntry`/`Exit`),
  `StarSystem`, `StarPos`, `Body`/`BodyID`/`BodyType`, `JumpDist`, `BoostUsed`, `SystemAddress`.
- **Station context**: `Docked`, `StationName`/`Type`/`Government`/`Allegiance`/`Faction`/`Economy`/`Services`,
  `MarketID`, `DistFromStarLS`.
- **System economy/politics**: `SystemEconomy`/`SecondEconomy`, `SystemGovernment`, `SystemSecurity`,
  `SystemAllegiance`, `SystemFaction`, and a nested `Factions` array (`Name`, `Influence`, `Government`,
  `Allegiance`, `Population`, `Happiness`, state lists).
- **Powerplay**: `Power`, `Powers`, `ControllingPower`, `PowerplayState` and its progress/reinforcement/undermining
  sub-fields.
- **Player state**: `Taxi`, `Multicrew`, `InSRV`, `OnFoot`, `OnPlanet`, `OnStation`, `FuelUsed`, `FuelLevel`,
  `Latitude`/`Longitude`.
- **Missions**: nested array (`MissionID`, `Name`, `Expires`, `State`, pass/fail flags, `PassengerMission`).
- **Conflicts/war**: nested array (`WarType`, `Faction1`/`2`, `Stake`, `WonDays`, `Winner`, state-machine fields,
  `ThargoidWar`).

This confirms the full breadth of `FSDJump`'s payload directly from code (not just the public journal manual), and
that this event, like `CodexEntry`, has a parallel debug/CSV export path distinct from its JSON journal form.

## `Docked`/`Landed`/`Undocked` state handler (`FUN_142c993c0`, 1,997 addresses)

This function (the largest of several referencing the string `"Docked"`) is a state-machine/status handler
referencing exactly three literal strings: `"Docked"`, `"Landed"`, `"Undocked"` — these three mutually-exclusive
ship-location states, not the full `Docked` journal event's field list (which was already documented via
`network.md`'s `Docked,Undocked,StationName,...` CSV header). This is most likely internal state-name logging/debug
display code rather than the JSON event writer itself; the actual `Docked` event JSON writer was not isolated in
this pass (the event's field list was already recovered from the CSV-header string directly, without needing to
isolate its writer function).

## Signal discovery events (`FSSSignalDiscovered`/`FSSDiscoveryScan`)

Located `FUN_14113fe40` (656 addrs, `FSSSignalDiscovered` constructor — contains the literal field name
`"SignalName"`, confirming at least that field against real code) and `FUN_14137dd80` (1,652 addrs, the larger
handler referencing the full `FSSSignalDiscovered,SystemAddress,...` CSV header). The larger handler, like the
`Market.json`/`Cargo.json` writers, contains no field-name string literals — another instance of the hashed-field
write pattern documented above, further confirming that pattern's reach across both status files and journal event
construction. `FUN_14113fb20` (793 addrs) and `FUN_141391d20` (306 addrs) are the equivalent pair for
`FSSDiscoveryScan`, not individually decompiled in this pass.

`FUN_14113fb20` (793 addrs) confirms `FSSDiscoveryScan`'s `BodyCount` and `NonBodyCount` fields against real code
(matching the CSV header `FSSDiscoveryScan,Progress,BodyCount,NonBodyCount,SystemName,SystemAddress`).
`FUN_141391d20` (306 addrs) shows no additional field-name literals — hashed-field pattern again.

## `Scan` debug CSV header (`FUN_14260bab0`, 352 addresses)

Same gated-debug-export pattern as `CodexEntry` and `FSDJump`. Field categories, summarized rather than reproduced
verbatim:

- **Body identity**: `BodyName`, `BodyID`, `Parents`, `ScanType`, `System`, `SystemAddress`, `Description`.
- **Planet classification**: `PlanetClass`, `TidalLock`, `TerraformState`, `Landable`, `Materials`.
- **Atmosphere**: `Atmosphere`, `AtmosphereType`, `AtmosphereComposition`, `Volcanism`.
- **Star-specific**: `StarType`, `Subclass`, `Luminosity`, `StellarMass`, `AbsoluteMagnitude`.
- **Physical properties**: `MassEM`, `Radius`, `SurfaceGravity`, `SurfaceTemperature`, `SurfacePressure`,
  `Composition` (`Ice`/`Rock`/`Metal`), `Age_MY`.
- **Orbital mechanics**: `DistanceFromArrivalLS`, `OrbitalPeriod`, `RotationPeriod`, `SemiMajorAxis`, `Eccentricity`,
  `OrbitalInclination`, `Periapsis`, `AxialTilt`, `ScanBaryCentre`, `AscendingNode`, `MeanAnomaly`.
- **Rings**: nested array (`Name`, `RingClass`, `MassMT`, `InnerRad`, `OuterRad`, reserve level), plus ring `Percent`
  composition.
- **Discovery/screenshot metadata**: `WasDiscovered`, `WasMapped`, `WasFootfalled`, `Screenshot`/`Filename`/
  `Width`/`Height`/`Latitude`/`Longitude`/`Altitude`/`Heading` (the in-game screenshot-location metadata).

This is the full body-scan schema confirmed directly from code, complementing the public journal manual with a
single authoritative field list and its exact original field ordering.

## Three more short event schemas, confirmed by function + field list

Functions exist (found via string xref) backing these three events; field lists taken from the source CSV-header
strings directly:

| Event | Function | Fields |
|---|---|---|
| `ApproachBody`/`LeaveBody` | `FUN_142c9e5f0` (206 addrs) | `StarSystem`, `Body`, `SystemAddress`, `BodyID` |
| `ApproachSettlement` | `FUN_141c4a1c0` (296 addrs) | `MarketID`, `Name`, `Latitude`, `Longitude`, `BodyName`, `SystemAddress`, `BodyID` |
| `CarrierJumpRequest`/`CarrierJumpCancelled` | `FUN_142564e60` (318 addrs) | `CarrierID`, `SystemName`, `SystemAddress`, `BodyID`, `Body`, `DepartureTime`, `CarrierLocation`, `StarSystem`, `CarrierType` |

Unlike the longer CSV headers (`CodexEntry`, `FSDJump`, `Scan`), the decompiler represented these shorter strings as
inline immediate-value stores rather than a single recognizable string literal, so they were read directly from the
raw string table instead of the decompiled C.

## Remaining event schemas captured from the string table

Field lists for several more events, taken directly from their literal CSV-header strings (format matches the
pattern established above; functions not individually traced for all of these in this pass):

| Event | Fields |
|---|---|
| `ScanOrganic` | `ScanType`, `Name`, `Genus`, `Species`, `Variant`, `WasLogged`, `SystemAddress`, `Body`, `SellOrganicData`, `MarketID`, `Value`, `Bonus`, `BioData` |
| `SAAScanComplete` | `BodyName`, `BodyID`, `Discoverers`, `Mappers`, `ProbesUsed`, `EfficiencyTarget`, `SAASignalsFound`, `SystemAddress`, `Signals` (`Type`/`Count`), `Genuses` |
| `FSSBodySignals` | `StarSystem`, `SystemAddress`, `BodyID`, `BodyName`, `Signals` (`Type`/`Count`) |
| `NavBeaconScan` | `SystemAddress`, `NumBodies` |
| `Docked`/`Undocked` | `StationName`, `StationType`, `CockpitBreach`, `StationFaction`/`FactionState`, `StarSystem`, `StationAllegiance`, `StationEconomy`/`StationEconomies` (`Name`/`Proportion`), `StationGovernment`, `StationState`, `Security`, docking-request outcomes (`DockingRequested`/`Granted`/`Denied`/`Cancelled`/`Timeout`), `LandingPad`, `Reason`, `DistFromStarLS`, `StationServices`, `SystemAddress`, `MarketID`, `Wanted`, `ActiveFine`, `Taxi`, `Multicrew`, `LandingPads` (`Small`/`Medium`/`Large` counts) |

Together with the events documented above, this covers the large majority of the exploration/scanning-relevant
journal events most useful to a tool like this repo (`ed_stats`): `CodexEntry`, `ScanOrganic`, `SAAScanComplete`,
`FSSSignalDiscovered`, `FSSBodySignals`, `FSSDiscoveryScan`, `Scan`, `NavBeaconScan`, `ApproachBody`,
`ApproachSettlement`, `Docked`/`Undocked`, `FSDJump`, `NavRoute` (fields: `Route`, `StarSystem`, `SystemAddress`,
`StarPos`, `StarClass`), `CarrierJumpRequest`.

## Powerplay and communication event schemas

| Event | Fields |
|---|---|
| `PowerplayVoucherRedeem`/`PowerplayCollect`/`PowerplayDeliver` | `Power`, `Type`, `Count` |
| `SendText`/`ReceiveText` | `To`, `From`, `Message`, `Channel`, `Sent` |
| `Friends` | `Status` |

Additional Powerplay-related identifiers found as class/handler names (not full field lists):
`PowerplayCarrierSbotageResponder` [sic — "Sbotage" is a typo in the binary, not mine], `PowerplayContact`,
`PowerplayDefect`, `PowerplayDetails`.

## Engineering, shipyard, outfitting, and material event schemas

| Event | Fields |
|---|---|
| `EngineerCraft`/`EngineerLegacyConvert` | `Engineer`, `EngineerID`, `Blueprint`, `BlueprintID`, `Level`, `Ingredients` (`Name`/`Count`), `Override`, `Slot`, `Module`, `Quality`, `IsPreview` |
| `EngineerContribution` | `Engineer`, `EngineerID`, `Blueprint`, `BlueprintID`, `Type`, `Faction`, `Commodity`, `Material`, `Quantity`, `TotalQuantity`, `ApplyExperimentalEffect` |
| `ModuleBuy`/`ModuleBuyAndStore`/`ModuleSell`/`ModuleSwap`/`ModuleStore`/`ModuleRetrieve`/`ModuleSellRemote` | `Slot`, `SellItem`/`SellPrice`, `BuyItem`/`BuyPrice`, `FromSlot`/`ToSlot`/`FromItem`/`ToItem`, `Ship`/`ShipID`, `StoredItem`, `InTransit`, `ReplacementItem`/`RetrievedItem`/`SwapOutItem`, `Cost`, `EngineerModifications`, `StorageSlot`, `TransferCost`/`TransferTime`, `RestockVehicle`, `StoredModules`, `StationName`, `MarketID`, `Horizons`, `Hot` |
| `ShipyardBuy`/`Sell`/`Swap`/`Transfer`/`New`/`Redeem` | `ShipType`, `ShipPrice`, `StoreOldShip`/`SellOldShip`/`SellPrice`, `TransferPrice`/`TransferTime`, `System`, `Distance`, `ShipID`/`SellShipID`/`StoreShipID`/`NewShipID`, `StoredShips`/`ShipsHere`/`ShipsRemote`, `Shipyard`/`PriceList`, `StationName`, `MarketID`, `AllowCobraMkIV`, `Hot`, `ClearImpound`, `BundleID`, `ShipRedeemed`, `ShipyardBankDeposit` |
| `MaterialCollected`/`MaterialDiscarded`/`MaterialDiscovered` | `Category`, `Name`, `Count`, `DiscoveryNumber` |
| `Synthesis` | `Name`, `Materials` |
| `*MicroResources` (Buy/Sell/Trade/Transfer/RequestPower/DeliverPower) | `Name`, `Price`, `Offered`, `Received`, `MarketID`, `TotalCount`, `Direction`, `Context`, `LockerOldCount`/`LockerNewCount` |

This covers the majority of the ship-ownership, engineering, and crafting-related journal events.

## Commander state: `LoadGame`, `Rank`/`EngineerProgress`

| Event | Fields |
|---|---|
| `LoadGame` | `Commander`, `Ship`/`ShipID`, `StartLanded`, `StartDead`, `GameMode`, `Group`, `Credits`, `Loan`, `ShipName`, `ShipIdent`, `FuelLevel`/`FuelCapacity`, `HullValue`/`HullHealth`, `ModulesValue`, `Rebuy`, `Horizons`, `Odyssey`, `FID`, `Hot`, `UnladenMass`, `Main`/`Reserve` (fuel tanks), `CargoCapacity`, `MaxJumpRange` |
| `Rank` | `Combat`, `Trade`, `Explore`, `Soldier`, `Exobiologist`, `Empire`, `Federation`, `CQC` |
| `Progress`/`Promotion` | per-rank-category progress percentages (same category list as `Rank`) |
| `EngineerProgress` | `Rank`, `Engineer`, per-superpower reputation (`Federation`/`Empire`/`Independent`/`Alliance`), `Reputation`, `Engineers` array, `RankProgress` |

This confirms the complete commander-rank category list directly from code: Combat, Trade, Explore, Soldier (CQC
ground combat... actually mercenary), Exobiologist, Empire, Federation, CQC — eight parallel rank tracks.

## Fleet Carrier event schemas

| Event(s) | Fields |
|---|---|
| `CarrierStats`, `CarrierDecommission`/`CarrierCancelDecommission`, `CarrierBankTransfer`, `CarrierCrewServices`, `CarrierFinance`, `CarrierShipPack`, `CarrierModulePack`, `CarrierDockingPermission` | `CarrierID`, `CarrierType`, `Deposit`/`Withdraw`, `PlayerBalance`/`CarrierBalance`/`AvailableBalance`, `ReservePercent`/`ReserveBalance`, `ScrapRefund`/`ScrapTime`, `Operation`, `PackTheme`/`PackTier`, `Cost`/`Refund`, `DockingAccess`, `AllowNotorious`, `Name`, `FuelLevel`, `JumpRangeCurr`/`JumpRangeMax`, `PendingDecommission`, `SpaceUsage` (`Crew`/`Cargo`/`CargoSpaceReserved`/`ShipPacks`/`ModulePacks`/`FreeSpace`/`TotalCapacity`), `Finance`, `Callsign`, `CrewRole`/`CrewName`, `Activated`, `Enabled` |
| `CarrierDepositFuel` | `CarrierID`, `Amount`, `Total` |
| `CarrierNameChange` | `CarrierID`, `Name`, `Callsign` |

Combined with `CarrierJumpRequest`/`CarrierJumpCancelled` documented above, this covers the full Fleet Carrier
journal event set, matching the 30-endpoint `elite/fleetcarrier/*` cluster in `server-endpoints.txt`.

## Odyssey on-foot event schemas

| Event | Fields |
|---|---|
| `Backpack`/`BackpackChange` | `Name`, `OwnerID`, `MissionID`, `Count`, `Items`, `Components`, `Consumables`, `Data`, `Added`/`Removed`, `Type`, `TransferComplete` |
| `UseConsumable` | `Name`, `Type` |
| `CollectItems` | `Name`, `Type`, `OwnerID`, `Count`, `Stolen` |
| `FCMaterials` | `MarketID`, `CarrierName`, `CarrierID`, `Items` (`id`/`Name`/`Price`/`Stock`/`Demand`) |

`FCMaterials` matches the file of the same name listed in `README.md`'s file-name findings — this is the carrier
commodity-market journal counterpart to the `FCMaterials.json` status file.

## Crime and combat event schemas

| Event | Fields |
|---|---|
| `Bounty` | `Rewards` (`Faction`/`Reward` per entry), `PilotName`, `Target`, `TotalReward`, `SharedWithOthers`, `Faction`, `VictimFaction`, `Reward` |
| `FactionKillBond` | `Reward`, `AwardingFaction`, `VictimFaction` |
| `Died` | `Killers` (`Name`/`Ship`/`Rank` per killer), `KillerName`/`KillerShip`/`KillerRank`, `Name`/`Ship`/`Rank`, `CrewLaunchFighter`, `Crew`/`ID`, `Telepresence` (for the single- vs. wing-kill variants) |
| `ShipTargeted`/`TargetLocked` | `Ship`, `ScanStage`, `PilotName`/`PilotRank`, `SquadronID`, `ShieldHealth`/`HullHealth`, `Faction`, `LegalStatus`, `Bounty`, `Subsystem`/`SubsystemHealth`, `Power` |
| `Interdiction`/`Interdicted`/`EscapeInterdiction` | `Submitted`, `Success`, `Interdictor`, `IsPlayer`, `CombatRank`, `Faction`, `Power`, `IsThargoid` |
| `CommitCrime` | `CrimeType`, `Faction`, `Victim`, `Fine`, `Bounty` |
| `PayFines`/`PayLegacyFines`/`PayBounties`/`RedeemVoucher` | `AllFines`, `Type`, `Amount`, `BrokerPercentage`, `Faction`/`Factions` |

This covers the core combat/crime/bounty journal events.

## Trade, mining, and ship-service event schemas

| Event | Fields |
|---|---|
| `MarketBuy`/`MarketSell` | `Type`, `Count`, `BuyPrice`/`TotalCost`, `SellPrice`/`TotalSale`, `AvgPricePaid`, `IllegalGoods`, `StolenGoods`, `BlackMarket` |
| `Market` (status file) | `Items` (`Name`/`MeanPrice`/`Stock`/`Demand`/`Consumer`/`Producer`/`Contraband`/`Rare`/`Category`/`StockBracket`/`DemandBracket`), `StationName`, `StarSystem`, `MarketID`, `StationType`, `CarrierDockingAccess` |
| `ProspectedAsteroid` | `Materials`, `MotherlodeMaterial`, `Content`, `Remaining` |
| `MiningRefined` | `Type` |
| `BuyAmmo`/`RestockVehicle` | `Loadout`, `Type`, `Cost`, `Count` |
| `BuyDrones`/`SellDrones` | `Type`, `Count`, `BuyPrice`/`TotalCost`, `SellPrice`/`TotalSale` |
| `Repair`/`RepairAll` | `Item`/`Items`, `Cost`, `Amount` |
| `RefuelAll`/`RefuelPartial` | `Cost`, `Amount` |
| `FuelScoop` | `Scooped`, `Total` |

This closes out the trade/mining/ship-maintenance event group.

## Wing and multicrew event schemas

| Event | Fields |
|---|---|
| `WingJoin`/`WingAdd`/`WingLeave`/`WingInvite` | `Name`, `Others` |
| `JoinACrew`/`QuitACrew`/`CrewMemberJoins`/`CrewMemberQuits`/`ChangeCrewRole`/`KickCrewMember`/`EndCrewSession` | `Captain`, `Crew`, `Role`, `CrewMemberRoleChange`, `OnCrime`, `Telepresence` |
| `CrewHire`/`CrewFire`/`CrewAssign` | `Name`, `Cost`, `Role`, `CombatRank`, `Faction`, `CrewID` |
| `NpcCrewPaidWage` | `NpcCrewId`, `NpcCrewName`, `Amount` |
| `NpcCrewRank` | `NpcCrewId`, `NpcCrewName`, `RankCombat`, `EngineerID` |
| `CargoDepot` | `MissionID`, `StartMarketID`/`EndMarketID`, `ItemsCollected`/`ItemsDelivered`/`TotalItemsToDeliver`, `Progress`, `UpdateType`, `CargoType`, `Count` |

This closes out the wing/multicrew/NPC-crew/cargo-mission event group.

## Remaining travel/mission-flow event schemas

| Event | Fields |
|---|---|
| `DataScanned` | `Type` |
| `DatalinkScan` | `Message` |
| `DatalinkVoucher` | `Reward`, `VictimFaction`, `PayeeFaction` |
| `Resurrect` | `Option`, `Cost`, `Bankrupt`, `SellShipOnRebuy`, `ShipType`, `System`, `SellShipId`, `ShipPrice`, `CarrierBankTransfer`, `CarrierID`, `Withdraw`, `PlayerBalance`/`CarrierBalance` |
| `BookTaxi`/`BookDropship`/`CancelTaxi`/`CancelDropship` | `Cost`, `Refund`, `DestinationSystem`/`DestinationLocation`, `Retreat` |
| `Touchdown`/`Liftoff` | `Latitude`, `Longitude`, `PlayerControlled`, `NearestDestination`, `Taxi`, `Multicrew` |

This is a natural stopping point for the journal-event survey: combined with everything documented above in this
file, the schema list now covers exploration (Codex/Scan/Organic/Signals), navigation (FSDJump/NavRoute/Approach),
stations (Docked/Market/Outfitting/Shipyard), engineering, Fleet Carriers, Powerplay, crime/combat, wing/multicrew,
on-foot/Odyssey, commander state, and travel/taxi/resurrection — the large majority of the public journal manual's
event catalogue, each cross-checked against literal strings actually present in the shipped binary rather than taken
on faith from documentation alone.

## Combat status and squadron event schemas

| Event | Fields |
|---|---|
| `HeatWarning`/`HeatDamage` | (no additional fields beyond the event name itself) |
| `HullDamage` | `Health`, `PlayerPilot`, `Fighter` |
| `ShieldState` | `ShieldsUp` |
| `UnderAttack` | `Target` |
| `NewCommander` | `Name`, `FID`, `Package` |

`Squadron*`-prefixed identifiers (over 70 found) are mostly UI/activity component names for the in-game squadron
management screens (browsing, applications, bank, carrier integration, logo customisation, leaderboards, chat) rather
than journal event fields — `SquadronCreateJoin`, `SquadronPromotion`/`SquadronDemotion`, `SquadronInvite`,
`SquadronBank`/`SquadronBankActivity` and `SquadronCarrier*` are the closest to journal-relevant events, but their
field lists weren't isolated in this pass (unlike the CSV-header events documented elsewhere in this file, squadron
events don't appear to share one consolidated header string).

## Mission lifecycle event schemas

| Event | Fields |
|---|---|
| `MissionRedirected` | `MissionID`, `NewDestinationStation`/`OldDestinationStation`, `NewDestinationSystem`/`OldDestinationSystem` |
| `MissionAbandoned` | `Name`, `MissionID`, `Fine` |
| `MissionFailed` | `Name`, `MissionID`, `Fine` |
| `PVPKill` | `Victim`, `CombatRank` |
| `AsteroidCracked` | `Body` |

A separate, much larger consolidated mission-field string (already captured in `README.md`'s string-table findings)
covers `MissionAccepted`/`MissionCompleted` and the general `Missions` array: `Name`, `System`, `Reward`, `Faction`,
`PermitsAwarded`, `Commodity`/`Count`, `Donation`, `TargetType`/`Target`/`TargetFaction`, `Expiry`, `MissionID`,
`DestinationSystem`/`DestinationStation`/`DestinationSettlement`, `PassengerCount`/`PassengerVIPs`/`PassengerWanted`/
`PassengerType`, `CommodityReward`/`MaterialsReward`, `Influence`, `Reputation`/`ReputationTrend`, `KillCount`,
`LocalisedName`, `CGID`, `Donated`, `FactionEffects` (`Trend`/`Effect`/`Effects`), `SystemAddress`, `Category`,
`Wing`, `NewDestinationStation`/`NewDestinationSystem`.

This closes out the mission-lifecycle event group, completing the journal-event schema survey for this pass.

## CommunityGoal status schema

`CommunityGoal`/`CurrentGoals`: `CGID`, `Title`, `SystemName`, `MarketName`, `Expiry`, `IsComplete`, `CurrentTotal`,
`PlayerContribution`, `NumContributors`, `TierReached`, `PlayerPercentileBand`, `Bonus`, `Name`, `TopTier`,
`TopRankSize`, `PlayerInTopRank`.

## Suit/loadout event schema (Odyssey)

`BuyWeapon`/`SellWeapon`/`BuySuit`/`SellSuit`/`CreateSuitLoadout`/`SwitchSuitLoadout`/`DeleteSuitLoadout`/
`RenameSuitLoadout`/`LoadoutEquipModule`/`LoadoutRemoveModule`: `Name`, `Price`, `SuitID`, `LoadoutID`/`LoadoutName`,
`Module`/`SlotName`/`ModuleName`/`Modules`, `SuitModuleID`, `SuitName`, `Class`, `SuitMods`, `WeaponMods`.
Request field: `&suitLoadoutSlotId=`.

## Vehicle/SRV/fighter and repair event schemas

| Event | Fields |
|---|---|
| `DockSRV`/`DockFighter`/`VehicleSwitch` | `To`, `ID`, `Embark`, `Disembark`, `DropshipDeploy`, `Muilticrew` [sic], `SRV`, `Taxi`, `Crew`, `Name`, `Role`, `SRVType` |
| `FighterDestroyed` | `ID` |
| `LaunchDrone` | `Type` |
| `AfmuRepairs` | `Module`, `FullyRepaired`, `Health` |
| `ReservoirReplenished` | `FuelMain`, `FuelReservoir` |
| `MaterialTrade` | `MarketID`, `TraderType`, `Material`/`MaterialID`, `Quantity`, `Paid`, `Received`, `Category` |

These complete the vehicle-launch/dock, repair, and material-trading event groups.

## Misc small event schemas

| Event | Fields |
|---|---|
| `Music` | `MusicTrack` |
| `SetUserShipName` | `Ship`, `ShipID`, `UserShipName`, `UserShipId` |
| `CrimeVictim` | `Offender` |

## Powerplay rank/merits and remaining SRV/drone event schemas

| Event | Fields |
|---|---|
| `PowerplayJoin`/`PowerplayLeave` | `Power`, `FromPower`/`ToPower`, `Rank`, `Merits`, `TimePledged` |
| `Powerplay` (status/merits events) | `PowerplayMerits`, `MeritsGained`, `TotalMerits`, `PowerplayRank` |
| `RepairDrone` | `HullRepaired`, `CockpitRepaired`, `CorrosionRepaired` |
| `SRVDestroyed` | `ID`, `SRVType` |

This closes out the Powerplay rank-progression and remaining SRV/drone event groups.

### Hash-dispatcher hunt, third attempt: also a dead end

`UInt32ToStringHashMap` exists as a type name in the binary (confirming a uint32-keyed hash map data structure is
used somewhere in the codebase) but has zero direct code cross-references — like the RTTI-only registration strings
documented elsewhere, it's likely only referenced through compiler-generated type metadata, not a findable call site.
This is the third distinct lead chased for the hashed-field dispatch mechanism (after the `FUN_140869e30`/`ec0`
service-locator functions and the high-frequency-call candidates in the `Market.json` handler), and all three have
hit dead ends. The mechanism remains real (confirmed by its effects — zero string literals in affected handlers) but
unlocated; further progress would need a different method, such as dynamic analysis/tracing, which is out of scope
for static analysis of this executable alone.

## Legacy exploration-data and carrier trade order schemas

| Event | Fields |
|---|---|
| `BuyExplorationData`/`SellExplorationData`/`MultiSellExplorationData` (legacy, pre-Codex) | `System`, `Cost`, `Systems`, `Discovered`, `BaseValue`, `Bonus`, `TotalEarnings`, `SystemName`, `NumBodies` |
| `RedeemVoucher` | `Type`, `Amount`, `Faction` |
| `CarrierTradeOrder` | `CarrierID`, `BlackMarket`, `Commodity`, `PurchaseOrder`/`SaleOrder`, `CancelTrade`, `Price` |

## `Status.json` full field schema

Confirmed via literal CSV-header string (complements the decompiled reader `FUN_142e874a0` documented earlier, which
only checks for `flags`/`event`/`timestamp` as required keys): `Flags`, `Flags2`, `Pips`, `FireGroup`, `GuiFocus`,
`Latitude`/`Longitude`, `Heading`, `Altitude`, `Fuel`, `Cargo`, `BodyName`, `PlanetRadius`, `LegalState`, `Oxygen`,
`Health`, `Gravity`, `Temperature`, `SelectedWeapon`, `Destination`, `System`, `Body`, `Name`, `Balance`, and the
nested `ShipLocker` block (`Name`, `OwnerID`, `MissionID`, `Count`, `Type`, `Items`, `Components`, `Consumables`,
`Data`).

### Hashed-field pattern extended to Outfitting.json, Shipyard.json, NavRoute.json

`FUN_141fa8570` (`Outfitting.json`, 4,822 addrs), `FUN_141fa9850` (`Shipyard.json`, 3,163 addrs), and `FUN_1425e78b0`
(`NavRoute.json`, 1,273 addrs) all show the identical hashed-field pattern (no field-name string literals beyond
boolean constants) already confirmed for `Market.json`/`Cargo.json`/`Backpack.json`/`ShipLocker.json`. This is now
confirmed across 7 of the 9 known status files, making it very likely a uniform convention across the entire
status-file write path rather than a per-file choice.

## Neutron/white dwarf and technology broker event schemas

| Event | Fields |
|---|---|
| `JetConeDamage`/`JetConeBoost` | `BoostValue`, `Module`, `Damage` |
| `TechnologyBroker` | `BrokerType`, `MarketID`, `ItemsUnlocked`, `Ingredients` (`Commodities`/`Materials`), `Category`, `Name`, `Count` |

## Powerplay 2.0 covert-action event schema

| Event | Fields |
|---|---|
| `HoloscreenHacked` | `PowerBefore`, `PowerAfter` |

Matches `elite/powerplay2/holoscreen/hack` in the endpoint catalogue (`server-endpoints.txt`), one of the Powerplay
2.0 covert-action endpoints (alongside `ship/scan`, `megaship/scan`, `carrier/sabotage`).

## `SearchAndRescue` and `Scanned` event schemas

| Event | Fields |
|---|---|
| `SearchAndRescue` | `MarketID`, `Name`, `Count`, `Reward` |
| `Scanned` | `ScanType` |

### Hashed-field pattern extended to survey endpoints

`FUN_1413842c0` (`survey/body/multiscan`), `FUN_141dcfc40` (`survey/beacon/scan`), `FUN_141383b00`
(`survey/info`) all show zero field-name string literals, consistent with the hashed-field dispatch pattern already
confirmed across status files and multiple other endpoint handlers.

## Session lifecycle and legacy trade-data schemas

| Event | Fields |
|---|---|
| `ClearSavedGame` | `Name`, `FID` |
| `BuyTradeData` (legacy) | `System`, `Cost` |

Other standalone identifiers found but without a full field list: `Shutdown`, `SystemsShutdown` (likely bare
event-name-only entries, consistent with how `HeatWarning`/`HeatDamage` were documented earlier).

## `UpgradeWeapon`/`UpgradeSuit` schema

`UpgradeWeapon`/`UpgradeSuit`: `Name`, `Class`, `Cost`, `SuitID`, `SuitModuleID`, `Resources`.

## `CollectCargo`/`EjectCargo` schema

Two slightly different field sets found (likely an engine-version difference, matching the game-update point raised
in this conversation): `CollectCargo`/`EjectCargo`: `Type`, `Count`, `Stolen`, `Abandoned`, `MissionID`, with a newer
variant adding `PowerplayOrigin`.

## `LaunchFighter`/`LaunchSRV`/`LaunchVessel` schema

`LaunchFighter`/`LaunchSRV`/`LaunchVessel`: `VesselType`, `Loadout`, `PlayerControlled`, `FighterRebuilt`, `ID`,
`SRVType`.

## `FSSSignalDiscovered` — full field list (supersedes earlier partial note)

Fuller field list found: `SystemAddress`, `SignalName`, `SpawningState`, `SpawningFaction`, `ThreatLevel`,
`TimeRemaining`, `IsStation`, `USSType`, `SignalType`, `SpawningPower`, `OpposingPower`. This complements the single
`SignalName` field confirmed earlier directly against decompiled code.
