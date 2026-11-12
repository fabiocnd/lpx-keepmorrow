# Contributing to LPX Keepmorrow

LPX Keepmorrow is maintained by **Lopix Neural Inc.** and led by **Fabio de Sousa
Lopes**. Contact: **fabio@lopixneural.com**.

This is a private, proprietary repository. Access permits only the work
authorized by its owner; it does not grant a public redistribution license. The
product's intended free, nonmonetized use is a separate product decision.

The owner now plans an open-source transition. The release license has not yet
been selected or adopted, and repository visibility has not changed. Follow the
current [LICENSE](LICENSE) until the chosen release and contribution terms are
formally adopted; this direction alone is not a new license grant.

## Before changing the repository

Read [AGENTS.md](AGENTS.md), the
[Golden Coding Standard](docs/engineering/golden-coding-standard.md), and the
relevant product or architecture contract. Identify the requirement and expected
behavior before choosing an implementation. Preserve relevant historical
engineering evidence and record subsequent decisions separately.

All newly authored project content uses US English. Original imported material
retains its original bytes and language. Use synthetic examples for development.

## Branch workflow

`develop` is the integration branch for active development. Create short-lived
feature, fix, or documentation branches from `develop`, and target `develop`
with routine pull requests.

`main` contains the reviewed release baseline. Promote changes from `develop`
to `main` through a pull request after review and successful validation.
A merge does not automatically publish a release or deploy the service.

CI validates pushes to both branches and pull requests. This workflow is a
project convention; enforced branch rules are reported separately.

## Working on a change

1. Inspect the current branch and working tree. Preserve unrelated changes.
2. Make one coherent change with a clear purpose on a short descriptive branch
   based on `develop`.
3. Keep public boundaries typed and validated. Name errors so callers can
   distinguish invalid input, unavailable material, and operational failure.
4. Add meaningful tests for changed behavior and concrete failure modes. A
   documentation-only edit normally needs a documentation review, not a test.
5. Update contracts, examples, and limitation statements affected by the change.
6. Review the diff for accidental secrets, personal material, generated output,
   inconsistent terminology, and unsupported capability claims.

Use an imperative US-English commit subject that describes the effect, for
example, `Reject duplicate manifest paths`. Explain the reason in the body when
it is not apparent from the diff. Use the actual author's identity and preserve
accurate attribution for contributed work.

## Validation

The preservation core and durable operation engine use Python's standard
library. The optional private service adds the pinned MCP, HTTP, and identity
dependencies; its companion interface has a separate locked Node package.
Run the commands appropriate to the changed boundary from the repository root.
The basic source-layout check is:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests benchmarks
```

For the complete optional Python service on the recorded Python 3.12 environment:

```bash
python -m pip install -c requirements/chatgpt-dev-py312.constraints.txt '.[chatgpt]'
PYTHONPATH=src python -m unittest discover -s tests -v
```

When changing interface code, follow [the UI build and validation instructions](ui/chatgpt/README.md)
and regenerate its bundled asset and third-party notices. When changing legal
policy bytes, run `python scripts/build_policy_assets.py` and inspect the
resulting package copies. Version or digest changes invalidate existing
acceptance evidence as described by the access contract; never silently preserve
an old acceptance against changed policy text.

Record the interpreter/tool versions, exact commands, pass/skip/failure counts,
and relevant source revision. A skipped optional test was not executed. Treat
local correctness, a remote CI run, live provider/account integration, and a
measured host operating envelope as separate evidence. Follow the
[Performance Policy](docs/engineering/performance-policy.md) when making a
performance claim and the [AI Evaluation Plan](docs/ai/evaluation-plan.md) when
changing a model-assisted feature.

Use [Validation and Release Evidence](docs/engineering/validation.md) for the
current commands and CI jobs. Historical 0.1.0 and 0.2.0 verification records
remain evidence for their recorded revisions; update the current
[private pilot record](docs/engineering/private-pilot-validation.md) with new
results instead of rewriting old counts.

## Review expectations

Use the pull request template when opening a pull request. State the concrete
problem, resulting behavior, verification, and remaining risks. Reviewers should
be able to trace changes to their requirement and inspect the relevant evidence.

For service changes, inspect the trust boundary explicitly: authenticated
principals come from verified credentials; human acceptance and plan review
writers stay outside model-callable tools; publication authorization shares the
grant-revocation transaction; attempt ownership and byte reservations last until
the executor and private cleanup finish. Document each public API's side
effects, ownership, errors, bounds, and relevant complexity. Comments should
explain those invariants and tradeoffs rather than repeat the next statement.

Follow the repository's configured branch rules. This document does not claim
that branch protection, required reviews, or automated gates are already
configured.

Do not add dependencies, model calls, analytics, network access, or a new
integration merely for convenience. Explain the need and record the resulting
data flow, maintenance burden, and applicable licensing. Public publication and
changes to repository visibility require authorization for that action.
