# Documentation Index

All newly authored project documentation uses US English and follows the
[Golden Coding Standard](engineering/golden-coding-standard.md). Version 0.3.0
contains the deterministic preservation core and the private service reference
implementation. Source implementation, local validation, remote CI, and a live
ChatGPT deployment have separate evidence boundaries.

The owner plans an open-source transition. The release license is not yet
selected or adopted; the current source license and private visibility remain
in effect. Review the [decision register](governance/decision-register.md) for
the current direction and unresolved release choices.

Start with the [product brief](product/product-brief.md). For operation, use the
[private service runbook](operations/private-service-runbook.md); for executed
results and remaining gates, use [private pilot validation](engineering/private-pilot-validation.md).
Historical verification records retain the observations of their named release.

## Product

- [Product brief](product/product-brief.md)
- [Official export comparison](product/export-comparison.md)
- [Requirements and delivery status](product/requirements.md)
- [Roadmap](product/roadmap.md)
- [Ideas and naming](product/ideas-and-naming.md)

## Architecture

- [System overview](architecture/system-overview.md)
- [Reference core](architecture/reference-core.md)
- [Collection workflow](architecture/collection-workflow.md)
- [Import contract](architecture/import-contract.md)
- [ChatGPT integration modes and limits](architecture/chatgpt-integration.md)
- [ChatGPT integration delivery plan](architecture/chatgpt-delivery-plan.md)
- [Consent boundary](architecture/consent-boundary.md)
- [Access-control contract](architecture/access-control.md)
- [External authentication](architecture/external-authentication.md)
- [Trusted human portal](architecture/trusted-portal.md)
- [Operation journal](architecture/operation-journal.md)
- [Transfer contract](architecture/transfer-contract.md)
- [ADR 0001: repository layout](architecture/decisions/0001-repository-layout.md)
- [ADR 0002: immutable collections](architecture/decisions/0002-immutable-collections.md)
- [ADR 0003: private preservation service](architecture/decisions/0003-private-preservation-service.md)

## Engineering

- [Golden Coding Standard](engineering/golden-coding-standard.md)
- [Source comment review and validation](engineering/source-comment-review.md)
- [Performance policy](engineering/performance-policy.md)
- [Historical foundation performance and organization review](engineering/performance-review.md)
- [Validation](engineering/validation.md)
- [Historical 0.1.0 foundation verification](engineering/foundation-verification.md)
- [Historical 0.2.0 collection verification](engineering/collection-verification.md)
- [Private pilot validation](engineering/private-pilot-validation.md)
- [Benchmark index and workload boundaries](../benchmarks/README.md)

## Optional AI policy

The current backend does not implement model inference or training. These
documents govern future model-assisted features and preserve the deterministic
authorization and integrity boundaries of the existing service.

- [AI engineering standard](ai/ai-engineering-standard.md)
- [AI evaluation plan](ai/evaluation-plan.md)

## Operations

- [Private service runbook](operations/private-service-runbook.md)
- [Deployment examples](../deploy/README.md)
- [MCP Apps UI](../ui/chatgpt/README.md)

## Governance and evidence

- [Identity and attribution](governance/identity.md)
- [Decision register](governance/decision-register.md)
- [Legal research](research/legal-basis.md)

## Legal drafts

- [Legal status and review requirements](../legal/README.md)
- [Terms of use](../legal/terms-of-use.md)
- [Privacy notice](../legal/privacy-notice.md)
- [Consent and operation authorization](../legal/consent-and-operation-authorization.md)

Legal documents remain drafts until the owner and qualified counsel complete
the required review. Their inclusion here does not authorize a public launch.

## Release documentation review

- [Version 0.3.0 documentation review](engineering/documentation-review.md)
- [Open-source transition and source release boundary](governance/open-source-transition.md)
