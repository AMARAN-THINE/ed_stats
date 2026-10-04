# Built-in developer shell (console) commands

The binary embeds a command shell (`ShellManager`, `Shell::CommandBase`, `Shell::ParsedCommand`, `Shell::NamedArg`).
Commands recovered from usage strings (description → usage):

| Command | Usage | Description |
|---|---|---|
| Help | `Help [{command}] [{string}]` | Display help on the available commands |
| Run | `Run {file:*.cmd}` | Run shell commands from a file, one per line |
| RunProgram | `RunProgram {string}*` | Run a list of commands (a program) directly from the shell |
| Clear | | Clear the shell screen |
| Quit / ForceQuit | | Quit like a user selecting quit / force quit (a delayed assert fires if quit hangs) |
| Delay | `Delay [/Clear] [{Wait=float} {Exec=string}]` | Run a command after N seconds; no args lists queued commands |
| RunInState | `RunInState {string} {string}` | Run a command when a MainGame state machine state is reached |
| DebugInteractive | `DebugInteractive {bool}` | Enable/disable interactive debug |
| DebugSilent | `DebugSilent {bool}` | Enable/disable silent (non-interactive, ignore errors) mode |
| HotKey | `HotKey [{keypress} {string}*]` | Set or clear a hot key bound to a command |
| Repeat | `Repeat {Count=uint32} {Interval=float} {string}+` | Repeat a command; only one active at a time |
| RepeatCancel | | Cancel the active repeat |
| ServerToken | `ServerToken (/Asp \| /Boa \| /Cobra \| /Test \| /PublicTest \| /PrivateTest \| /StagingTest \| /UseInternalServer \| /NoMachineID \| ({string} {string}))*` | Set the central server authentication token |
| ConfigureEpic | `ConfigureEpic {RefreshToken=string} {SandboxID=string} {DeploymentID=string}` | Configure the Epic store helper |
| (seed) | `wseed {uint32}` | Set a world seed |

Argument types seen in parser errors: `float`, `uint32`, `bool`, `string`, `file:*`, `keypress` (with `Control+`/`Shift+`
modifiers), `vector%u`. Streaming reports are available as `Report_Streaming_Streams`, `Report_Streaming_Providers` and
`Report_Streaming_Priority` (CSV output named `%Y%m%d_%H%M%S` + `.csv`).

Further commands exist but are registered by code without a recognisable usage string; use Ghidra xrefs on
`Shell::CommandBase` construction to enumerate them.
