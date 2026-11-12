# Synthetic Preservation Fixture

Every item in this directory is invented demonstration data. No private conversation, source account, credential, or actual customer record is included.

`synthetic-input/` is the explicitly supplied directory used by the reference core. It contains two ordinary files and one directory. `expected-inventory.json` describes the byte-preservation expectations and the future semantic parser's expected interpretation.

| Scenario | Representation |
| --- | --- |
| Two confirmed projects | Aurora Research and Harbor Design |
| Confirmed project conversations | One conversation in each project, with explicit synthetic evidence |
| Confirmed standalone conversation | An explicit synthetic user decision |
| Unknown association | Missing project metadata retained as unknown |
| Message branching | Two assistant children share one parent message |
| Repeated capture | The same logical conversation and revision occur in two source snapshots |
| Available artifact | `artifacts/research-note.txt` |
| Missing artifact | A referenced `diagram.png` with `not_supplied` status and no fabricated replacement |

The current implementation preserves `catalog.json` as opaque bytes. It does not parse the synthetic conversation schema, resolve identities, calculate semantic counts, or report missing conversation artifacts automatically. Those are explicit acceptance targets for a later source adapter. The file inventory and recovery behavior are implemented and tested.

Use the commands in [Reference Core](../docs/architecture/reference-core.md), including the required explicit acceptance flags, to preserve and recover this fixture.

