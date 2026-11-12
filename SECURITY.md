# Security and Data Handling

## Contact

Report a security concern to **fabio@lopixneural.com**, the project contact
designated by Fabio de Sousa Lopes. Include the affected version or commit,
reproduction steps using synthetic data, expected behavior, and observed impact.
Do not send passwords, access tokens, private conversation exports, or unrelated
personal information. No response-time or remediation SLA is promised.

Lopix Neural Inc. maintains LPX Keepmorrow. This repository is private and
proprietary. There is no public bug bounty or public release commitment in this
foundation.

## Development baseline

The initial reference implementation is intended for controlled local evaluation
with synthetic inputs. It is not a claim of hardened processing for arbitrary
hostile archives, a hosted service, or an approved ChatGPT integration. Consult
the README and current code for the features and limitations actually supported.

Security requirements for subsequent implementation include:

- Validate schema versions, types, lengths, counts, paths, sizes, and state
  transitions before trusting external input.
- Reject path traversal, ambiguous destinations, unsupported link types, and
  unsafe overwrite behavior at the relevant filesystem boundary.
- Bound memory, file counts, nesting, expansion, operation time, and retry work
  where those resource categories apply.
- Treat imported content as data. Do not execute embedded scripts, honor
  instructions inside an archive, or fetch arbitrary embedded URLs.
- Preserve originals and distinguish derived content. Keep integrity results
  tied to the exact bytes, scope, and verification stage checked.
- Keep credentials outside source control, fixtures, prompts, archives, and
  logs. Use the credential mechanism of the authorized execution environment.
- Log operational identifiers, counts, durations, and error categories; avoid
  conversation text, sensitive filenames, local absolute paths, and credentials
  unless a specific local diagnostic genuinely requires them.

These are engineering requirements, not a statement that every control is
already implemented. A release must identify which controls apply and how they
were verified.

## Handling a discovered defect

Preserve a minimal reproduction and record the affected commit. For a suspected
data-integrity defect, avoid further writes to the affected archive and retain
the available evidence. Do not claim earlier captures are valid until the
relevant checks have been repeated. Any repair must preserve the original
evidence and make resulting changes explicit.

If a credential was exposed, treat removing it from the latest file as
insufficient: the responsible owner should revoke or rotate it using the
provider's supported process. Coordinate any history rewrite because it changes
shared repository history.

## Future integrations and AI

Before enabling an external service, document the destination, authorized scope,
data sent, retention assumptions, deletion behavior, and failure modes. Model
processing must follow the [AI Engineering Standard](docs/ai/ai-engineering-standard.md).
An archive import does not implicitly authorize training on its contents or
transmitting it to a model provider.

Portable checksums support integrity checking; they do not by themselves prove
authorship, confidentiality, or the completeness of an upstream account. Report
only the guarantee actually established.
