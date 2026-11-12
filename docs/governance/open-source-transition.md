# Source License and Public Distribution Boundary

**Reviewed:** November 12, 2026
**Maintainer:** Lopix Neural Inc.
**Creator:** Fabio de Sousa Lopes
**Contact:** fabio@lopixneural.com

## Adopted source license

Project-owned source and documentation in this revision use Apache License 2.0.
The owner authorized the source-release preparation and license adoption.
`LICENSE`, `NOTICE`, Python metadata, UI metadata, and generated notices must
agree. Upstream components retain their applicable licenses and full notices.
The MCP packages' licensing-transition text is preserved, not simplified to a
single manifest label. The source grant does not relicense private development
records or user-supplied archives.

The maintained product is intended to remain free and nonmonetized. That product
choice does not restrict commercial uses or redistribution permitted by the
license. The company and creator attribution is informational and must not imply
trademark rights, platform affiliation, endorsement, or certification.

Source rights are separate from processing consent. Terms draft.4 corrects the
source-license disclosure; privacy remains draft.3. Changed policy bytes require
fresh acceptance. Production legal review and hosted-service qualification
remain open; the source license is not evidence that they have occurred.

## Publication boundary

Keep `fabiocnd/lpx-keepmorrow` private. Its earlier Git objects, branches, Actions
logs, and artifacts are not approved public history. Removing a file from the
current tree does not remove historical copies. Do not change this repository's
visibility or push its refs to a public remote.

The authorized public destination is `fabiocnd/keepmorrow`. The product and Python
package remain LPX Keepmorrow and `lpx-keepmorrow`. Initialize the public repository
from the reviewed source ZIP with a new root commit. Do not use a fork, mirror,
bundle, or push of the private repository's branches. The public `main` and
`develop` start from that same reviewed root.

Only maintained code, synthetic tests, reusable documentation, build metadata,
third-party notices, and relevant technical measurements belong in the snapshot.
Exclude real exports, account records, private research, conversation transcripts,
credentials, operational databases, logs, caches, and local environments.
Professional project attribution and the designated business contact remain.

## Verification and remaining administrative steps

The source-contract checker validates declared metadata, packaged policy bytes,
known forbidden paths, regular-file entries, and immutable Action references.
Gitleaks scans the complete exported source tree. The public security workflow
also scans the complete public Git history and runs CodeQL for Python and
TypeScript. Passing a scanner is not a guarantee that no sensitive material or
vulnerability exists; inspect the exact source inventory and findings manually.

The CI aggregate requires the existing Python OS/version matrix, optional
service integration, UI/browser tests, and source contract. Release tags must
match package metadata and be contained in `main`. Release automation creates a
draft prerelease with source/wheel artifacts and SHA-256 checksums; it does not
publish to PyPI or deploy a service.

Repository creation, visibility, branch protection, native secret scanning,
push protection, vulnerability reporting, and Dependabot security settings are
administrative controls. Their presence in a script is not evidence of execution.
The connected editing interface did not expose those write operations during
preparation. Follow the [publication runbook](../operations/public-source-release.md)
and verify actual results before claiming them enabled.

## Primary references

- Apache License 2.0: https://www.apache.org/licenses/LICENSE-2.0.html
- Applying Apache License 2.0: https://www.apache.org/legal/apply-license
- GitHub licensing: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository
- GitHub visibility effects: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility
- GitHub Actions secure use: https://docs.github.com/en/actions/reference/security/secure-use
