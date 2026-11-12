# Delivery Roadmap

## Current delivery sequence

The [ChatGPT integration delivery plan](../architecture/chatgpt-delivery-plan.md)
sets the proposed execution order from the 0.2.0 baseline: an actual synthetic
connection, local representative-export validation, an authenticated read-only
pilot, then UI, durable intake/recovery, and operational release evidence.

The milestones below group capabilities; they are not a requirement to complete
cloud storage or durable write jobs before testing the existing read tools in
ChatGPT. Content eligibility, human acceptance, and per-object authorization are
gates before real content is connected. All new plan items remain pending.

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

- [x] Define the experimental mapping profile, versioned collection schema,
  source identifiers, revision rules, association evidence, and artifact states.
- [x] Validate the declared profile with paired synthetic exports, numbered files,
  one wrapper directory, image bytes, opaque binaries, and explicit omissions.
- [ ] Validate and revise the profile against an authorized representative real
  export before claiming real-account compatibility.

**Exit evidence:** All synthetic scenarios have explicit expected results;
unsupported records cannot disappear silently.

## Milestone 2 — usable local archive

- [x] Preserve selected folders and supported ZIPs, including original containers.
- [x] Interpret supported message graphs, namespaced identities, revision history,
  occurrence provenance, and explicit relative-path artifact relationships.
- [x] Provide a standalone readable view, catalog browsing, literal search, and
  bounded revision reading.
- [x] Record explicit local association decisions without changing source evidence.
- [x] Recover selected derived conversations and available bound binary files.
- [ ] Broaden source/attachment support only with representative evidence and
  additional compatibility tests; unresolved URI-only bindings remain visible.

**Exit evidence:** Repeated capture and renamed-conversation scenarios preserve
identity without merging ambiguous records.

## Milestone 3 — recovery and operational resilience

- [x] Apply aggregate payload, JSON, semantic metadata, query, and MCP response limits.
- [x] Exercise handled cancellation, source mutation, corruption, and staging cleanup.
- [ ] Add durable checkpoints and a specified restart/resume protocol.
- [ ] Validate larger representative corpora, crash durability, and storage pressure.

**Exit evidence:** Recovery reconciles the inventory and detects tampering;
partial work is distinguishable from success.

## Milestone 4 — one storage provider

Select a provider, obtain explicit destination authorization, specify ownership
and retention, and implement bounded retries and resumability. Distinguish
receipt acknowledgment from remote integrity verification.

Google Drive remains a candidate. No provider is selected or integrated.

## Milestone 5 — ChatGPT interface

- [x] Review current OpenAI MCP/plugin documentation.
- [x] Implement optional read-only MCP tools over explicit collection grants,
  with acceptance before content I/O and loopback-only development transport.
- [x] Exercise real SDK sessions and in-process Streamable HTTP using synthetic data.
- [ ] Select and implement an authenticated deployment or supported secure tunnel,
  per-user authorization, and hosted data-handling/consent behavior.
- [ ] Connect and validate the plugin in the actual ChatGPT account/workspace.
- [ ] Implement user-selected file intake, interaction review, and any embedded UI
  against supported platform capabilities before exposing write operations.

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

The optional MCP adapter runs one admitted verification job at a time; this is a
bounded development transport, not a parallel preservation engine. The current
implementation and its limits are recorded in
[collection verification](../engineering/collection-verification.md).
