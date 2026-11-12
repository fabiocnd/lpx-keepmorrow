# Delivery Roadmap

**Baseline:** Version 0.3.0 development candidate
**Reviewed:** November 12, 2026

Implemented engineering work is distinct from a live pilot or public release.
The [delivery plan](../architecture/chatgpt-delivery-plan.md) maps each phase to
its current evidence and external dependencies.

## Implemented foundation and preservation

- [x] Organize source and documentation by responsibility.
- [x] Define engineering, performance, AI, ownership, and consent boundaries.
- [x] Preserve selected directories, compatible ZIPs, binaries, and original containers.
- [x] Reconcile supported conversation identities, revisions, branches, and captures.
- [x] Report unknown associations and unavailable artifacts explicitly.
- [x] Provide browsing, literal search, revision reading, verification, and recovery.
- [x] Keep updates and association decisions in new immutable generations.
- [ ] Validate an authorized representative real export and document unsupported cases.

## Implemented private service

- [x] Validate configured external OAuth resource tokens and explicit identities.
- [x] Record independent human consent, exact-generation grants, expiry, and withdrawal.
- [x] Review canonical operation plans through the trusted portal.
- [x] Persist idempotent operations, cancellation, reservations, and attempt ownership.
- [x] Serialize publication authorization against revocation and reconcile process stops.
- [x] Clean only proven operation-owned scratch; preserve ambiguous directories.
- [x] Receive bounded uploads and create, deliver, and unpack verified portable ZIPs.
- [x] Recheck current scope, ancestors, session, and package expiry during delivery.
- [x] Provide a TypeScript MCP Apps companion and an authenticated browser portal.
- [x] Record synthetic integration tests and a reproducible service benchmark.
- [ ] Confirm the selected live identity provider, browser-client registration, and host.
- [ ] Demonstrate installation and real interaction in the intended ChatGPT account.
- [ ] Validate eligibility and explicit scope before connecting real user material.
- [ ] Qualify deployment transport, browser behavior, accessibility, and recovery drills.

## Open-source preparation

- [x] Record the intended transition and retain professional project attribution.
- [x] Separate source licensing from processing consent and user-data ownership.
- [x] Inspect bundled UI license texts and preserve third-party notices.
- [x] Adopt Apache-2.0 for the source revision and align package metadata.
- [x] Inspect a sanitized source artifact with no private development history.
  Rebuild and recheck the exact public artifact after license adoption.
- [ ] Approve and create the public distribution destination and publication history.
- [x] Establish contribution, issue-reporting, security, and draft-release procedures.
- [ ] Apply and verify branch protections and native GitHub security settings.

The historical repository stays private. Apache-2.0 is adopted for the new source
revision; public destination creation, administrative settings, and final source
validation remain separately verifiable steps in the publication runbook.

## Operational release gates

- [ ] Select operator, storage location, region, identity provider, and budget.
- [ ] Approve final processing notices and deployment-specific retention with counsel.
- [ ] Exercise backup/restore, revocation, incident handling, and rollback on that host.
- [ ] Measure larger representative workloads and overload on the selected hardware.
- [ ] Validate any platform file-transfer capability before adding it to the interface.
- [x] Inspect the complete six-job CI matrix and retain its exact source and results.
  Repeat the required checks for any subsequent release change.

A journal provides process-restart reconciliation; per-file resume and payload
power-loss durability remain unimplemented. Neither a source release nor a
passing synthetic test authorizes hosted processing of unrestricted history.

## Deferred until justified

Remote storage adapters, physical blob deduplication, persistent search indexes,
parallel workers, distributed orchestration, model inference, embeddings, and
native provider restoration require a concrete need and a separate design.
Google Drive is one possible future storage adapter; none is integrated today.
