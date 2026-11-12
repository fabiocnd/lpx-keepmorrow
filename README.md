# LPX Keepmorrow

LPX Keepmorrow turns explicitly supplied ChatGPT exports into a verifiable,
searchable collection of conversations, revisions, branches, and available files.
It preserves the original input, records what could and could not be interpreted,
and lets you recover the complete payload or a selected part into ordinary files.

**Publisher and maintainer:** Lopix Neural Inc.
**Creator and lead developer:** Fabio de Sousa Lopes — Senior Software Engineer
**Contact:** [fabio@lopixneural.com](mailto:fabio@lopixneural.com)
**Source:** Currently private and proprietary; [open-source transition planned](docs/governance/open-source-transition.md), with release license pending · **Project language:** US English
**Product direction:** Free to use, with no monetization or advertising

## What the project does

Start with an export ZIP or directory that you already downloaded and are
authorized to process. Keepmorrow provides a preservation workflow around that
material:

1. **Preserve the supplied originals.** Retain exact file bytes and the original
   ZIP container. Record paths, sizes, and SHA-256 digests in a verifiable manifest.
2. **Build a useful collection.** Interpret the supported conversation format,
   retaining source identity, message branches, revisions, and capture provenance.
   Keep unsupported records in the originals and report the interpretation gaps.
3. **Keep repeated exports understandable.** Reconcile records using source IDs
   within an explicit account namespace. Preserve each capture and distinct
   revision; a renamed title does not create a new conversation by itself.
4. **Organize with evidence.** Distinguish confirmed project membership,
   confirmed standalone conversations, and unknown associations. Record reviewed
   corrections separately without modifying the original source.
5. **Inspect and recover.** Browse, search, read revisions, verify integrity, and
   recover selected conversations with their available, explicitly bound files.
   The private service can package a verified collection for authorized download.
6. **Control each processing scope.** The private portal records explicit human
   acceptance, exact generation permissions, and reviewed operation plans before
   admission. Revocation stops future authorized access and delivery.

For example, you can keep two exports taken at different times, inspect the
revisions of a conversation that was renamed between them, and recover one
conversation with a supplied image and code file. An attachment is included in
that selection only when the supported metadata binds it to actual preserved
bytes. Missing bytes remain an explicit gap.

## How this differs from ChatGPT's native export

ChatGPT prepares the account export through its supported export process. [1]
Keepmorrow works with the ZIP or directory you explicitly choose to supply
afterward. It adds capture provenance, conversation revisions, integrity checks,
reviewed association decisions, and selective recovery across repeated exports.

This is useful when a project evolves through renamed conversations, alternative
branches, and changing files. For an occasional downloaded copy, native export
and ordinary backup storage may already meet your needs. Keepmorrow's purpose is
to make ongoing preservation and selected recovery easier to inspect and verify.

**Images and binaries:** Keepmorrow preserves supplied regular files regardless
of extension. OpenAI's Edu export documentation describes files and conversation
assets, but the actual inventory must be checked for each supplied package. [2]
A URL, thumbnail, or filename does not establish that the original binary is
present. Keepmorrow cannot recover absent bytes from a broken link or regenerate
a missing original. Selected attachments are copied intact; their internal
contents are not automatically redacted.

Recovery creates ordinary files and portable collections. It does not recreate
native ChatGPT chats, Projects, account settings, or the sidebar. OpenAI also
explains that uploading exported conversation JSON as reference does not recreate
the original separate conversations. [3]

The current parser is experimental and has been tested with synthetic exports.
A representative authorized real export is still required before claiming
real-account compatibility. The ChatGPT-facing service and UI are implemented,
but an actual ChatGPT connection has not been demonstrated. See the detailed
[export comparison](docs/product/export-comparison.md) and
[validation record](docs/engineering/private-pilot-validation.md).

Official sources reviewed November 12, 2026:

- [1 — OpenAI: Exporting your ChatGPT history and data](https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data)
- [2 — OpenAI: Exporting data from a ChatGPT Edu workspace](https://help.openai.com/en/articles/20001279-exporting-data-from-a-chatgpt-edu-workspace)
- [3 — OpenAI: Transfer exported conversations between ChatGPT accounts](https://help.openai.com/en/articles/9106926-transfer-exported-conversations-between-chatgpt-accounts)

## Current scope — version 0.3.0

This repository contains the preservation application, current product requirements,
architecture decisions, engineering and AI standards, draft processing policies,
synthetic examples, and reproducible validation tools. Private development
conversations, personal research, and operational user data are excluded from the
current distributable source tree.

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

The private service adds an external OAuth resource-server boundary, a trusted
human consent portal, per-generation grants, durable reviewed operations,
cooperative cancellation, crash reconciliation, bounded uploads, and portable
recovery ZIPs. A TypeScript MCP Apps companion presents explicit content reads
and operation status. The original local CLI remains independently usable.

**Implementation is not deployment evidence.** Synthetic tests exercise two
identities, the actual HTTP/MCP boundary, operation interruption, and byte-exact
package recovery. A real ChatGPT account connection, selected live identity
provider and host, representative real export, and deployed portal/browser
qualification remain open gates. The companion has passed synthetic Chromium
tests and desktop/narrow screenshot review. Account-wide discovery, native ChatGPT restoration, model
inference, and model training are not implemented.

## Start here

| Need | Document |
| --- | --- |
| Understand purpose and scope | [Product brief](docs/product/product-brief.md) |
| Inspect the complete documentation | [Documentation index](docs/README.md) |
| Review implemented behavior and limits | [Reference core](docs/architecture/reference-core.md) |
| Import exports, inspect revisions, and recover a selection | [Collection workflow](docs/architecture/collection-workflow.md) |
| Review supported input shapes and missing-media states | [Import contract](docs/architecture/import-contract.md) |
| Run the private service and understand its limits | [Private service runbook](docs/operations/private-service-runbook.md) |
| Review identity and trusted human decisions | [External authentication](docs/architecture/external-authentication.md) and [trusted portal](docs/architecture/trusted-portal.md) |
| Review executed integration evidence | [Private pilot validation](docs/engineering/private-pilot-validation.md) |
| Use the legacy synthetic adapter | [ChatGPT development adapter](docs/architecture/chatgpt-integration.md) |
| Review delivery progress and external acceptance gates | [ChatGPT delivery plan](docs/architecture/chatgpt-delivery-plan.md) |
| Compare the product with official export | [Export comparison](docs/product/export-comparison.md) |
| Review legal terms and acceptance | [Legal drafts](legal/README.md) |
| Contribute or change code | [Contributing](CONTRIBUTING.md) and [Golden Coding Standard](docs/engineering/golden-coding-standard.md) |
| Review performance decisions | [Performance review](docs/engineering/performance-review.md) |
| Review distribution and privacy preparation | [Open-source transition](docs/governance/open-source-transition.md) |
| Follow remaining work | [Roadmap](docs/product/roadmap.md) |

## Run the local application

Use Python 3.11 or later. Local development validation runs on Linux; the
[private pilot validation record](docs/engineering/private-pilot-validation.md)
records the actual Linux and Windows CI results and their limits. Other platforms
currently refuse archive creation and restoration. The local preservation core
has no third-party runtime dependencies. The optional private service uses separately pinned MCP, HTTP, and JWT
dependencies. The TypeScript companion has its own reproducible package lock.

Read the [terms of use](legal/terms-of-use.md),
[privacy notice](legal/privacy-notice.md), and
[operation authorization](legal/consent-and-operation-authorization.md) first.
The following commands are for the repository's synthetic example and internal
review of draft version `2026-11-12-draft.3`.

```bash
export PYTHONPATH=src

python -m keepmorrow create examples/synthetic-input ../keepmorrow-demo-archive \
  --accept-terms 2026-11-12-draft.3 \
  --accept-privacy 2026-11-12-draft.3

python -m keepmorrow verify ../keepmorrow-demo-archive \
  --accept-terms 2026-11-12-draft.3 \
  --accept-privacy 2026-11-12-draft.3

python -m keepmorrow restore ../keepmorrow-demo-archive ../keepmorrow-demo-restore \
  --accept-terms 2026-11-12-draft.3 \
  --accept-privacy 2026-11-12-draft.3
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
  --accept-terms 2026-11-12-draft.3 --accept-privacy 2026-11-12-draft.3

python -m keepmorrow catalog ../keepmorrow-collection \
  --accept-terms 2026-11-12-draft.3 --accept-privacy 2026-11-12-draft.3
```

Open `payload/index.html` inside the resulting archive for the standalone derived
view. Exit status `3` means the original bytes were preserved but semantic coverage
is partial or unsupported; inspect `payload/report.json`. Exit `0` does not assert
that every item in the source account was supplied. See the
[complete workflow](docs/architecture/collection-workflow.md) for revisions,
association decisions, and selected recovery.

## Run the private portal

Install the optional service dependencies in your project environment:

```bash
python -m pip install -c requirements/chatgpt-dev-py312.constraints.txt '.[chatgpt]'
python -m keepmorrow.application.cli init /absolute/path/to/new-service --operator local-owner
python -m keepmorrow.application.cli check --configuration /absolute/path/to/new-service/service.json
python -m keepmorrow.application.cli serve --configuration /absolute/path/to/new-service/service.json
```

Replace the absolute example path with a new directory you control. Initialization
creates an empty local workspace and an owner-only `operator.key` file. It never
prints the key or inspects source files. Open `http://127.0.0.1:8765` on the same
machine and enter the key only in that portal. Sign-in, scope acceptance, selected
upload, and exact operation review are distinct steps. No consent checkbox is
preselected, and MCP tools cannot approve these decisions for the user.

Local operator mode has **no MCP endpoint**. OAuth mode requires explicit issuer,
resource audience, JWKS, browser-client registration, and allowlisted identities.
Both modes listen on loopback. Hosting or a private tunnel must preserve the
configured authentication boundary; changing the listen address is not a
production deployment. See [deployment examples](deploy/README.md).

A completed import or recovery creates a new immutable generation. Accept that
generation's scope before querying it. Preparing a portable package is a separate
reviewed operation; its exact generation requires download consent. ZIP packages
have independently enforced encoded and expanded byte limits and are verified
again when unpacked. No operation deletes or overwrites source data.

To rebuild packaged UI and policy assets from their canonical source:

```bash
npm --prefix ui/chatgpt ci --ignore-scripts
npm --prefix ui/chatgpt run build
python scripts/build_policy_assets.py
```

## Validate

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests benchmarks
npm --prefix ui/chatgpt test
```

The [private pilot validation record](docs/engineering/private-pilot-validation.md)
records current test results, inspected CI outcomes, and the measured synthetic workload.
The [synthetic HTTP pilot](docs/operations/private-service-runbook.md#reproduce-the-synthetic-http-pilot)
starts a Linux child service and verifies the portal workflow over an actual
loopback socket using only generated fixtures. It records no actual human
acceptance and does not establish OAuth or a ChatGPT account connection.
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
| `src/keepmorrow/access/` | Principal identity, exact scopes, policy acceptance, and revocation |
| `src/keepmorrow/persistence/` | Private SQLite transactions and component schemas |
| `src/keepmorrow/operations/` | Immutable plans, trusted reviews, idempotent admission, worker fencing, and recovery |
| `src/keepmorrow/transfers/` | Owned upload staging and portable byte-preserving packages |
| `src/keepmorrow/application/` | Configuration, generation registry, service coordination, owned scratch, and setup CLI |
| `src/keepmorrow/integrations/chatgpt/` | OAuth/MCP boundary, trusted portal, streaming HTTP, and packaged UI assets |
| `ui/chatgpt/` | Typed MCP Apps component, reproducible build, interaction and protocol tests |
| `deploy/` | Explicit private deployment examples; no live environment implied |
| `schemas/` | Versioned archive and collection contracts |
| `examples/` | Synthetic input and expected inventory |
| `tests/` | Unit and integration behavior |
| `benchmarks/` | Reproducible performance measurements |
| `docs/product/` | Product scope, requirements, roadmap, ideas |
| `docs/architecture/` | Boundaries, reference behavior, and decisions |
| `docs/engineering/` | Coding, performance, and validation standards |
| `docs/operations/` | Startup, retention, recovery, backup, and incident procedures |
| `docs/ai/` | Optional model-assistance policy and evaluation |
| `docs/governance/` | Identity, ownership, decisions |
| `docs/research/` | Public research with source qualifications |
| `legal/` | Draft terms, privacy, and operation authorization |
| `.github/` | CI and review configuration |

This grouping is explained in [ADR 0001](docs/architecture/decisions/0001-repository-layout.md)
and the [private service decision](docs/architecture/decisions/0003-private-preservation-service.md).
Source archives and restored user data belong outside the repository. Only
synthetic demonstration data is committed.

## Ownership and release status

Copyright (c) 2026 Lopix Neural Inc. All rights reserved. See [LICENSE](LICENSE)
and [NOTICE](NOTICE).

The owner intends an [open-source transition](docs/governance/open-source-transition.md).
The exact release license and publication decision remain pending; the current
proprietary license and private visibility continue to apply. The transition
includes reviewing material suitable for public distribution and excluding
private development records or user data. Legal documents remain drafts for
owner and qualified legal review. No hosting, model provider, or public launch
is implied by the planned license change.

The [private pilot validation record](docs/engineering/private-pilot-validation.md)
separates implementation, synthetic verification, remote CI, measured workloads,
and the remaining live account, export, identity-provider, browser, and legal gates.

A reviewed source archive excludes Git history and local operational state.
Earlier private commits remain in the development repository; changing its
visibility would require a separate history and artifact review. The recommended
public-release path starts from the sanitized source snapshot after license adoption.
