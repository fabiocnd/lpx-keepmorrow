# Contributing to LPX Keepmorrow

LPX Keepmorrow is maintained by **Lopix Neural Inc.** and led by **Fabio de Sousa
Lopes**. Contact: **fabio@lopixneural.com**.

This is a private, proprietary repository. Access permits only the work
authorized by its owner; it does not grant a public redistribution license. The
product's intended free, nonmonetized use is a separate product decision.

## Before changing the repository

Read [AGENTS.md](AGENTS.md), the
[Golden Coding Standard](docs/engineering/golden-coding-standard.md), and the
relevant product or architecture contract. Identify the requirement and expected
behavior before choosing an implementation. Keep historical source snapshots
intact and record subsequent decisions separately.

All newly authored project content uses US English. Original imported material
retains its original bytes and language. Use synthetic examples for development.

## Working on a change

1. Inspect the current branch and working tree. Preserve unrelated changes.
2. Make one coherent change with a clear purpose. Use a short descriptive branch
   when a branch is appropriate to the task.
3. Keep public boundaries typed and validated. Name errors so callers can
   distinguish invalid input, unavailable material, and operational failure.
4. Add meaningful tests for changed behavior and concrete failure modes. A
   documentation-only edit normally needs a documentation review, not a test.
5. Update contracts, examples, and limitation statements affected by the change.
6. Review the diff for accidental secrets, personal material, generated output,
   inconsistent terminology, and unsupported capability claims.

Use an imperative US-English commit subject that describes the effect, for
example, `Reject duplicate manifest paths`. Explain the reason in the body when
it is not apparent from the diff. Attribute commits honestly. When acting on
Fabio's behalf, use `Fabio de Sousa Lopes <fabio@lopixneural.com>`.

## Validation

The initial reference code uses Python's standard library and `unittest`.
Run the commands documented in the current README for the supported environment.
For a source-layout checkout, the basic test invocation is:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Record the interpreter version, exact command, and result. Do not interpret a
passing unit suite as evidence of complete MVP behavior, cloud integration, or
performance at production scale. Follow the
[Performance Policy](docs/engineering/performance-policy.md) when making a
performance claim and the [AI Evaluation Plan](docs/ai/evaluation-plan.md) when
changing a model-assisted feature.

## Review expectations

Use the pull request template when opening a pull request. State the concrete
problem, resulting behavior, verification, and remaining risks. Reviewers should
be able to trace changes to their requirement and inspect the relevant evidence.

An authorized initial import or repository setup may be committed directly as
part of the owner's request. Later work should follow the repository's actual
branch rules. This document does not claim that branch protection, required
reviews, or automated gates are already configured.

Do not add dependencies, model calls, analytics, network access, or a new
integration merely for convenience. Explain the need and record the resulting
data flow, maintenance burden, and applicable licensing. Public publication and
changes to repository visibility require authorization for that action.
