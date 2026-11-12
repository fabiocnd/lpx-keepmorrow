# ADR 0001 — Organize by Responsibility and Feature

**Date:** 2026-11-12  
**Status:** Adopted for the repository foundation  
**Basis:** Owner's explicit request for better naming, grouping, and performance-oriented engineering.

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
| `docs/provenance/` | Historical source snapshots and coverage |
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

A single process is the initial deployment. Parallelism, queues, databases,
and separate services need measured evidence and a migration decision.

## Tradeoffs

Several documentation groups create more directories than one flat folder,
but each has a distinct reader and responsibility. The index supplies a single
entry point. We deliberately avoid empty future-service scaffolding and duplicate
canonical documents.
