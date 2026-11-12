# Open-Source Transition and Source Release Boundary

**Reviewed:** November 12, 2026
**Status:** Release preparation; the existing private proprietary license remains in force
**Maintainer:** Lopix Neural Inc.
**Contact:** fabio@lopixneural.com

## 1. Intended outcome

Prepare LPX Keepmorrow for a public source release that includes reusable code,
professional documentation, synthetic tests, reproducible builds, and accurate
operating limits. Retain project attribution while excluding private development
conversations, personal research, credentials, account records, and operational
user data.

Source publication and a hosted-service launch are separate actions. A source
license does not transfer user-data rights, authorize account access, establish
processing consent, or approve the service's draft legal terms.

## 2. License recommendation

**Engineering recommendation: Apache License 2.0.** It provides broad reuse and
redistribution rights, an explicit contributor patent grant, and defined notice
requirements. Its patent terms and attribution obligations make it a reasonable
candidate for a company-maintained software project. This recommendation has not
been adopted as the repository's effective license. [L1]

| Candidate | Practical consideration | Proposed fit |
| --- | --- | --- |
| Apache-2.0 | Explicit patent grant and redistribution/notice rules; includes conditions that maintainers must preserve | Recommended for the planned release |
| MIT | Short permissive grant requiring preservation of its copyright and permission notice; no equivalent express patent section | Alternative if licensing simplicity is the overriding preference |

Both allow downstream commercial use. The maintained project's free,
nonmonetized direction can remain its own operating choice, but an open-source
license must not prohibit business use or redistribution merely to enforce that
choice. Source visibility alone does not create open-source rights. [L2][L3]

The selected license must be adopted consistently in `LICENSE`, package metadata,
source headers where appropriate, notice generation, contribution guidance,
distribution artifacts, and release notes. Do not combine an open-source claim
with a contradictory proprietary or `UNLICENSED` project declaration.

## 3. Materials included and excluded

| Include in the reviewed source snapshot | Exclude from distribution |
| --- | --- |
| Maintained source, schemas, synthetic fixtures, and tests | Real exports, user collections, uploaded files, and recovery outputs |
| Current architecture, requirements, runbook, and engineering standards | Private conversation transcripts, session links, and internal source snapshots |
| Public professional project attribution and designated business contact | Personal account records, biographical research, and unrelated identity details |
| Reproducible workload descriptions and measured technical evidence | Credentials, cookies, operator keys, IdP subjects, live service databases, and private host configuration |
| Dependency locks, exact bundled notices, and release instructions | Local virtual environments, installed packages, caches, temporary scratch, and browser profiles |

Synthetic tests can use clearly artificial identities and private-path examples
to verify error redaction. Such fixtures are test data, not actual account records.
Technical hashes identify tested source and artifacts; they do not disclose user
archives when their inputs are the committed synthetic workload.

## 4. History and publication boundary

Removing files from the current tree does not remove their earlier Git objects.
The existing private development history therefore must not be treated as a
reviewed public history. GitHub also makes Actions history and logs visible when
a repository becomes public. [L4]

The recommended publication path is a fresh repository initialized from the
reviewed source snapshot after license adoption. That boundary transfers approved
files without carrying earlier private commits, branches, tags, or CI artifacts.
Keep the original development repository private. A branch in the same repository
is not an equivalent privacy boundary when the whole repository becomes public.

An alternative history rewrite would require its own complete review of all
reachable refs, logs, artifacts, existing clones, and publication effects. No
history purge or visibility change is represented as completed here.

The review ZIP produced with `git archive` contains tracked source files from one
commit, without the `.git` database or untracked local state. Its current license
remains proprietary until a selected open-source license is adopted. Review and
rebuild the exact artifact before public publication.

## 5. Dependency and contribution review

The current bundled MCP Apps resource includes five dependency packages. Full
installed license texts are retained in
[`ui/chatgpt/THIRD-PARTY-NOTICES.txt`](../../ui/chatgpt/THIRD-PARTY-NOTICES.txt)
and the packaged asset copy. Some package metadata labels differ from the supplied
MCP Apache/MIT transition text. Preserve the actual license text and resolve its
application before a public distribution; do not simplify the evidence to a
single manifest label. Dependency notices must match the actual distribution. [L5]

Confirm the right to license all contributed code and assets. Establish a clear
inbound contribution policy consistent with the chosen outbound license before
accepting public contributions. Contribution review must keep real user archives,
secrets, and privately copied code out of issues, patches, fixtures, and logs.

## 6. Release acceptance

A public release requires a concrete source commit and artifact, the adopted
license and matching metadata, complete applicable third-party notices, passing
release CI, a reviewed history boundary, and maintainer approval of the public
destination. The source remains experimental where the compatibility record says
so. Public availability must not be described as a completed ChatGPT deployment
or a production privacy/legal certification.

Current technical evidence is recorded in
[private pilot validation](../engineering/private-pilot-validation.md).
The [roadmap](../product/roadmap.md) keeps live integration and source release
milestones independently visible.

## Primary references

- [L1 — Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0.html)
- [L2 — MIT License](https://opensource.org/license/mit)
- [L3 — Open Source Definition](https://opensource.org/osd)
- [L4 — GitHub: Setting repository visibility](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
- [L5 — Apache: Assembling LICENSE and NOTICE files](https://infra.apache.org/licensing-howto.html)
