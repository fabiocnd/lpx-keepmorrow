# LPX Keepmorrow

Preserve the AI work you choose to keep, organize its available evidence, and
recover it into ordinary files with verifiable integrity.

**Publisher and maintainer:** Lopix Neural Inc.
**Creator and lead developer:** Fabio de Sousa Lopes — Senior Software Engineer
**Contact:** [fabio@lopixneural.com](mailto:fabio@lopixneural.com)
**Source:** Private and proprietary · **Project language:** US English
**Product direction:** Free to use, with no monetization or advertising

## Current scope — version 0.2.0

This repository contains the project foundation: the retrieved Blueprint,
product requirements, architecture decisions, engineering and AI standards,
company/creator research, legal drafts, synthetic examples, and a local
preservation application with an experimental semantic import profile.

The application preserves explicitly selected directories or supported ZIPs,
including binary files and original ZIP containers. It builds a versioned
conversation catalog, keeps branch graphs and revisions, supports literal search,
records explicit association decisions, and recovers selected conversations with
available bound artifacts. A standalone HTML view accompanies every collection.
The original directory archive and complete file recovery commands remain available.

Current compatibility is **experimental**: the mapping profile is validated with
synthetic exports, not a representative real account export. Artifact binding
requires an explicit safe relative path; a filename or URI alone does not establish
that an image or binary has been supplied. Unknown fields remain in original files.

An optional, read-only MCP development adapter implements the protocol boundary
for a future ChatGPT connection. It is tested locally, bound to loopback, and
limited to developer-registered collection IDs. It is **not deployed, authenticated
for multiple users, or installed in ChatGPT**. Cloud storage, durable job resume,
model inference, direct account discovery, and native ChatGPT restoration remain
unimplemented.

## Start here

| Need | Document |
| --- | --- |
| Understand purpose and scope | [Product brief](docs/product/product-brief.md) |
| Inspect the complete documentation | [Documentation index](docs/README.md) |
| Review implemented behavior and limits | [Reference core](docs/architecture/reference-core.md) |
| Import exports, inspect revisions, and recover a selection | [Collection workflow](docs/architecture/collection-workflow.md) |
| Review supported input shapes and missing-media states | [Import contract](docs/architecture/import-contract.md) |
| Understand the ChatGPT integration boundary | [ChatGPT development adapter](docs/architecture/chatgpt-integration.md) |
| Plan the private ChatGPT pilot and later recovery workflow | [ChatGPT delivery plan](docs/architecture/chatgpt-delivery-plan.md) |
| Compare the product with official export | [Export comparison](docs/product/export-comparison.md) |
| Review legal terms and acceptance | [Legal drafts](legal/README.md) |
| Contribute or change code | [Contributing](CONTRIBUTING.md) and [Golden Coding Standard](docs/engineering/golden-coding-standard.md) |
| Review performance decisions | [Performance review](docs/engineering/performance-review.md) |
| See original evidence and coverage | [Source register](docs/provenance/source-register.md) |
| Follow remaining work | [Roadmap](docs/product/roadmap.md) |

## Run the local application

Use Python 3.11 or later. Local development validation runs on Linux; the
[collection verification record](docs/engineering/collection-verification.md)
records the actual Linux and Windows CI results and their limits. Other platforms
currently refuse archive creation and restoration. The local preservation core
has no third-party runtime dependencies. The optional ChatGPT development adapter
uses the separately pinned MCP SDK.

Read the [terms of use](legal/terms-of-use.md),
[privacy notice](legal/privacy-notice.md), and
[operation authorization](legal/consent-and-operation-authorization.md) first.
The following commands are for the repository's synthetic example and internal
review of draft version `2026-11-12-draft.2`.

```bash
export PYTHONPATH=src

python -m keepmorrow create examples/synthetic-input ../keepmorrow-demo-archive \
  --accept-terms 2026-11-12-draft.2 \
  --accept-privacy 2026-11-12-draft.2

python -m keepmorrow verify ../keepmorrow-demo-archive \
  --accept-terms 2026-11-12-draft.2 \
  --accept-privacy 2026-11-12-draft.2

python -m keepmorrow restore ../keepmorrow-demo-archive ../keepmorrow-demo-restore \
  --accept-terms 2026-11-12-draft.2 \
  --accept-privacy 2026-11-12-draft.2
```

In PowerShell, set `$env:PYTHONPATH = "src"` and place each command on one
line. Archive and restore destinations must not already exist. The CLI's
`--help` output describes the supported options.

Acceptance applies only to the named local operation. It does not authorize
source deletion, cloud transfer, model processing, public distribution, or
unlimited retention.

To build a conversation collection from explicitly selected exports:

```bash
python -m keepmorrow import ./export-first.zip ./export-second \
  --destination ../keepmorrow-collection --account-namespace my-local-account \
  --accept-terms 2026-11-12-draft.2 --accept-privacy 2026-11-12-draft.2

python -m keepmorrow catalog ../keepmorrow-collection \
  --accept-terms 2026-11-12-draft.2 --accept-privacy 2026-11-12-draft.2
```

Open `payload/index.html` inside the resulting archive for the standalone derived
view. Exit status `3` means the original bytes were preserved but semantic coverage
is partial or unsupported; inspect `payload/report.json`. Exit `0` does not assert
that every item in the source account was supplied. See the
[complete workflow](docs/architecture/collection-workflow.md) for revisions,
association decisions, and selected recovery.

## Validate

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests benchmarks
```

The [collection verification record](docs/engineering/collection-verification.md)
records local test results, inspected CI outcomes, and the measured synthetic workload.
See [validation](docs/engineering/validation.md) and
[performance policy](docs/engineering/performance-policy.md) for evidence
requirements. The GitHub Actions workflow is configured for Linux and Windows;
a remote run must be inspected before it can be reported as passing.

## Repository organization

| Path | Responsibility |
| --- | --- |
| `src/keepmorrow/` | Thin CLI, explicit consent boundary, and feature packages |
| `src/keepmorrow/archive/` | Deterministic manifests, bounded file operations, and verified publication |
| `src/keepmorrow/importers/` | Bounded ZIP intake and experimental ChatGPT source interpretation |
| `src/keepmorrow/catalog/` | Collection contracts, reconciliation, queries, associations, and readable views |
| `src/keepmorrow/formats/` | Shared pre-decode JSON resource boundary |
| `src/keepmorrow/integrations/chatgpt/` | Optional loopback MCP development adapter with explicit collection grants |
| `schemas/` | Versioned archive and collection contracts |
| `examples/` | Synthetic input and expected inventory |
| `tests/` | Unit and integration behavior |
| `benchmarks/` | Reproducible performance measurements |
| `docs/product/` | Product scope, requirements, roadmap, ideas |
| `docs/architecture/` | Boundaries, reference behavior, and decisions |
| `docs/engineering/` | Coding, performance, and validation standards |
| `docs/ai/` | Optional model-assistance policy and evaluation |
| `docs/governance/` | Identity, ownership, decisions |
| `docs/provenance/` | Preserved source snapshots and coverage |
| `docs/research/` | Public research with source qualifications |
| `legal/` | Draft terms, privacy, and operation authorization |
| `.github/` | CI and review configuration |

This grouping is explained in [ADR 0001](docs/architecture/decisions/0001-repository-layout.md).
Source archives and restored user data belong outside the repository. Only
synthetic demonstration data is committed.

## Ownership and release status

Copyright (c) 2026 Lopix Neural Inc. All rights reserved. See [LICENSE](LICENSE)
and [NOTICE](NOTICE).

A free product does not make this source repository open source. The current
repository is for private development. Legal documents are drafts for owner
and qualified legal review; they are not an approved public contract.
No hosting, model provider, or public launch is implied.

The [0.2.0 verification record](docs/engineering/collection-verification.md)
separates local tests, remote CI, benchmark evidence, and outstanding integration work.

This repository records the materials actually retrieved and the foundation
created from them. It does not claim to contain every historical chat, unavailable
attachment, or unprovided project asset.
