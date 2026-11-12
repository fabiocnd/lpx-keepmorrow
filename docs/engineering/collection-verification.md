# Collection Verification Record

**Date:** 2026-11-12
**Version:** 0.2.0, private development
**Local environment:** Linux x86-64, CPython 3.12.14
**Policy versions:** `2026-11-12-draft.2`

This record separates executed checks from remaining release evidence. All
content fixtures and benchmark inputs are synthetic. No representative real
ChatGPT account export or private account connection was used.

## Local behavioral validation

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests benchmarks
```

The complete suite ran **168 tests**, with no failures or skips in the recorded
environment. Syntax compilation also passed. The optional installed SDK was
`mcp==1.29.0`; schema validation used `jsonschema==4.26.0`.

A separate standard-library execution excluded site packages:

```bash
PYTHONPATH=src python -S -m unittest discover -s tests -q
```

It discovered the same 168 tests, executed 153 successfully, and skipped the 10
SDK-dependent and five schema-dependent tests. The three registry tests still
executed. This establishes that the preservation and collection core does not
require the optional SDK to run.

## Executed scenarios

| Boundary | Observed coverage |
| --- | --- |
| Archive assembly | Single copy/hash source pass, independent staged verification, bounded generated entries, no-clobber publication, failure poisoning, and cleanup |
| ZIP intake | Bounded metadata and inflation, CRC, headers, overlapping records, paths, collisions, links, unsupported codecs, source mutation, and temporary extraction cleanup |
| Import profile | Namespaced source identity, stable record revisions, null roots, branches, provenance, explicit project evidence, missing artifacts, and unknown-field preservation |
| JSON handling | Pre-decode byte/depth/token budgets, strict key and number handling, malformed structures, and controlled failure |
| Collection | Immutable extension, repeated occurrences, original ZIP retention, manifest-bound inventory, graph cross-references, and explicit association history |
| Query and recovery | Bounded literal search and pagination, corrupt-byte refusal, selected graph records and exact bound files, and exclusion of whole recognized source JSON and ZIP containers |
| Consent | Exact current policies, refusal before content access, operation scope, and distinct accepted-but-failed outcomes |
| HTML | Escaping, restrictive content policy, exact inventory links, no source markup activation, and visible partial scope |
| MCP | Real SDK initialization and calls, in-process Streamable HTTP, opaque grants, consent before I/O, request/response bounds, sanitized errors, host rejection, busy admission, and cancellation ownership |
| JSON Schema | Draft 2020-12 schema validation and real generated full, selected, associated, and unsupported collections |

The paired export fixtures establish four logical conversations, five distinct
revisions, six capture occurrences, 16 graph nodes, one branched revision, two
source-confirmed projects, and explicit unknown associations. Binary checks use
a valid PNG and opaque non-UTF-8 byte fixtures; executable filename extensions
are tested without executing their contents.

These tests establish behavior for the documented experimental profile. They do
not establish that current provider exports always contain that profile or all
requested account content.

## Remote CI evidence

The workflow contains four standard-library jobs on Ubuntu and Windows with
Python 3.11 and 3.14, and one optional MCP/schema job on Ubuntu/Python 3.12.
The optional job installs the recorded constraints from
`requirements/chatgpt-dev-py312.constraints.txt`.

Remote results for this version are pending upload and observation. No result
from the historical 0.1.0 workflow is attributed to this implementation. This
section will be updated with the inspected commit, run, and individual outcomes.

## Measured collection workload

The [benchmark report](../../benchmarks/COLLECTION_BENCHMARK.md) and its
[raw samples](../../benchmarks/results/2026-11-12-collection-reference.json)
record 100 logical conversations, two captures, 150 revisions, 200 occurrences,
and 2,050 graph nodes over three repetitions. The first input is a directory;
the second is a ZIP. Supplemental checks verified 24 exact binary hashes,
expected counts, deterministic manifests, unchanged parents, and selected scope.

| Stage | Median elapsed seconds | Maximum Python-traced peak bytes |
| --- | ---: | ---: |
| Initial import | 0.617440 | 4,893,062 |
| Extend generation | 1.051870 | 11,318,444 |
| Verified catalog and search | 0.369093 | 4,491,014 |
| Selected recovery | 0.412937 | 4,491,464 |

The source aggregate recorded before and after that run was
`d9789f2f86ea858bca6255cbde1ff12e55b56228a23fef108ed17054e4deac44`.
The report identifies the contributing files individually. These are worktree
hashes, not a claim about an uninspected remote commit.

The wide-branch diagnostic measured 1,000 and 4,000 children, with a median time
ratio of 3.97. It helps inspect the removed repeated linear child-membership
scans; it does not prove an asymptotic result or a speedup against a prior
measured implementation.

Timings include `tracemalloc` overhead and warmed filesystem caches. Traced peaks
are not process RSS. Storage medium, CPU quota, production corpus sizes, Windows
performance, and tail latency were not characterized. Physical copies between
generations and full-byte verification before queries remain explicit costs.

## Known evidence limits

- The source interpreter is experimental until representative real exports are
  authorized and checked against independent expectations.
- HTML structural and security tests passed. A browser-rendering attempt was
  blocked by the available browser sandbox; no visual browser QA is claimed.
- The optional MCP adapter is loopback-only and was tested with local SDK
  clients. It is not remotely authenticated, deployed, installed, or tested in
  an actual ChatGPT account. No embedded ChatGPT component is implemented.
- SDK initialization emitted a non-failing upstream settings forward-reference
  warning for `lifespan` in the recorded local environment. Protocol tests still
  executed; no upstream source was modified to suppress it.
- Selective recovery excludes whole recognized conversation JSON containers,
  but arbitrary selected binary content is not universally redacted.
- Source stability checks are not a filesystem snapshot or a defense against
  hostile concurrent ancestor replacement. Atomic publication is not an
  `fsync` crash-durability guarantee. Durable resume is not implemented.
- Hashes verify consistency with a supplied manifest; they do not authenticate
  its publisher. Consent receipts record local declarations rather than
  authenticated legal assent. The legal documents remain drafts.
- No model inference, cloud archive storage, automatic account enumeration,
  native ChatGPT restoration, source deletion, or public release was performed.

## Source delivery

The intended destination is the existing private repository
[fabiocnd/lpx-keepmorrow](https://github.com/fabiocnd/lpx-keepmorrow). Source upload,
remote tree equality, current visibility, and remote execution will be recorded
after their results are observed.
