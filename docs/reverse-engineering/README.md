# EliteDangerous64.exe – static reverse-engineering notes

Static analysis only (Ghidra 11.3.2 headless auto-analysis + string/import export). The binary was **never executed**
and is **not** included in this repository.

| Item | Value |
|---|---|
| File size | 103,469,056 bytes |
| SHA-256 | `e6be8bbe04e6a7ae226d4318945af7f367de13dc5a007a261964d9ba8144e988` |
| Format | PE32+ (x86-64), GUI subsystem, large-address-aware, ASLR/NX/high-entropy VA |
| Linker | MSVC 14.29 (VS2019) |
| PE timestamp | 2026-09-02 21:33:40 UTC |
| Image base / entry | `0x140000000` / `0x144899118` |
| Image size | `0x6409000` (~100 MB) |
| Authenticode | none (Security directory empty) |
| Functions found by Ghidra | 129,454 (1,382 named from exports/RTTI/symbols, rest `FUN_*`) |
| Strings (>=6 chars) | ~60,800 |

Provenance caveat: the hash was not checked against any known-good value and the file has no Authenticode signature,
so it cannot be confirmed as an unmodified official build.

## Layout
- Sections `.text` (~79 MB code), `.rdata`, `.data`, `.pdata`, `.reloc`, `.rsrc`, `.tls`.
- Data directories present: export, import, resource, exception, base reloc, debug, TLS, load config, IAT.
- An export directory exists (unusual for an exe); entries are mostly middleware thunks.
- Largest functions (address count): `FUN_143c44dc0` (69,755), `FUN_144b6d0d0`/`FUN_144b5dfd0` (61,687 each),
  `FUN_144d3aa00` (58,403). The `0x144b…` cluster looks generated/table-driven.

## Imports (415 symbols)
KERNEL32 (212), USER32 (73), WS2_32 (46), EOSSDK-WIN64-SHIPPING (14), ADVAPI32 (13), OLE32 (12), PORTAUDIO_X64 (10),
WINMM, SETUPAPI, OPENVR_API (5 each), SHELL32, IPHLPAPI (4), OLEAUT32, GDI32 (3), XINPUT9_1_0 (2), DXGI, DINPUT8,
DBGHELP, D3D11 (1 each).

Takeaways: D3D11 + DXGI renderer, DirectInput/XInput input, WinSock networking, Epic Online Services SDK,
PortAudio for voice, OpenVR for VR.

## Subsystems identified from strings / RTTI
- **Engine**: Frontier "FGDK4" code base; graphics modules under `Src\Core\f3d\_private\` (f3dDevice, f3dShader,
  f3dResource, f3dSwapChain, f3dQuery, f3dViews, f3dStateBlocks, f3dVertexShaderBinding), DX11 backend.
- **Scripting**: embedded Lua 5.3.1 (game audio scripts, mission/UI text keys).
- **Networking/HTTP**: libcurl + OpenSSL, MiniUPnPc (UPnP port mapping), WinSock.
- **Audio**: Audiokinetic Wwise, PortAudio, Ogg/Vorbis, VP8/WebM video.
- **VR**: OpenVR interfaces (IVRSystem, IVRCompositor, IVROverlay, IVRChaperone) and LibOVR runtime loading.
- **Store/login**: Epic Online Services token handling and Steam registry detection.
- **UI**: ActionScript-style Flash UI symbols.

## Command line / server selection
A usage string documents: `ServerToken (/Asp | /Boa | /Cobra | /Test | /PublicTest | /PrivateTest | /StagingTest |
/UseInternalServer | /NoMachineID | ({string} {string}))*`. Other flags seen: `-forcepack`, `-infinity`, `-mobius`,
`-mobiusHost`, `-noninteractive`, `-defaultContinueOnError`, `-fastNonStationMissions`, `-nonStationMissionsImportant`.

Hard-coded hostnames found as plain strings: `api.live.local.elite.onsrvdev1.corp.frontier.co.uk`,
`api.live.internalprod.elite.onsrvdev1.corp.frontier.co.uk`, `api.orerve.net`. A `2.0/elite/journal` path is used with
`UploadJournal`, `TransmitJournal` and `FlushUploadJournalActivity`. The Epic login flow uses the header
`X-Frontier-EpicAuth` and a console command `ConfigureEpic {RefreshToken} {SandboxID} {DeploymentID}`.

## Chat commands (in-game)
`/local`, `/direct`, `/squadron`, `/multicrew`, `/voice`, `/reply`, `/names`, `/clear`, `/LinkInfo`, plus lookup helpers
`/FIND:`, `/LOOKUP:`, `/MATCH:`, `/DEFINE:`.

## Files the game reads/writes (names found)
Config: `AppConfig.xml`, `AppConfigLocal.xml`, `AppNetCfg.xml`, `AudioConfiguration.xml`, `GraphicsConfiguration.xml`,
`Graphics/DisplaySettings.xml`, `Startup/Settings.xml`, `ControlSchemes/DeviceMappings.xml`, `DeviceDefaults.xml`.
Journal companions (relevant to this repo): `Status.json`, `Cargo.json`, `Backpack.json`, `ShipLocker.json`,
`NavRoute.json`, `Market.json`, `Outfitting.json`, `Shipyard.json`, `ModulesInfo.json`, `FCMaterials.json`.

## Journal
Journal files are JSON-lines with a header like
`{ "timestamp":…, "event":"Fileheader", "part":N, "language":"…", "Odyssey":bool, "gameversion":"…", "build":"…" }` and a
`Continued` event on roll-over. Other event names are built at runtime, so the catalogue cannot be recovered from
strings alone; use the official journal manual for field definitions.

## Not done / next steps
- No review of individual decompiled functions; `FUN_*` bodies are unnamed.
- Dynamic analysis was intentionally not performed.
- Suggested: RTTI/vtable recovery; xref `Fileheader` to find the journal writer; compare against a verified build.

## Reproducing
```
analyzeHeadless <proj_dir> ed -import EliteDangerous64.exe \
  -scriptPath docs/reverse-engineering/tools -postScript Export.py <out_dir> -deleteProject
```
Auto-analysis took roughly 50 minutes. `tools/Export.py` writes `functions.tsv`, `imports.tsv`, `strings.tsv`, `blocks.tsv`.
