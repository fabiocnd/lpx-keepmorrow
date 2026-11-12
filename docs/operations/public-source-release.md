# Public Source Release Runbook

## Scope and nonnegotiable boundary

This procedure publishes experimental source, not a hosted service. Keep
`fabiocnd/lpx-keepmorrow` private. The authorized public destination is
`fabiocnd/keepmorrow`; the product/package name remains LPX Keepmorrow.
Never use `git push --mirror`, `--all`, a fork, the private `.git` directory, or a
private-history bundle to populate the destination.

## 1. Validate the exact candidate

Start with a clean checkout of the reviewed source-release commit. Confirm the
source-license grant, contributions/asset rights, third-party notices, and source
inventory. Only synthetic examples may be included. Resolve scanner findings;
rotate exposed credentials rather than allowing them through. There is no claim
that a scanner can certify the absence of every secret or personal detail.

Run `python scripts/check_public_source.py`, the complete Python/core/service
and UI/browser CI, and the source secret scan on that exact revision. A skipped
optional test is not an executed test. CodeQL deliberately skips the historical
private repository unless an appropriate separate setup is established; it must
complete on the public destination. Do not infer that a successful CodeQL upload
means it found no vulnerabilities; review the reported findings.

The release-contract check guards metadata, policy copies, known forbidden
paths, regular files, and immutable Action pins. It does not replace Gitleaks,
a dependency review, or human inspection. Review Dependabot updates together with
Python constraints and UI locks; no unattended auto-merge is configured.

## 2. Export without private history

From a clean, committed checkout, write to a new path outside the repository:

```sh
python scripts/export_public_source.py ../LPX-Keepmorrow-Source.zip
```

Record the source revision and SHA-256 checksum. Inspect the ZIP inventory before
publication. The ZIP contains the tracked tree only, not Git objects or Actions
artifacts. Retain the review evidence privately, separate from the public tree.

## 3. Create a fresh destination

An authenticated GitHub administrator with repository-creation permission must
perform this step. The connected editor used for preparation did not expose
repository creation or administrative writes; a document or script is not proof
that those actions occurred.

Extract the reviewed ZIP into an empty directory, then run these commands inside
its `lpx-keepmorrow` directory. Use GitHub CLI with your own authenticated account;
never paste a token into the repository, a chat, or a command argument.

```sh
git init --initial-branch=main
git config user.name "Fabio de Sousa Lopes"
git config user.email "fabio@lopixneural.com"
git add .
git commit -m "Publish the reviewed LPX Keepmorrow source baseline"
git branch develop
gh repo create fabiocnd/keepmorrow --private --source=. --remote=origin
git push origin main develop
```

Verify with `git rev-list --all --count` that both branches share one root commit.
Check the initial private CI and source scan. Stop on any failed or missing check.
This new repository has no historical private development refs or Actions logs.

After inspecting the exact new repository and authorizing its reviewed contents:

```sh
gh repo edit fabiocnd/keepmorrow --visibility public --accept-visibility-change-consequences
gh workflow run ci.yml --repo fabiocnd/keepmorrow --ref main
gh workflow run security.yml --repo fabiocnd/keepmorrow --ref main
```

Check the actual workflow results. The public security run must include both
CodeQL languages and the public-history scan. The explicit dispatch is necessary
because changing visibility does not itself establish a new push or test result.
The other long-lived branch initially has the same commit; revalidate whenever
its head changes.

## 4. Apply and verify GitHub controls

The included bootstrap helper changes only `fabiocnd/keepmorrow`, never the
historical repository, and never changes visibility. Its default is a dry run.
It requires administrator rights and successful `CI required` and
`Security required` checks at both branch heads before any administrative write.
It refuses to overwrite existing branch protections; review those manually.

```sh
python scripts/configure_public_github.py
python scripts/configure_public_github.py --apply --reviews 0
```

The sole-maintainer baseline requires PRs, strict status checks, resolved review
threads, linear history, and blocks force pushes/deletions for `main` and
`develop`, including administrators. Zero independent approvals avoids an
impossible self-review requirement. Use `--reviews 1` at initial setup when a
second maintainer can review. The helper requests native secret scanning, push
protection, vulnerability alerts, security updates, and private vulnerability
reporting, and sets default Actions token permissions to read-only.

The operations are not transactional. A failure can leave earlier changes
applied; inspect the repository before retrying. Review the returned settings
and Security/Actions UI. No paid security product is enabled by this helper.
CodeQL upload success is not an enforced severity threshold; review findings
before release or adopt a separately verified code-scanning merge rule.

## 5. Publish a reviewed experimental release

Promote validated changes through a PR from `develop` to `main`. A release tag
must be exactly `v<pyproject version>` and point to a commit contained in `main`.
The release workflow repeats CI/security, builds an sdist and wheel, includes
LICENSE/NOTICE, and packages the source ZIP with checksums. It creates a draft
prerelease for human inspection, never an automatic stable/public package release.

Review artifacts, notices, checksums, known limitations, and security findings
before publishing the draft. Do not announce native ChatGPT installation,
real-export compatibility, production readiness, or legal certification without
separate evidence. Back out by withholding the draft; never delete or rewrite
private history as part of release rollback.
