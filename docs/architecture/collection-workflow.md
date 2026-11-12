# Local Collection Workflow

**Release:** 0.2.0 internal development
**Publisher:** Lopix Neural Inc.
**Engineering lead:** Fabio de Sousa Lopes
**Contact:** fabio@lopixneural.com

This workflow operates on material explicitly supplied by the operator. It does
not access a ChatGPT account or establish that an export contains every account
record or binary. Read the [import contract](import-contract.md) before relying
on the experimental mapping profile.

## 1. Review the current documents

Read [Terms of Use](../../legal/terms-of-use.md) and
[Privacy Notice](../../legal/privacy-notice.md), both draft version
`2026-11-12-draft.2`. The CLI requires both exact declarations for every operation
that inspects selected material. Missing or old versions fail before source
inspection. These development declarations do not authenticate an end user or
establish legal approval of the drafts.

Use Python 3.11 or later on the verified Linux/Windows configurations. From the
repository, set `PYTHONPATH=src` in the shell; in PowerShell use
`$env:PYTHONPATH = "src"`. Commands below show a POSIX shell; put each command on
one line in PowerShell. Destinations must be new and outside selected source trees.

## 2. Preserve and interpret selected exports

```bash
python -m keepmorrow import ./export-first.zip ./export-second \
  --destination ../collection-001 --account-namespace my-local-account \
  --accept-terms 2026-11-12-draft.2 --accept-privacy 2026-11-12-draft.2
```

The account namespace is a stable local label, not a credential. Use the same
label for later exports from the same account and a different label for another
account. An email address is unnecessary. Logical conversation identity includes
the provider, this namespace, and the source conversation identifier.

Directory files are copied without format conversion. For supported ZIPs, both
the complete original container and extracted contents are preserved. The parser
reads preserved JSON; it never rewrites the source or follows embedded URLs.

| Archive path | Meaning |
| --- | --- |
| `manifest.json` | Versioned inventory and SHA-256 hashes for every payload file |
| `payload/captures/000001/source/` | Supplied files from one capture, including unassociated binaries |
| `payload/captures/000001/original.zip` | Original ZIP bytes, when ZIP intake was used |
| `payload/catalog.json` | Derived identities, revisions, graph nodes, provenance, and artifact states |
| `payload/report.json` | Parser coverage, item outcomes, counts, and limitations |
| `payload/index.html` | Standalone escaped view with local file links and no scripts/network requests |

Open `payload/index.html` directly to inspect the archive. The view lists message
parents and children instead of silently flattening branches. It is a derived
view; the captured source files retain unknown fields and original wording.

## 3. Interpret the outcome

| Exit status | Meaning |
| --- | --- |
| `0` | The requested operation completed within its declared contract |
| `1` | Ordinary archive verification found an inventory or byte mismatch |
| `2` | Acceptance, input, validation, filesystem, or other supported operation error |
| `3` | A collection was preserved and verified, but semantic coverage is partial or unsupported |
| `130` | The operator interrupted the operation; completion is not asserted |

Missing media, unresolved pointers, unsupported source content, and conflicting
source observations remain visible. A count of `null` for a source document means
the record count is unavailable, not that an empty export was observed. Even a
complete parser result says nothing about unsupplied account data.

## 4. Add another capture without changing the previous generation

```bash
python -m keepmorrow import ./export-third.zip \
  --previous ../collection-001 --destination ../collection-002 \
  --account-namespace my-local-account \
  --accept-terms 2026-11-12-draft.2 --accept-privacy 2026-11-12-draft.2
```

This verifies the prior collection, copies its preserved captures into a new
generation, and reconciles the new records. Renaming a conversation creates a
revision under its existing namespaced identity. An unchanged complete source
record reuses that revision and adds capture provenance. Repeated inputs retain
separate capture occurrences and physical file copies; cross-capture blob
deduplication is not implemented.

The source fingerprint describes bytes. Capture identifiers also include their
sequence in the generation. Capture order is the explicit input order, not a
claim about platform edit chronology. Extending a generation requires space for
the new complete output and temporarily for any ZIP extraction.

## 5. Browse, search, and read

```bash
python -m keepmorrow catalog ../collection-002 --limit 20 \
  --accept-terms 2026-11-12-draft.2 --accept-privacy 2026-11-12-draft.2

python -m keepmorrow search ../collection-002 "preservation" --limit 20 \
  --accept-terms 2026-11-12-draft.2 --accept-privacy 2026-11-12-draft.2

python -m keepmorrow read ../collection-002 CONVERSATION_KEY --offset 0 --limit 50 \
  --accept-terms 2026-11-12-draft.2 --accept-privacy 2026-11-12-draft.2
```

Replace `CONVERSATION_KEY` with an exact key returned by the catalog. Search is
literal and Unicode case-insensitive, across retained revisions. Queries verify
the whole archive before inspecting its catalog. This is a deliberate integrity
cost, not an indexed-search latency claim.

Read output is paginated and bounded: text, titles, child references, and revision
lists have explicit truncation indicators. The standalone archive retains their
full supported content. Without `--revision-id`, read chooses the most recently
supplied occurrence, which may differ from the platform's edit chronology.

## 6. Record an explicit association decision

```bash
python -m keepmorrow associate ../collection-002 ../collection-003 \
  --conversation-key CONVERSATION_KEY --state standalone_confirmed \
  --reason "I confirm this conversation belongs outside a project." \
  --accept-terms 2026-11-12-draft.2 --accept-privacy 2026-11-12-draft.2
```

Use `project_confirmed` with `--project-id PROJECT_ID` to assign a project, or
`association_unknown` to record uncertainty. The decision history is separate
from source evidence. Its hash chain checks internal consistency, not the
identity or authority of the person entering the decision.

## 7. Recover selected material or the complete payload

```bash
python -m keepmorrow recover ../collection-003 ../selected-package \
  --conversation-key CONVERSATION_KEY \
  --accept-terms 2026-11-12-draft.2 --accept-privacy 2026-11-12-draft.2

python -m keepmorrow restore ../collection-003 ../complete-recovery \
  --accept-terms 2026-11-12-draft.2 --accept-privacy 2026-11-12-draft.2
```

Selected recovery can use repeated conversation keys or one confirmed
`--project-id`; an optional revision filter applies to one conversation. The
selected package contains derived conversation records and exact available bound
artifact bytes. It excludes whole original ZIPs, unrelated unassociated files,
and recognized whole conversation JSON documents. Such an export document
referenced as an attachment is labeled `excluded_by_selection`.

Arbitrary selected attachments are not internally redacted: a chosen ZIP, PDF, or
other binary can itself contain additional material. A selected package is not
a substitute for full originals, which remain in the parent collection.

Complete restore recovers every payload file, including full originals, into a
separate directory. Neither operation recreates native ChatGPT chats or projects.

## Validation and remaining work

See [collection verification](../engineering/collection-verification.md) for
observed tests and CI. Real export validation, broader attachment binding,
durable job resume, authenticated ChatGPT connection, hosted retention rules,
and legal approval remain explicit work. No source deletion or public release
is enabled by this workflow.
