# Delivery Roadmap

## Foundation — current work

- [x] Consolidate the retrieved Blueprint and owner instructions.
- [x] Establish canonical names, ownership, contact, and proprietary source policy.
- [x] Organize documentation and code by responsibility.
- [x] Define engineering, performance, and AI standards.
- [x] Verify private GitHub repository creation and the remote source commit.
- [x] Complete reference-core and consent-boundary validation (42 local tests passed).
- [x] Verify the Linux and Windows CI matrix with Python 3.11 and 3.14.
- [x] Record initial benchmark methodology and measured results.
- [ ] Obtain qualified legal review before public use of the draft terms.

## Milestone 1 — preservation contract

Select one supported source format using an authorized representative sample.
Define the semantic catalog schema, source identifiers, revision rules,
association evidence, unknown-field behavior, and missing-artifact statuses.

**Exit evidence:** All synthetic scenarios have explicit expected results;
unsupported records cannot disappear silently.

## Milestone 2 — usable local archive

Implement import, branch-aware conversation records, stable identity, readable
views, catalog browsing, basic search, and manifests. Keep canonical originals
separate from derived records and optional AI output.

**Exit evidence:** Repeated capture and renamed-conversation scenarios preserve
identity without merging ambiguous records.

## Milestone 3 — recovery and operational resilience

Add durable jobs, cancellation, restart behavior, large-corpus validation,
resource budgets, and fault injection. Test restored archives in a different
location and supported operating systems.

**Exit evidence:** Recovery reconciles the inventory and detects tampering;
partial work is distinguishable from success.

## Milestone 4 — one storage provider

Select a provider, obtain explicit destination authorization, specify ownership
and retention, and implement bounded retries and resumability. Distinguish
receipt acknowledgment from remote integrity verification.

Google Drive remains a candidate. No provider is selected or integrated.

## Milestone 5 — ChatGPT interface

Review the supported platform capabilities and current distribution rules.
Expose the core's verified operations and status. Provide user-controlled
association review and versioned consent.

**Exit evidence:** The interface cannot imply broader account access or
stronger integrity guarantees than the backend provides.

## Milestone 6 — public release decision

Finalize terms, privacy, support limits, retention, operating costs, deployment
security, and release claims. Decide licensing of distributed binaries and
services separately from this private source repository.

**Exit evidence:** Fabio approves the release scope after engineering and legal
review. No public launch is authorized by the repository setup alone.

## Deliberately deferred

Model selection, embeddings, vector databases, cloud orchestration, native
extensions, parallel workers, and a public distribution channel remain deferred
until a measured requirement justifies them.
