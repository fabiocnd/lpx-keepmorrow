# Source comment and documentation review

**Review date:** 2026-11-12

**Release:** 0.3.0 reference service

**Scope:** US English comments, docstrings, explanatory configuration comments,
generated UI assets, and related documentation

This review applies the project's [Golden Coding Standard](golden-coding-standard.md)
to the current implementation. It clarifies contracts and evidence boundaries
without changing executable statements, dependencies, configuration values, or
test assertions. The README's native-export comparison tables and subjective
scores were removed at the owner's request.

The reviewed GitHub baseline was commit
`eadb8d3ef5c521f090569d23277fc21260eecec8`, with source tree
`3bfd7e206209ee574ab972dbf2ce4d6862ec65b9`. The local baseline had the same tree.

## Coverage

Every tracked Python file and every authored browser source, test, build script,
and template was reviewed. Four implementation and deployment configurations
were also reviewed. Files whose existing comments were sufficient were retained
without cosmetic edits.

| Authored file category | Reviewed | Updated |
| --- | ---: | ---: |
| Python source, tests, benchmarks, and build scripts | 92 | 53 |
| JavaScript, TypeScript, and MJS | 13 | 13 |
| CSS | 2 | 2 |
| HTML templates | 2 | 2 |
| CI, package, systemd, and nginx configuration | 4 | 4 |
| Total | 113 | 74 |

The generated MCP Apps HTML asset was rebuilt through the existing build script;
it is additional to the authored-file counts. Repository administration files
were inspected separately. JSON schemas, fixture data, dependency declarations,
policy assets, license text, and third-party notices were preserved.

## Contract improvements

- **Preservation and interpretation:** distinguish copied bytes from metadata,
  verified input from authorization, canonical identity from title similarity,
  and supplied attachments from unresolved references. Selected attachments
  remain whole files; their internal contents are not redacted.
- **Resource bounds:** distinguish bounded payload buffers from decoded JSON,
  inventory, sorting, and graph costs. Comments identify the relevant inputs
  rather than implying constant total memory or a measured speed improvement.
- **Storage and publication:** explain caller ownership, no-replacement
  publication, cleanup error propagation, process recovery, and the limits of
  power-loss durability. SQLite transaction ownership is explicit; a deferred
  transaction does not enforce read-only access.
- **Access and execution:** distinguish immutable records from current
  authorization, acceptance from exact-plan review, cancellation requests from
  publication decisions, and terminal operation status from executor cleanup
  and reservation release.
- **Integration and interface:** document initialization side effects, worker
  lifespan, token rejection filters, cryptographic verification, browser-session
  boundaries, streaming revalidation, stale-response handling, and retry identity.
- **Validation evidence:** distinguish direct application calls, in-process ASGI
  tests, synthetic browser hosts, real loopback HTTP, installed distributions,
  and an actual ChatGPT connection. Benchmark comments distinguish traced
  allocations from process RSS and sampled disk observations from proven peaks.

The project does not currently implement model inference or training. Comments
do not imply such behavior or use model output as preservation, identity, or
authorization evidence.

## Preservation checks

The review checked the following properties against the baseline:

1. All **92 Python files** parsed and compiled. Their executable abstract syntax
   trees were identical after removing module, class, and function docstrings
   and normalizing source-line positions in `TypeIgnore` entries. This comparison
   includes type-comment content; it does not claim that edited docstrings have
   identical introspection values.
2. All **22 exposed MCP tool/resource docstrings** remained byte-for-byte
   unchanged. These descriptions are framework-consumed interface metadata,
   not merely source commentary.
3. All **13 JavaScript/TypeScript/MJS files** and both CSS files produced the
   same normalized code through the installed `esbuild` transformer with
   comments removed. Both authored HTML templates were unchanged after removing
   comments and blank lines.
4. The regenerated HTML had the same document elements, attributes, significant
   text, normalized script, and normalized stylesheet. Comment nodes and
   whitespace-only text were excluded from that comparison.
5. TOML and YAML parsed values were identical. The systemd and nginx directives
   were identical after excluding comments and blank lines.
6. **23 protected files** were byte-identical, including source licensing and
   attribution, dependency and TypeScript configuration, legal/policy assets,
   schemas, examples, and existing benchmark results.

These checks support the narrow scope of this review. They do not establish
new platform compatibility, legal enforceability, deployed identity-provider
behavior, or production capacity.

## Executed local validation

Validation ran on Linux with CPython **3.12.14** and Node.js **24.22.1**.

| Check | Observed result |
| --- | --- |
| Complete Python suite, including optional service dependencies | 331 passed; zero skips; 4.797 seconds |
| UI DOM and component suite | 28 passed; zero skips; 1.686704446 seconds |
| TypeScript checking and normal UI build | Passed |
| Python compilation and baseline AST comparison | 92 files passed |
| Wheel build with setuptools 84.2.1 | Passed without dependency resolution or build isolation |
| Packaged source and assets | All 57 packaged files matched the current source bytes |

Commands from the repository root:

```sh
PYTHONPATH=src python -m unittest discover -s tests -q
python -m pip wheel --no-deps --no-build-isolation --no-index . --wheel-dir dist/comment-review
git diff --check
```

Commands from `ui/chatgpt`:

```sh
npm run build
npm test
```

The Python suite emitted dependency warnings about Starlette's TestClient/httpx
transition and a Pydantic settings forward reference. Neither warning caused a
test failure. The installed dependency versions were not changed in this review.

The browser suite and synthetic HTTP workflow are exercised by the existing
GitHub Actions workflow. Their result must be read from the workflow attached to
the pushed commit; the local results above do not claim another local browser or
HTTP execution. Earlier CI observations remain in the
[private pilot validation record](private-pilot-validation.md).

### Regenerated distribution

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `src/keepmorrow/integrations/chatgpt/assets/keepmorrow.html` | 690,131 | `c1a8bfd6bf20dbbbd340aca4c36c2b3f97aa0d178d629a519f5a145b44aa444e` |
| `dist/comment-review/lpx_keepmorrow-0.3.0-py3-none-any.whl` | 356,312 | `6e391f1a83104686af02db70b6d5e4db054be68c15b954fe5ceb7b932bca1746` |

The wheel digest identifies this particular build, not every wheel built from
the same source. Earlier distribution and pilot hashes remain historical
evidence for their named artifacts. No performance benchmark was rerun, and
this review makes no performance-improvement claim.

## Existing implementation follow-ups

**Subsequent resolution:** The behavioral change documented in
[consent and cleanup verification](consent-cleanup-verification.md) implemented
the deadline presentation and binding, reproduced the cleanup failure, and
corrected its classification. The observations below retain the evidence
available during this earlier comment-only review.

The source review identified two boundaries that require separate behavioral
work or live qualification. Neither was introduced or fixed by this change.

### Consent expiration presentation

The portal's preparation response supplies the policy, resource, generation,
actions, purpose, recipient, and eligibility requirements. It does not currently
supply the acceptance expiration timestamp for the preacceptance display.
Expiration is enforced, and the accepted response exposes it. The
[delivery plan](../architecture/chatgpt-delivery-plan.md) now records the missing
preacceptance presentation as a qualification item rather than claiming it is
already displayed.

### Cleanup metadata errors

`OperationWorkspaces.discard` classifies filesystem and ownership failures as
`OperationCleanupRequired`. The worker retains the reservation and stops new
claims for that classification. The initial cleanup-ledger read and final
ledger deletion use transactions outside that exception wrapper, so metadata
errors propagate separately.

Source inspection identified a possible reservation release if the initial
cleanup-ledger read fails transiently and later worker database calls recover,
while workspace cleanup remains unresolved. This is a **source-level finding,
not a reproduced failure**. Existing filesystem/ownership tests do not establish
the behavior of this metadata-error sequence.

Follow-up qualification should inject transient and persistent failures at both
ledger boundaries and verify reservation retention, stopped admission, preserved
ownership evidence, and restart recovery before broadening the cleanup guarantee.
See the [workspace implementation](../../src/keepmorrow/application/staging.py)
and [operation protocol](../architecture/operation-journal.md).

## Release scope

The README retains a concise explanation of native export as supplied input and
Keepmorrow's preservation/recovery workflow. All three comparison/scoring tables,
their score rubric, and weighted totals were removed. The separate product
comparison document remains available for detailed background.

This review does not adopt a replacement source license, publish private Git
history, or establish a live ChatGPT installation. The
[open-source transition record](../governance/open-source-transition.md) remains
the authority for unresolved publication decisions.
