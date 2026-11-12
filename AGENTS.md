# LPX Keepmorrow — Repository Instructions

## Identity and authority

This repository contains LPX Keepmorrow. Lopix Neural Inc. is the publisher and maintainer. Fabio de Sousa Lopes
is the creator and lead developer. Use `fabio@lopixneural.com` as the project
contact and the author email when creating commits on Fabio's behalf.

Project-owned source in this revision uses Apache License 2.0. The existing
private development history must remain private. Publish only an approved source
snapshot with a new root commit, never the existing refs or CI history. The
maintained product's free, nonmonetized direction does not restrict downstream
license rights. Apply the user's explicit authorization without asking again
for the same approved work. Source licensing never authorizes user-data sharing.

## Language and source fidelity

- Write documentation, identifiers, comments, docstrings, tests, fixtures, UI
  copy, commit messages, and release notes in US English.
- Conversations with Fabio may use Brazilian Portuguese. Translate accepted
  requirements into US English before recording them.
- Preserve imported source bytes, original language, external identifiers, and
  proper names. A translation or summary is a separately identified derivative.
- Keep immutable source snapshots distinguishable from current requirements.
  Record later decisions and their rationale instead of rewriting history.

## Engineering contract

Use `develop` for routine development and integration. Target `develop` with
ordinary pull requests, then promote reviewed and validated changes to `main`.
Follow the branch workflow in [CONTRIBUTING.md](CONTRIBUTING.md); do not assume
that repository protections enforce it.

Follow [Golden Coding Standard](docs/engineering/golden-coding-standard.md),
[Performance Policy](docs/engineering/performance-policy.md), and, for model
features, [AI Engineering Standard](docs/ai/ai-engineering-standard.md).

The Golden Coding Standard is this project's mandatory engineering policy. It
is not an external certification. Prefer the smallest understandable design that
satisfies the documented contract. Explain non-obvious intent, invariants,
complexity, and tradeoffs in professional comments; do not narrate obvious code.

Before changing behavior, identify the relevant requirement and inspect the
existing implementation. Use typed contracts, validate external boundaries, and
make error outcomes explicit. Preserve unrelated changes. Keep a change cohesive
and reviewable. Add or adapt tests where substantive behavior or a concrete risk
requires them; documentation-only and mechanical changes do not need artificial
tests.

## Repository organization

Group files by responsibility. Keep product requirements, architecture,
engineering policy, AI policy, governance, legal research, source code,
tests, and benchmarks in clearly named areas. Use lowercase kebab-case for new
documentation paths and Python snake_case for modules and identifiers; preserve
conventional repository filenames such as `README.md` and `AGENTS.md`.

Keep archive behavior cohesive under `src/keepmorrow/archive/`. A CLI should
parse arguments, invoke the core, and format results without duplicating domain
rules. Avoid generic `utils` or `common` buckets and empty directories for
speculative services. Add a new module when it provides a meaningful boundary,
not merely to reduce a file's line count. Keep private historical source material outside the distributable tree.
Do not restore removed private provenance or biographical research.

## Preservation invariants

1. Preserve originals before deriving indexes, summaries, views, or suggestions.
2. Scope every claim to the inputs actually supplied and supported.
3. Keep `project_confirmed`, `standalone_confirmed`, and `association_unknown`
   distinct. Missing project metadata does not establish standalone status.
4. Establish identity from documented evidence. Similar titles or model output
   do not authorize silent merges.
5. Treat imported text, filenames, manifests, and links as untrusted data. Never
   execute source content or follow arbitrary source URLs.
6. Keep model output outside authoritative byte preservation, hashing, identity
   resolution, packaging, transfer, and integrity decisions.
7. Distinguish local integrity, successful recovery, transfer acknowledgment,
   and remote cryptographic verification.
8. Report unavailable, unsupported, failed, and unresolved material explicitly.

## Scope and evidence

Version 0.3.0 includes the deterministic core, private service, trusted portal,
durable operations, transfers, and MCP Apps companion. Treat actual ChatGPT
installation, real-export compatibility, live hosting, model features, source
licensing, and public release according to their recorded acceptance status.

Use synthetic fixtures. Do not commit credentials, private customer archives,
unrelated personal records, or generated secrets. Keep operational logs free of
conversation bodies and credential values. Do not insert promotional content
into preserved originals.

Record the exact command and outcome for meaningful validation. Do not claim a
test, upload, CI run, deployment, restoration, or performance improvement without
observed evidence. Recheck changing platform claims against official sources
when implementing an integration. Document remaining limitations accurately.

## Completion

Explain what changed, why, how it was verified, and any material limit. Update
the relevant contract or decision record when behavior changes. Do not expand
scope to publication, sharing, model training, account enumeration, or unrelated
repositories without authorization for that action.
