# Changelog

## 0.2.0 — Collections and ChatGPT Development Adapter — 2026-11-12

### Added

- Immutable collection generations from explicitly supplied folders and bounded
  ZIP inputs, with original source bytes, manifests, coverage reports, and an
  offline HTML view.
- An experimental ChatGPT mapping parser with account-scoped conversation
  identity, content revisions, complete supported branch graphs, source
  provenance, explicit project evidence, and unresolved artifact states.
- Verified catalog browsing, literal search, paginated revision reading, separate
  association decisions, and selective recovery of conversation records and
  explicitly bound files.
- A composable archive writer that copies and hashes each added source stream
  once before independent staged verification and no-replacement publication.
- Strict persisted collection validation, pre-decoding JSON resource checks,
  bounded query responses, and a versioned collection JSON Schema.
- An optional MCP development adapter with an explicit collection registry,
  policy acceptance before content access, bounded read-only tools, loopback
  Streamable HTTP, and cancellation-aware admission control.
- Synthetic end-to-end, malformed-input, binary-preservation, protocol, and
  concurrency tests; a reproducible collection benchmark; and an optional SDK
  and schema CI job.
- Current implementation, provider-export comparison, integration, and immutable
  generation architecture documentation.

### Changed

- Organized source by archive, importer, catalog, format, and integration
  responsibilities while retaining a thin command-line boundary.
- Advanced terms and privacy drafts to `2026-11-12-draft.2` to describe the
  expanded local processing and development adapter.
- Required exact current acceptance for every user-facing collection operation.
- Kept association decisions separate from preserved source evidence and
  distinguished partial semantic coverage from successful byte preservation.

### Scope

This remains a private development version. The parser is validated against
synthetic fixtures, not a representative real account export. The MCP adapter
is protocol-tested locally but is not deployed or installed in ChatGPT. Remote
authentication, an embedded ChatGPT UI, file intake through ChatGPT, durable
jobs, physical cross-generation deduplication, and native account restoration
are not implemented. Legal documents remain drafts.

## 0.1.0 — Foundation — 2026-11-12

### Added

- Preserved Blueprint v0.2 and project-source coverage record.
- Product brief, requirements, roadmap, naming conventions, and decision register.
- Private proprietary ownership and canonical contact fabio@lopixneural.com.
- Responsibility-based repository layout and performance review.
- Golden Coding Standard, contribution guidance, and AI evaluation policy.
- Local directory archive reference engine, versioned manifest, synthetic
  conversation fixture, tests, and benchmark harness.
- Draft terms, privacy notice, consent requirements, and legal research.
- Explicit local-operation acceptance boundary.
- Validation workflow configuration with pinned GitHub Actions.

### Fixed

- Obtain complete filesystem identity during Windows inventory before checking
  opened source files for replacement or mutation.
- Use consistent Windows descriptor timestamp semantics and account for
  filename-derived mode bits without weakening subsequent mutation checks.

### Scope

This is a development foundation, not a public product release. Semantic export
parsing, cloud transfer, model integration, durable jobs, and a production user
interface remain outside the implemented scope.
