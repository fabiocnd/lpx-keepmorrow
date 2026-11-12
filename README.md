# LPX Keepmorrow

Preserve the AI work you choose to keep, organize its available evidence, and
recover it into ordinary files with verifiable integrity.

**Publisher and maintainer:** Lopix Neural Inc.  
**Creator and lead developer:** Fabio de Sousa Lopes — Senior Software Engineer  
**Contact:** [fabio@lopixneural.com](mailto:fabio@lopixneural.com)  
**Source:** Private and proprietary · **Project language:** US English  
**Product direction:** Free to use, with no monetization or advertising

## Current scope

This repository contains the project foundation: the retrieved Blueprint,
product requirements, architecture decisions, engineering and AI standards,
company/creator research, legal drafts, synthetic examples, and a small local
reference preservation engine.

The reference engine creates a directory archive from explicitly selected local
files, verifies its inventory and SHA-256 hashes, and restores into a separate
new destination. The command-line boundary requires explicit acceptance of the
current draft terms and privacy notice before processing.

Semantic ChatGPT export parsing, conversation search, revision catalogs,
resumable jobs, cloud transfer, model providers, and a ChatGPT interface remain
planned. The synthetic conversation catalog is currently preserved as bytes;
it is not interpreted as a complete product catalog.

## Start here

| Need | Document |
| --- | --- |
| Understand purpose and scope | [Product brief](docs/product/product-brief.md) |
| Inspect the complete documentation | [Documentation index](docs/README.md) |
| Review implemented behavior and limits | [Reference core](docs/architecture/reference-core.md) |
| Review legal terms and acceptance | [Legal drafts](legal/README.md) |
| Contribute or change code | [Contributing](CONTRIBUTING.md) and [Golden Coding Standard](docs/engineering/golden-coding-standard.md) |
| Review performance decisions | [Performance review](docs/engineering/performance-review.md) |
| See original evidence and coverage | [Source register](docs/provenance/source-register.md) |
| Follow remaining work | [Roadmap](docs/product/roadmap.md) |

## Run the reference core

Use Python 3.11 or later. Local development validation runs on Linux; the
[foundation verification record](docs/engineering/foundation-verification.md)
records the actual Linux and Windows CI results and their limits. Other platforms
currently refuse archive creation and restoration. There are no third-party
runtime dependencies.

Read the [terms of use](legal/terms-of-use.md),
[privacy notice](legal/privacy-notice.md), and
[operation authorization](legal/consent-and-operation-authorization.md) first.
The following commands are for the repository's synthetic example and internal
review of draft version `2026-11-12-draft.1`.

```bash
export PYTHONPATH=src

python -m keepmorrow create examples/synthetic-input ../keepmorrow-demo-archive \
  --accept-terms 2026-11-12-draft.1 \
  --accept-privacy 2026-11-12-draft.1

python -m keepmorrow verify ../keepmorrow-demo-archive \
  --accept-terms 2026-11-12-draft.1 \
  --accept-privacy 2026-11-12-draft.1

python -m keepmorrow restore ../keepmorrow-demo-archive ../keepmorrow-demo-restore \
  --accept-terms 2026-11-12-draft.1 \
  --accept-privacy 2026-11-12-draft.1
```

In PowerShell, set `$env:PYTHONPATH = "src"` and place each command on one
line. Archive and restore destinations must not already exist. The CLI's
`--help` output describes the supported options.

Acceptance applies only to the named local operation. It does not authorize
source deletion, cloud transfer, model processing, public distribution, or
unlimited retention.

## Validate

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests benchmarks
```

The [foundation verification record](docs/engineering/foundation-verification.md)
records local test results, inspected CI outcomes, and the measured synthetic workload.
See [validation](docs/engineering/validation.md) and
[performance policy](docs/engineering/performance-policy.md) for evidence
requirements. The GitHub Actions workflow is configured for Linux and Windows;
a remote run must be inspected before it can be reported as passing.

## Repository organization

| Path | Responsibility |
| --- | --- |
| `src/keepmorrow/` | CLI, explicit consent boundary, and deterministic archive engine |
| `schemas/` | Versioned machine-readable archive contract |
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

This repository records the materials actually retrieved and the foundation
created from them. It does not claim to contain every historical chat, unavailable
attachment, or unprovided project asset.
