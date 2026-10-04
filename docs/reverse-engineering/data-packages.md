# Data package cross-check

A third-party note on the game's data packages (`06_data_packages_and_extraction.md`, supplied by the repo owner) was
cross-checked against this binary (SHA-256 in README.md). Only claims that can be checked statically are recorded here.

## Confirmed in this binary
- Functions exist at the addresses the note names: `0x14004b220` (209-address function, consistent with an AES block
  routine), `0x144987d80` (332), and `0x14496e250` containing `0x14496e34b` (374). The note's `0x14004cbc0` is data, not code
  (consistent with a lookup table). This only confirms the note was written against the same build; I did not verify that these
  are AES or key-wrap routines.
- Path strings for package types: `Win64/Root`, `Win64/Global/Global.ovl`, `Win64/Global/Localised/`,
  `Win64/EffectsBinary/Effects_%s.arc` and `Effects2_%s.arc`, `PlanetShaders/S1.arc`, and five `PlanetShaders\*.csa`
  (e.g. `TerrainComputeShaders.csa`, `...DP.csa`, `...Nvidia.csa`).
- A `data.ovx` reference in a request-style string (`stage=startup&file=data.ovx`), i.e. the file is also fetched/verified
  by the launcher/updater flow.
- The literal magics `FREA` and `fCSA` do **not** appear as strings (they are probably compared as integer constants), and
  `FRES` appears only inside `REFRESH-INTERVAL`.

## Not pursued
The note proposes recovering an AES key from the process or binary to decrypt the encrypted store (`FREA`) files. That is
bypassing the game's content protection to expose copyrighted assets, so it is out of scope for this repo's analysis and was
not attempted. The open container formats (zlib, ARC, CSA, FRES/OVL headers) are described in the source note itself.
