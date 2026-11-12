# Product Brief

**Product:** LPX Keepmorrow
**Publisher:** Lopix Neural Inc.
**Creator and lead developer:** Fabio de Sousa Lopes
**Contact:** fabio@lopixneural.com
**Baseline date:** 2026-11-12

**Implementation:** 0.2.0 internal development

## Purpose

Preserve the AI work a user explicitly chooses to archive, keep its available
artifacts connected to their sources, and make recovery verifiable. The product
addresses work fragmented across projects, standalone conversations, branches,
revisions, documents, images, and code.

The initial audience is independent professionals, researchers, creators,
developers, and small teams. This audience is a product hypothesis, not a
validated market-size or adoption claim.

## Product commitments

- Free use, with no monetization, paid tiers, upsells, or advertising.
- Clear credit to Lopix Neural Inc. and Fabio de Sousa Lopes.
- Private, proprietary development source under the owner's current direction.
- Explicitly selected inputs and clear preservation scope.
- Original bytes retained before any derived interpretation.
- Portable recovery, with documented checks and visible omissions.
- Explicit user acceptance and operation authorization before processing.
- No promotional changes to preserved conversations or original files.

## Organization model

A conversation can be linked to a confirmed project, confirmed as standalone,
or left with an unknown association. Missing project metadata does not establish
standalone status. Each classification needs recorded evidence. AI suggestions
remain suggestions until an authorized decision establishes a classification.

Projects, conversations, captures, revisions, messages, and artifacts are
different entities. A folder name is a presentation label, not a durable identity.
A content hash identifies bytes, not a person or a logical conversation.

## Current delivery

Version 0.2.0 builds a local conversation collection from explicitly selected
directories or supported ZIP exports. It retains original files and raw ZIP
containers, then derives a catalog, coverage report, and standalone HTML view.
The experimental ChatGPT mapping profile supports message graphs, branches,
structural roots, namespaced conversation identities, and complete-record revision
history across repeated captures.

Users can browse, search, and read retained revisions; record an explicit project,
standalone, or unknown association; and recover either the complete payload or a
selected conversation/project package. Available images and other supplied binary
files remain byte-for-byte copies. Semantic artifact links require explicit
supported path evidence; missing or unresolved media remains visible. No remote
artifact is fetched merely because an export contains its URL.

Each update creates a new generation and leaves previous generations unchanged.
Existing capture files are physically copied into the new generation. Revision
reuse reduces duplicate normalized records; physical blob deduplication and
resumable jobs are not implemented. The
[local collection workflow](../architecture/collection-workflow.md) explains the
available commands and outputs.

The optional read-only MCP adapter provides collection browsing, search, reading,
and verification through the official SDK. Its loopback implementation has SDK
protocol tests. It is not yet connected to a real ChatGPT account, deployed, or
authenticated. The intended ChatGPT experience still requires a deployment,
identity and access design, installation, and account-level acceptance testing.
See the [ChatGPT integration contract](../architecture/chatgpt-integration.md).

## Compatibility evidence

The semantic parser is explicitly experimental. Paired synthetic mapping exports
exercise collection behavior, but no representative real account export has been
validated. The earlier `examples/synthetic-input/catalog.json` remains an opaque
generic-archive demonstration. These fixtures establish different engineering
contracts; neither proves universal compatibility with ChatGPT exports.

The [import contract](../architecture/import-contract.md) defines supported shapes,
artifact binding, limits, and partial outcomes. The
[collection verification record](../engineering/collection-verification.md)
records observed test evidence. Broader artifact mapping and authentic-source
validation remain required work.

## Boundaries

The product's scope is the material a user supplies. It does not promise
unrestricted account discovery, complete capture of every asset, restoration of
never-supplied deleted material, continuous synchronization from occasional
exports, or recreation of native ChatGPT chats and Projects. A portable restore
is a separate collection of ordinary files.

Selected recovery contains derived conversation records and available bound
artifacts. It omits whole source ZIPs and recognized whole conversation export
documents, which can contain unselected conversations. Arbitrary chosen binary
attachments are not internally redacted. Full originals remain available in the
parent collection.

The official export may already satisfy a user's preservation needs. Keepmorrow
adds a local workflow for repeated captures, explicit associations, revision
browsing, verification, and selection. It cannot recover bytes absent from the
supplied material. See the [export comparison](export-comparison.md) for the
documented distinction.

Terms, privacy notices, and operation consent must accurately describe the
implemented deployment. Free use and a user waiver do not eliminate mandatory
legal duties. Cloud storage, authenticated hosting, retention and deletion rules,
crash durability, and resume remain open work. Public distribution requires a
separate owner decision and legal review.

## Evidence

This brief consolidates the [Blueprint v0.2](../provenance/blueprint-v0.2-snapshot.md)
and the owner's repository, engineering, organization, contact, and legal
instructions on 2026-11-12. See the
[decision register](../governance/decision-register.md) for the status of each
choice.
