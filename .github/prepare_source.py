"""One-time, owner-authorized migration; removed before the review commit."""
from pathlib import Path
from urllib.request import urlopen
import re
import shutil

R = Path.cwd()

def write(p, s):
    f = R / p
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(s, encoding="utf-8")

def change(p, a, b):
    f = R / p
    s = f.read_text()
    assert a in s, (p, a[:60])
    f.write_text(s.replace(a, b))

def paragraph(p, needle, new):
    f = R / p
    parts = f.read_text().split("\n\n")
    matches = [i for i, s in enumerate(parts) if needle in s]
    assert len(matches) == 1, (p, needle, matches)
    parts[matches[0]] = new
    f.write_text("\n\n".join(parts))

with urlopen("https://www.apache.org/licenses/LICENSE-2.0.txt", timeout=30) as response:
    license_bytes = response.read()
assert b"Version 2.0, January 2004" in license_bytes
assert b"END OF TERMS AND CONDITIONS" in license_bytes
(R / "LICENSE").write_bytes(license_bytes)
write("NOTICE", '''LPX Keepmorrow
Copyright (c) 2026 Lopix Neural Inc.

Publisher and maintainer: Lopix Neural Inc.
Creator and lead developer: Fabio de Sousa Lopes
Project contact: fabio@lopixneural.com

Project-owned source and documentation in this revision are licensed under
Apache License 2.0. See LICENSE. Earlier private development records and
user-supplied contents are not relicensed by this source release.

The maintained product is intended to remain free and nonmonetized. This is a
product direction, not a restriction on rights granted by Apache License 2.0.
Third-party components retain their copyrights and licenses. Complete notices
for the bundled interface are retained in ui/chatgpt/THIRD-PARTY-NOTICES.txt and
the packaged asset copy. This NOTICE does not modify any applicable license.

References to ChatGPT, OpenAI, GitHub, and storage providers identify integration
targets, not affiliation, endorsement, approval, or access to user accounts.
''')
change("pyproject.toml", '# Keep release metadata consistent with LICENSE when a source license is adopted.\nlicense = {text = "Proprietary. Copyright 2026 Lopix Neural Inc. All rights reserved."}', 'license = "Apache-2.0"\nlicense-files = ["LICENSE", "NOTICE"]')
for p in ["ui/chatgpt/package.json", "ui/chatgpt/package-lock.json"]:
    change(p, '"license": "UNLICENSED"', '"license": "Apache-2.0"')
change("ui/chatgpt/scripts/build.mjs", "// The private project's license does not supersede these upstream notices.", "// The project license does not supersede these upstream notices.")
for p in ["ui/chatgpt/scripts/build.mjs", "ui/chatgpt/THIRD-PARTY-NOTICES.txt", "src/keepmorrow/integrations/chatgpt/assets/THIRD-PARTY-NOTICES.txt"]:
    change(p, "Project source: proprietary, Copyright 2026 Lopix Neural Inc. All rights reserved.", "Project source: Apache-2.0, Copyright 2026 Lopix Neural Inc.")
change("src/keepmorrow/integrations/chatgpt/portal_assets/index.html", "Private development pilot · Proprietary source · No model training", "Private development pilot · Apache-2.0 source · No model training")
change("legal/terms-of-use.md", "**Terms version:** `2026-11-12-draft.3`", "**Terms version:** `2026-11-12-draft.4`")
paragraph("legal/terms-of-use.md", "Its source code is proprietary.", '''Project-owned source and documentation in this revision are licensed under the
accompanying Apache License 2.0. That license governs the software rights it
grants. These draft processing terms do not add restrictions to, replace, or
condition those rights. Earlier private records and user-supplied content are
not relicensed. The maintained product's free, nonmonetized direction does not
restrict downstream commercial uses permitted by the source license. Source
licensing does not authorize account access or processing of personal data,
approve a hosted-service launch, or grant endorsement or trademark rights.''')
change("src/keepmorrow/consent.py", 'CURRENT_TERMS_VERSION = "2026-11-12-draft.3"', 'CURRENT_TERMS_VERSION = "2026-11-12-draft.4"')
shutil.copyfile(R / "legal/terms-of-use.md", R / "src/keepmorrow/policies/terms-of-use.md")
for p in ["README.md", "legal/README.md", "legal/consent-and-operation-authorization.md", "docs/operations/private-service-runbook.md"]:
    f = R / p
    f.write_text(f.read_text().replace("--accept-terms 2026-11-12-draft.3", "--accept-terms 2026-11-12-draft.4"))
change("README.md", "draft version `2026-11-12-draft.3`.", "terms `2026-11-12-draft.4` and privacy notice `2026-11-12-draft.3`.")
change("README.md", "**Source:** Currently private and proprietary; [open-source transition planned](docs/governance/open-source-transition.md), with release license pending · **Project language:** US English", "**Source license:** [Apache-2.0](LICENSE) · **Release stage:** Experimental · **Project language:** US English")
f = R / "README.md"
s = f.read_text()
s = s[:s.index("## Ownership and release status")] + '''## Ownership and release status

Copyright (c) 2026 Lopix Neural Inc. Project-owned source and documentation in
this revision use [Apache License 2.0](LICENSE). [NOTICE](NOTICE) and the bundled
third-party notices preserve professional attribution and upstream terms.

The maintained project is free and nonmonetized; downstream license rights are
not restricted by that choice. The UI package remains `private: true` only to
prevent accidental npm publication. Imported content retains its original rights.

Publish only a reviewed source snapshot with a new root commit. The existing
private development history must remain private. License adoption does not mean
that a public repository was created, repository protections were configured,
or a production service was deployed. Follow the [publication runbook](docs/operations/public-source-release.md)
and [transition record](docs/governance/open-source-transition.md).

The source is experimental. Real ChatGPT integration, representative real-export
validation, deployment qualification, and final processing terms remain separate
gates. The [historical pilot record](docs/engineering/private-pilot-validation.md)
retains evidence for its exact earlier revisions. Updated terms require new
acceptance; old receipts are not silently migrated.
'''
f.write_text(s)
paragraph("AGENTS.md", "The current repository is private under", '''Project-owned source in this revision uses Apache License 2.0. The existing
private development history must remain private. Publish only an approved source
snapshot with a new root commit, never the existing refs or CI history. The
maintained product's free, nonmonetized direction does not restrict downstream
license rights. Apply the user's explicit authorization without asking again
for the same approved work. Source licensing never authorizes user-data sharing.''')
change("AGENTS.md", "Keep historical source material under\n`docs/provenance/` and identify its retrieval date.", "Keep private historical source material outside the distributable tree.\nDo not restore removed private provenance or biographical research.")
f = R / "CONTRIBUTING.md"
s = f.read_text()
a = s.index("This is a private, proprietary")
b = s.index("## Before changing")
s = s[:a] + '''Project-owned source in this revision uses [Apache License 2.0](LICENSE).
Intentional contributions use the same license under its contribution terms.
Submit only work you have authority to license; identify third-party material
and preserve its notices. No separate CLA or DCO sign-off is currently required.
Imported user data and private development records are never contributions.

Keep discussion respectful and constructive. Report harassment privately to the
maintainer. Follow [SECURITY.md](SECURITY.md) for sensitive reports; never attach
real exports, credentials, or personal data to public issues or pull requests.

''' + s[b:]
s += '''
## Release and administrative controls

The intended required checks are `CI required` and `Security required`. Workflow
files do not prove that server-side branch protection or native security settings
are enabled. See the publication runbook for the exact administrative steps.
A sole-maintainer setup uses pull requests and checks with zero required external
approvals; require one independent approval when a second maintainer is available.
Do not represent a maintainer's own merge as independent review. Dependabot version
updates target `develop`; native security updates may target the default branch.
'''
f.write_text(s)
paragraph("SECURITY.md", "This repository is private and", '''Lopix Neural Inc. maintains this source revision under Apache License 2.0.
Earlier private history is excluded from public distribution. No public bug
bounty or remediation SLA is operated. Only the current development line is
actively maintained; it is not certified for production processing. Use GitHub
private vulnerability reporting only after it is enabled, or the email above.
Do not post sensitive reports publicly. Rotate confirmed leaked credentials
rather than suppressing scanner findings to obtain a passing build.''')
change("SECURITY.md", "**Applies to:** The private 0.3.0 reference implementation", "**Applies to:** The experimental 0.3.0 reference implementation")
paragraph("ui/chatgpt/README.md", "license remains proprietary", '''Project-owned source uses Apache License 2.0. The UI package keeps `private: true`
to prevent accidental npm publication, not to restrict source rights. Its manifest
and lockfile declare `Apache-2.0`. THIRD-PARTY-NOTICES.txt is generated from the
packages that contribute bytes to the bundle and retains their complete installed
license texts, including the MCP transition notices. Development dependencies
remain identified in the lockfile, not included in the production HTML.''')
change("docs/architecture/chatgpt-integration.md", "This dependency does not change the proprietary license of Keepmorrow.", "This dependency retains its own license; project-owned Keepmorrow source uses Apache-2.0.")
for p, needle in [("docs/operations/private-service-runbook.md", "An open-source transition is planned."), ("docs/README.md", "The owner plans an open-source transition."), ("docs/product/product-brief.md", "The current repository remains private under"), ("docs/product/export-comparison.md", "An open-source transition is planned.")]:
    paragraph(p, needle, '''Project-owned source in this revision uses Apache License 2.0. The historical
development repository stays private; public distribution uses a reviewed source
snapshot with a fresh root commit. Source licensing, actual public publication,
and hosted-service qualification are separate decisions and evidence gates.
The maintained product's free direction does not restrict downstream rights.''')
change("docs/operations/private-service-runbook.md", "Use a private checkout and the tested Python environment for the release.", "Use a reviewed checkout and the tested Python environment for the release.")
paragraph("docs/engineering/private-pilot-validation.md", "An open-source transition is planned.", '''At the time of the historical runs below, source-license adoption was pending.
The subsequent source-release preparation adopts Apache-2.0 for the new revision.
That decision does not rewrite the original source hashes, policy versions,
counts, or artifacts measured here. Revalidate the exact publication candidate.''')
paragraph("legal/README.md", "The owner intends to transition", '''Project-owned source in this revision uses Apache License 2.0. These processing
drafts do not restrict or condition the rights that license grants. Source
licensing does not establish privacy compliance, approve hosting, or grant access
to user accounts. Terms draft.4 corrects the source-license disclosure; privacy
remains draft.3. Changed policy bytes and versions require fresh acceptance.''')
change("legal/README.md", "**Document set version:** `2026-11-12-draft.3`", "**Terms version:** `2026-11-12-draft.4` · **Privacy version:** `2026-11-12-draft.3`")
change("legal/consent-and-operation-authorization.md", "**Document version:** `2026-11-12-draft.3`", "**Document version:** `2026-11-12-draft.4`")
change("docs/governance/identity.md", "Private repository under the existing proprietary license", "Apache-2.0 source revision; private history excluded from publication")
change("docs/research/legal-basis.md", "The exact license and publication decision remain pending;", "Apache-2.0 is subsequently adopted for the new revision; public publication remains separate;")
f = R / "docs/governance/decision-register.md"
s = f.read_text()
s = re.sub(r"^\| D005 .*$", "| D005 | Preserve the private development history | Historical license superseded by D037 | Do not publish old refs, logs, or private development records |", s, flags=re.M)
s = re.sub(r"^\| D035 .*$", "| D035 | Prepare an open-source transition | License decision completed by D037 | Public repository creation remains a separately verified action |", s, flags=re.M)
s = s.replace("## Change discipline", '''| D037 | Adopt Apache-2.0 for this source revision | Owner-authorized | Align root license, metadata, notices, and current guidance; exclude private records and user content |
| D038 | Publish a fresh source snapshot to `fabiocnd/keepmorrow` | Authorized destination; administrative execution pending | Preserve the LPX Keepmorrow product/package identity and keep `fabiocnd/lpx-keepmorrow` private |
| D039 | Advance terms to draft.4 and retain privacy draft.3 | Draft policy | Correct source-license disclosure without broadening processing permissions; require new acceptance |

## Change discipline''')
f.write_text(s)
change("docs/product/roadmap.md", "- [ ] Adopt the exact release license and update all corresponding package metadata.", "- [x] Adopt Apache-2.0 for the source revision and align package metadata.")
change("docs/product/roadmap.md", "- [ ] Establish public contribution, issue-reporting, security, and release procedures.", "- [x] Establish contribution, issue-reporting, security, and draft-release procedures.\n- [ ] Apply and verify branch protections and native GitHub security settings.")
paragraph("docs/product/roadmap.md", "The current repository remains private under", '''The historical repository stays private. Apache-2.0 is adopted for the new source
revision; public destination creation, administrative settings, and final source
validation remain separately verifiable steps in the publication runbook.''')
change("docs/architecture/chatgpt-delivery-plan.md", "| License adoption and public destination decision |", "| Exact-candidate validation, public destination creation, and administrative settings |")
change("CHANGELOG.md", "# Changelog", '''# Changelog

## Unreleased — open-source preparation

- Adopt Apache-2.0 for project-owned source and align package metadata/notices.
- Preserve private history and third-party attribution; publish a fresh snapshot.
- Advance draft terms to draft.4 while retaining privacy draft.3 and fresh consent.
- Add release-contract checks, security scanning, Dependabot, issue forms, and
  draft-release packaging. Server-side GitHub settings remain separately verified.
''')
print("Applied the reviewed source-license and documentation migration.")
