# Ideas and Naming

## Adopted identity

| Use | Name |
| --- | --- |
| Product | LPX Keepmorrow |
| Compact brand | LpxKeepmorrow |
| Repository and technical slug | `lpx-keepmorrow` |
| Python package | `keepmorrow` |

Keepmorrow combines “keep” and “morrow” to express preserving present work for
future use. LPX is the short project signature for Lopix Neural Inc. No trademark
registration, name clearance, or domain availability is asserted.

## Product ideas retained from the project direction

| Idea | Status | Purpose |
| --- | --- | --- |
| Project and standalone-conversation organization | Core requirement | Make related work discoverable |
| Unknown-association review queue | Core requirement | Avoid silently misclassifying missing metadata |
| Original-file recovery | Core requirement | Recover useful work independently of the platform |
| Repeated-capture consolidation | Implemented for the experimental profile | Preserve revisions without unexplained duplicates |
| Google Drive adapter | Candidate | Provide an explicitly authorized remote destination |
| ChatGPT-facing experience | Service/UI implemented; actual connection pending | Make supported operations accessible in conversation |
| Optional model-assisted descriptions | Proposal | Improve navigation while preserving evidence boundaries |
| Archive splitting for provider limits | Optional future transport feature | Fit a verified destination limit |
| About-screen and release-note attribution | Accepted direction | Give proportionate creator and company visibility |
| Versioned acceptance and operation authorization | Required | Prevent processing outside the user's agreement |

## Naming conventions

Use nouns that identify responsibility. Prefer `archive`, `manifest`,
`integrity`, `consent`, and `catalog` to generic labels such as
`manager`, `common`, or `misc`. File and folder names are stable interfaces;
rename them with imports, links, tests, and migration notes in the same change.

Documentation paths use lowercase kebab-case. Python modules use snake_case.
Conventional repository filenames retain their established form:
`README.md`, `AGENTS.md`, `LICENSE`, and `SECURITY.md`.

## Organization inside an archive

Group conversation views by confirmed associations without moving or modifying
the original provider data. Use stable identifiers behind user-facing names.
Keep evidence and corrections in metadata, not encoded only in a folder path.
An unknown association must never be placed in a “standalone” group merely
because the source omitted its project identifier.
