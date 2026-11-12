# ADR 0003: A Bounded Service Around the Preservation Core

**Date:** November 12, 2026
**Status:** Implemented in development version 0.3.0

## Context

Conversation tools need authenticated object access and independent human consent.
Longer preservation work needs reviewable intent, idempotent admission, cancellation,
and recovery from process interruption. These responsibilities must not change the
core's source-fidelity or no-replacement publication contract.

## Decision

Keep the deterministic core and add cohesive access, persistence, operations,
transfers, application, and integration packages. Use one service process, one
exclusive worker, and local SQLite. Store grants and publication decisions in the
same transactional database. Keep the bounded upload ledger separate and reserve
its complete pool during operation admission.

Authenticate the MCP endpoint using configured external OAuth resource tokens.
Use a trusted browser portal for human acceptance and exact-plan review. Local
operator mode serves the portal on loopback and does not expose MCP. The official
MCP Apps SDK provides a compact companion; model-callable tools cannot write an
acceptance receipt or approve a plan.

Each operation binds a typed canonical plan, principal, input digest, resource,
generation, grant/version/acceptance, and storage reservation. Idempotent replay
returns the existing operation. A fresh deliberate capture needs fresh review.
Publication authorization is serialized against withdrawal, followed by atomic
no-replacement filesystem publication and independent reconciliation.

Completed descendants require current ancestor scopes. Explicit fresh human
acceptance may renew a completed ancestor's exact scope. Active plans remain
bound to the original reviewed grant and receipt. The two cases are tested
separately to avoid both unintended permanent lockout and authorization bypass.

Operation workspaces bind exact job/output IDs and a random ownership marker.
Restart cleanup requires matching database and filesystem evidence. Unknown
storage is left untouched. Worker ownership and reservations remain live until
the executor and cleanup finish, including after a client disconnect.

Use a bounded portable ZIP that preserves the collection manifest bytes. The
portal rechecks current identity, exact package scope, lineage, and expiry during
streaming. No arbitrary source URL is fetched and no source data is executed.

## Tradeoffs

One content slot serializes expensive reads and writes. It avoids concurrent
staging amplification but is not a high-concurrency service. Metadata operations
remain independent of that slot, with database contention still measurable.

Queries verify full payloads. New generations copy previous payloads. This costs
I/O and storage but retains a simple, inspectable integrity model. Index caches,
blob deduplication, distributed workers, and per-file resume need separate contracts.

SQLite durability covers journal decisions, not payload power-loss durability.
The tested restart protocol handles a stopped process; it does not promise host,
controller, or storage failure recovery. Deployment qualification remains required.

## Evidence and follow-up

See [private pilot validation](../../engineering/private-pilot-validation.md),
[operation journal](../operation-journal.md), [access control](../access-control.md),
[transfer contract](../transfer-contract.md), and the
[service benchmark](../../../benchmarks/PRIVATE_SERVICE_BENCHMARK.md).
Actual ChatGPT installation, live IdP registration, real-export compatibility,
production legal approval, and source release are separate gates.
