# Golden Coding Standard

**Owner:** Lopix Neural Inc.

**Engineering lead:** Fabio de Sousa Lopes

**Contact:** fabio@lopixneural.com

**Effective date:** 2026-11-12

**Status:** Mandatory project engineering policy

The Golden Coding Standard is LPX Keepmorrow's own definition of acceptable
engineering work. It is not a third-party standard, certification, or claim of
production readiness. Its purpose is reliable behavior that an experienced
engineer can understand, measure, reproduce, and maintain.

`MUST` identifies a required property for applicable work. `SHOULD` identifies a
default that may be changed with a documented technical reason. A policy
requirement does not mean an automated check for that requirement exists.

## 1. Correctness begins with a contract

Every substantive change MUST identify its expected behavior, inputs, outputs,
failure outcomes, and relevant invariants. A callable public boundary MUST use
explicit types. Types document a contract; external data still requires runtime
validation.

Validate data at the boundary where it becomes trusted. Check structure,
versions, required fields, value ranges, sizes, duplicate identities, and
cross-field constraints as applicable. Avoid repeatedly validating the same
unchanged internal value when that adds cost without establishing a new trust
boundary.

Empty, absent, unknown, malformed, unsupported, and failed are different states.
Do not collapse them into a successful empty result. Errors MUST provide enough
context for recovery without unnecessarily exposing source content or secrets.
Catch exceptions only where the code can add useful context, perform cleanup,
or select a documented recovery path. Do not silently suppress failures.

## 2. Preserve evidence before deriving meaning

Original source bytes MUST remain distinguishable from normalized records,
views, translations, summaries, and model suggestions. A derived representation
MUST NOT replace a missing original or claim information absent from the source.

Identity resolution MUST follow documented evidence. A stable source identifier
requires a namespace; a title is not an identity. Deduplication of byte content
does not prove that two conversations are the same logical object. Corrections
and later captures MUST retain the provenance needed to explain their history.

Each operation MUST report its actual input scope. A successful supported import
does not demonstrate that every conversation or artifact in an account exists
in the archive. Keep association uncertainty explicit.

## 3. Favor understandable structure

Separate domain rules from filesystem, network, user-interface, and model
adapters. Components SHOULD own one clear responsibility and expose the minimum
contract needed by callers. Prefer explicit data flow and dependency injection
at replaceable boundaries over hidden global state.

Use immutable values where they simplify ownership or prevent accidental
mutation. Avoid generic frameworks, inheritance layers, caches, and concurrency
that do not solve a current requirement. The size of an abstraction should
follow demonstrated variation, not hypothetical reuse.

Name values by their domain meaning and units: `size_bytes`, `duration_seconds`,
and `retry_count` are clearer than ambiguous quantities. Use US English in all
authored project content. Preserve source-defined keys when compatibility
requires exact spelling.

Organize paths by responsibility. Use product, architecture, engineering,
operations, AI, governance, and research documentation areas with a concise README
map. Use lowercase kebab-case for documentation paths and snake_case for Python
modules and identifiers. Conventional files such as `README.md` keep their
established names.

Archive modules belong together under `src/keepmorrow/archive/`. Keep the CLI
thin: argument parsing, application invocation, and result formatting. Core
rules must remain usable without the CLI. Place behavioral tests near their
subject in the test hierarchy, and reproducible performance workloads under
`benchmarks/`. Do not create empty future services or broad
`utils` and `common` containers that hide ownership. A new module must create a
useful responsibility boundary rather than satisfy an arbitrary line count.

## 4. Determinism and explicit side effects

Given the same declared inputs and configuration, deterministic core operations
MUST produce the same semantic result. Define ordering where order affects
serialization, hashing, identity, or user-visible output. Timestamps, random
identifiers, environment settings, and provider responses MUST be explicit
inputs or documented sources of variation.

Separate calculation from mutation where doing so makes failures observable.
Writers MUST define overwrite policy, commit boundaries, cleanup behavior, and
what remains after interruption. Do not describe an operation as atomic or
durable without a precise supported scope. Idempotency MUST define the key,
destination, and outcome of a repeated or conflicting request.

Retries require a bounded count or time budget and a classification of retryable
failures. Cancellation and partial completion MUST remain distinct from success.
Do not invent resumability where the current implementation safely restarts.

When publication depends on revocable authorization, define the serialized
decision boundary and retain attempt ownership through publication and cleanup.
Human acceptance and plan-review records MUST originate in the documented
trusted interaction boundary. A model-supplied assertion is not that record.

## 5. Performance is an engineering result

Choose algorithms and data structures for the expected workload, including
adversarial inputs at supported boundaries. State complexity for nontrivial
algorithms and name the relevant variables. Discuss storage and metadata costs
as well as the main loop.

Large content SHOULD be processed incrementally with bounded buffers. Avoid
whole-file copies solely to calculate a digest or transfer bytes. A bounded
payload buffer does not imply constant total memory when the catalog still
holds one record per file. Document both costs.

Concurrency requires bounded queues and workers, clear ownership, cancellation,
and deterministic reconciliation. A parallel implementation MUST justify its
coordination and I/O cost with evidence relevant to the supported workload.

Follow the [Performance Policy](performance-policy.md). Do not describe code as
faster, optimal, scalable, or production-grade on the strength of style alone.

## 6. Comments and docstrings

Comments MUST be technically precise, professional, and proportional to the
decision being explained. Explain intent, invariants, non-obvious constraints,
failure semantics, algorithmic tradeoffs, or compatibility requirements. Avoid
comments that merely translate the next line into English.

Public APIs SHOULD document behavior that callers cannot infer reliably from
names and types: mutation, ownership, ordering, exceptions, resource limits, and
applicable complexity. A small internal helper may need only a clear name.

Useful examples:

```python
# Hash and copy the same stream so the recorded digest describes the bytes
# written, rather than a separate read that could observe a changed file.

# Preserve unknown associations; missing project metadata is not evidence
# that the conversation was created outside a project.
```

Review comments when behavior changes. Do not leave aspirational guarantees in
comments when the implementation does not establish them. Explain an unusual
optimization and its measured reason near the relevant code or linked decision.

## 7. Tests must challenge behavior

Tests MUST assert externally meaningful properties and failures, rather than
mirror implementation details. Cover substantive changed behavior, known
regressions, boundary conditions, and concrete risks. Use deterministic synthetic
fixtures and isolated temporary destinations.

For preservation work, useful checks include byte equality, manifest inventory
reconciliation, corruption detection, safe path rejection, explicit unknown
associations, duplicate handling, and safe failure before overwriting a target.
Test interruption, cancellation, and remote behavior when those features exist.

Keep test requirements proportionate. Do not add artificial tests for spelling
edits or mirror a constant merely to raise coverage. Coverage can locate gaps;
it does not establish correctness. Avoid network dependencies in core tests.

Record exact commands, relevant runtime versions, outcomes, and material skips.
Never claim broader platform or workload support than the executed evidence.

## 8. Dependency and interface discipline

Prefer the standard library where it satisfies the requirement clearly and
correctly. A new dependency MUST have a documented purpose, maintenance rationale,
license assessment, and reproducible version strategy. Do not copy third-party
code, assets, or model weights without recording their source and applicable
terms.

Version persistent schemas and public contracts. Specify how unknown versions
are handled; do not silently reinterpret incompatible data. Migrations MUST
preserve a recoverable original and document any information loss.

Before implementing a changing platform integration, check official
documentation and record the review date. A remembered capability is not
evidence of current account permissions or distribution approval.

## 9. Security and privacy are behavior requirements

Treat imported files, archive metadata, conversation text, and embedded links as
untrusted input. Validate paths and resource limits at the boundary. Do not
execute source content, follow arbitrary URLs, or let model-generated text
determine operational permissions.

Operational telemetry SHOULD contain identifiers, counts, timings, and error
categories, with the minimum data needed for diagnosis. Conversation bodies,
credentials, and unnecessary personal data MUST stay out of logs and fixtures.
Document the processing and retention of each external integration before
enabling it, including the deployed behavior of an existing reference adapter.
Follow [SECURITY.md](../../SECURITY.md).

## 10. Review and completion

A completed substantive change MUST have a coherent diff, a clear requirement,
appropriate validation, current documentation, and an honest limitation
statement. Explain why the change is needed and the resulting behavior before
listing implementation details.

The repository may enforce some checks through automation. Contributors MUST
distinguish installed checks, manually reviewed requirements, and future gates.
A successful CI run establishes only what that workflow actually executed.

External side effects MUST remain within the approved scope. Public publication,
source redistribution, repository visibility changes, and new uses of private
data require the applicable owner decision and license or data authorization.
An engineering test result does not provide that authority.
