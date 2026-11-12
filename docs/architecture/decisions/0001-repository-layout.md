# ADR 0001 — Organize by Responsibility and Feature

**Date:** 2026-11-12  
**Status:** Adopted for the repository foundation  
**Basis:** Cohesive responsibility boundaries and measurable performance engineering.

## Context

The project combines product direction, source evidence, engineering rules,
legal obligations, deterministic preservation, and future model-assisted
features. Mixing these in generic folders obscures which documents describe
requirements, which record history, and which modules perform trusted work.

## Decision

Use one repository with a small Python package. Group documentation by its
purpose and code by cohesive behavior. Keep a thin command-line entry point
outside the archive implementation. Add the consent boundary as an explicit
component. Create future parser, storage, and model modules only when behavior
requires them.

| Location | Responsibility |
| --- | --- |
| `docs/product/` | Product brief, requirements, roadmap, ideas, naming |
| `docs/architecture/` | System boundaries, reference-core contract, architecture decisions |
| `docs/engineering/` | Coding, validation, and performance policies |
| `docs/ai/` | Model-assistance boundaries and evaluation plans |
| `docs/governance/` | Identity, ownership, decisions, operating policies |
| `docs/research/` | Source-backed findings and verification limits |
| `legal/` | Draft terms, privacy notice, acceptance and operation authorization |
| `src/keepmorrow/archive/` | Deterministic manifest and snapshot behavior |
| `src/keepmorrow/` | Package entry points and explicit consent boundary |
| `schemas/` | Versioned machine-readable contracts |
| `examples/` | Clearly synthetic demonstration material |
| `tests/` | Unit and end-to-end behavioral validation |
| `benchmarks/` | Reproducible workload and measurement tools |
| `.github/` | CI and review configuration |

## Naming rules

Documentation and non-Python project paths use lowercase kebab-case. Python
modules use snake_case. Prefer a short, specific name to layer slogans or
generic containers. Conventional root filenames retain their standard spelling.

Do not use mutable titles as identities. A physical source path records
location, not a confirmed project relationship. Keep archived source data
separate from repository source code and synthetic test fixtures.

## Performance consequences

Folder naming has no claimed runtime speed benefit. Cohesive boundaries make
it easier to profile a real operation, isolate storage costs, enforce resource
limits, and optimize a hotspot without changing unrelated behavior.

The current service remains a single process. [ADR 0003](0003-private-preservation-service.md)
adds a bounded worker and transactional SQLite for concrete consent/publication
requirements. Distributed workers and separate services still require measured
evidence and a new coordination contract.

## Tradeoffs

Several documentation groups create more directories than one flat folder,
but each has a distinct reader and responsibility. The index supplies a single
entry point. We deliberately avoid empty future-service scaffolding and duplicate
canonical documents.

## Version 0.3.0 extension

The implemented service adds `access`, `persistence`, `operations`, `transfers`,
and `application` packages, a typed UI under `ui/chatgpt/`, deployment examples
under `deploy/`, and operational guidance under `docs/operations/`. These groups
contain working behavior and tests. Private development records are excluded
from the distributable source tree; technical test evidence remains versioned.
