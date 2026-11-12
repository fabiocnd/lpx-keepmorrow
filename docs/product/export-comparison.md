# Keepmorrow and Official ChatGPT Data Export

**Review date:** 2026-11-12
**Product:** LPX Keepmorrow 0.3.0
**Publisher:** Lopix Neural Inc.

Official ChatGPT export supplies a copy of eligible platform data. Keepmorrow
builds a local, verifiable collection from material the user supplies, retaining
multiple captures, logical revisions, evidence-based associations, and available
files. The export can be an input to Keepmorrow.

For a user who only wants an occasional downloaded copy, **official export may
be sufficient**. A second ZIP wrapper or another conversation viewer would not,
by itself, demonstrate a meaningful product advantage.

## What the official documentation establishes

The [general export documentation][official-export] describes a ZIP containing
chat history and other relevant account data. It directs the user to inspect the
download and does not provide a universal guarantee that every image, generated
binary, attachment, or original project structure is included.

The [ChatGPT Edu export documentation][edu-export] explicitly says that a ZIP can
include files and other assets used in conversations, as well as conversation
JSON and metadata. It also documents an export viewer for searching and reading
included conversations. That description belongs to the Edu workflow; it should
not be generalized into an unsupported statement about every plan.

The [conversation transfer documentation][conversation-transfer] explains that
uploaded exported conversations can serve as reference in a new chat. This does
not recreate previous conversations as separate chats or restore the original
sidebar. Keepmorrow also does not recreate native ChatGPT chats or Projects.

These sources do not justify claiming that official export excludes images,
contains only unstructured text, or lacks all reading and search facilities.
They also do not establish the exact contents of a particular user's ZIP.

## Current implementation and practical distinction

| Need | Official export | Keepmorrow 0.3.0 |
| --- | --- | --- |
| Obtain eligible account data | The platform prepares the requested export. | Accepts explicitly supplied directories or supported ZIPs; it does not enumerate the account. |
| Preserve downloaded content | The downloaded package can be retained using ordinary storage. | Preserves source files, raw ZIP containers, empty directories, and byte inventories with SHA-256. |
| Interpret conversations | Conversation JSON is available in the documented transfer workflow. | An experimental mapping adapter recognizes declared JSON shapes; real-account compatibility has not yet been validated. |
| Retain repeated captures | The user can keep each downloaded export. | Keeps each capture occurrence and reconciles logical conversations and complete-record revisions within a named account namespace. |
| Preserve project evidence | The actual export must be inspected for the relevant metadata. | Recognizes the supported `project_id` field, preserves unknown association states, and records explicit local classification decisions separately. |
| Handle images and binary files | Files/assets are explicitly documented for Edu; general documentation does not guarantee every original binary in every export. | Preserves supplied bytes independently of file type. Reference-to-file binding requires explicit supported evidence; missing or unresolved media remains visible. |
| Read and search | A viewer with search is documented for Edu. | Provides a passive local HTML view and bounded literal catalog search across retained revisions. |
| Recover a selected subset | The user can use the downloaded data outside ChatGPT. | Packages selected derived conversation records and exact bytes of bound artifacts, with a verified inventory. |
| Recreate native ChatGPT state | The documented upload workflow does not restore separate chats or the original sidebar. | Native restoration is not implemented. |

The complete source contract, statuses, resource limits, and selective-recovery
qualifications are recorded in [Import and Collection Contract v1](../architecture/import-contract.md).

## Subjective engineering assessment

The following scores express the maintainers' judgment of **fit for a specified
workflow**, using the reviewed documentation and implemented contracts. They are
proposed product-assessment scores, not measured quality, performance, reliability,
or user-study results. OpenAI does not assign or endorse these scores.

The compared workflows are:

- **Native export + manual files:** request and retain official exports, organize
  their files with ordinary storage tools, use any documented viewer available
  for the eligible account, and perform additional reconciliation or checking
  manually. This gives credit to achievable manual workflows.
- **Keepmorrow:** obtain the same eligible source exports, then run the implemented
  preservation application on explicitly supplied, supported inputs. This adds
  setup and operational responsibility. A deployed ChatGPT connection and
  representative real-export compatibility are still unverified.

The 0–5 scale is anchored to the particular criterion: **0** means no identified
usable path; **1**, an early or unqualified path; **2**, a workable path requiring
substantial manual work or additional setup; **3**, a repeatable path with material
limitations; **4**, a strong dedicated mechanism within its stated scope; and
**5**, an established direct workflow well matched to that criterion. The same
score does not establish equal implementations. A missing description in the
reviewed articles does not establish that a native capability is absent.

| Criterion | Native export + manual files, 0–5 | Keepmorrow, 0–5 | Reason for the proposed judgment |
| --- | ---: | ---: | --- |
| Acquisition and convenience | 5 | 2 | [Official export][official-export] is the direct documented acquisition path for eligible accounts. Keepmorrow requires that input plus installation, storage, scope acceptance, and an additional import. The 5 does not imply immediate delivery or universal plan eligibility. |
| Repeated captures and revisions | 2 | 4 | Separate export folders retain snapshots but require manual reconciliation in this baseline. Keepmorrow implements namespaced source identity, capture occurrences, distinct revisions, and immutable generations; support remains limited to its experimental profile. |
| Evidence for project associations | 2 | 4 | The actual native export can contain useful metadata, which can be inspected manually. Keepmorrow represents supported source evidence, unknown associations, and reviewed local decisions explicitly. It cannot invent missing membership or attest native project state. |
| Integrity verification and recovery evidence | 2 | 4 | An export can be retained and supplemented with manual checksum and recovery checks. Keepmorrow integrates byte inventories, hashes, independent verification, generation binding, and publication checks. This score does not assess OpenAI's internal or transport safeguards; Keepmorrow hashes also do not authenticate the source or prove complete account coverage. |
| Selective recovery | 2 | 4 | [Official transfer guidance][conversation-transfer] permits using selected exported conversations as reference; manual selection remains possible. Keepmorrow creates a verified selected derivative with bound artifacts and explicit omissions. It does not restore native chats or redact arbitrary attachment contents. |
| Preservation of supplied binary files | 4 | 4 | Both workflows can retain the binary files actually present. [Edu explicitly documents files/assets][edu-export], and actual contents require inspection. Keepmorrow preserves accepted supplied bytes and reports unresolved references; neither receives credit for recovering absent original bytes. |
| Current operational maturity | 5 | 1 | Official export is an available platform workflow described by [current documentation][official-export]. Keepmorrow has synthetic tests and a local service benchmark, while live account, real-export, deployment, browser, and legal gates remain open. This is a readiness judgment, not an independent audit of either service. |

### The result changes with the task

The same criterion scores are weighted in two ways. Weights total 100 in each
column and are visible so a reader can replace them with their own priorities.

| Criterion | Ongoing preservation weight | Occasional backup weight |
| --- | ---: | ---: |
| Acquisition and convenience | 10 | 30 |
| Repeated captures and revisions | 25 | 5 |
| Evidence for project associations | 10 | 0 |
| Integrity verification and recovery evidence | 20 | 10 |
| Selective recovery | 15 | 5 |
| Preservation of supplied binary files | 10 | 20 |
| Current operational maturity | 10 | 30 |

The score out of ten is `sum(weight × criterion_score) / 50`.

| Intended workflow | Native export + manual files | Keepmorrow | Interpretation |
| --- | ---: | ---: | --- |
| Ongoing preservation across repeated captures | **5.6 / 10** | **7.0 / 10** | This weighting favors explicit revisions, evidence, and verified selection—the intended value of Keepmorrow's implemented mechanisms. |
| Occasional downloaded backup | **8.4 / 10** | **5.0 / 10** | This weighting favors direct acquisition, existing availability, and retaining supplied files; ordinary export storage has the practical advantage. |

These are conditional preference summaries. For example, changing the repeated
captures score by one point changes the ongoing-preservation result by 0.5 points
out of ten. A higher weighted fit does not complete a missing release gate or
authorize production use. The [measured service benchmark][service-benchmark]
uses synthetic inputs and has a separate purpose; none of its timings produced
the scores above. No timed native-export comparison has been performed.

## Where the product should demonstrate value

Keepmorrow is interesting when the user's work changes over time and the question
extends beyond obtaining a ZIP: **which supplied capture contains this revision,
which branch and files belong with it, what evidence supports its organization,
and can the selected result be verified after recovery?** Its implemented answer
combines preserved originals, declared identity rules, uncertainty, and verified
recovery in one inspectable workflow.

For example, two exports may contain the same source conversation ID under
different titles, with a later branch and a supplied image. Keepmorrow can retain
both occurrences, distinguish revisions, preserve the branch graph, and recover
a selected revision with the available, explicitly bound image. A referenced
spreadsheet whose bytes were never supplied remains unresolved. This is useful
traceability within the supported profile; it does not establish that the
platform exported every item or that local structure recreates native Projects.

Project-owned source in this revision uses Apache License 2.0. The historical
development repository stays private; public distribution uses a reviewed source
snapshot with a fresh root commit. Source licensing, actual public publication,
and hosted-service qualification are separate decisions and evidence gates.
The maintained product's free direction does not restrict downstream rights.

The useful test is whether someone can preserve and recover an evolving body of
work with less ambiguity and less manual effort. A representative validation
scenario should include two authorized exports, a renamed conversation, new
messages, a branch, a supplied binary artifact, and a referenced artifact whose
bytes are absent.

Keepmorrow should preserve the original bytes, retain logical identity where
source identifiers justify it, preserve distinct revisions and branches, report
unsupported or missing content, and recover the selected material with matching
file hashes. Synthetic tests establish these behaviors for the supported
profile. They do not establish universal export compatibility or superiority
over a user's existing backup process.

The next compatibility decision requires an authorized representative real
export. Compare its actual files and structures with the profile, record every
unsupported case, and measure the time and steps required for the same recovery
using ordinary export folders. User archives must not be committed as test data.

## Boundaries that apply to the comparison

- A complete received file, a thumbnail, a filename, an asset identifier, and a
  download URL are different forms of evidence. A reference alone is not a
  preserved original.
- Matching file hashes establish consistency with the supplied manifest. They
  do not authenticate the publisher or prove that every account asset was
  supplied.
- A source that never supplied an image or binary gives Keepmorrow no bytes to
  recover. The application does not reconstruct missing originals with AI.
- Selected packages omit known whole conversation JSON documents and raw export
  ZIPs. Selected arbitrary attachments remain intact and are not universally
  content-redacted.
- Repeated captures are preserved in separate immutable generations. Current
  extension copies prior payloads; physical deduplication and resuming a byte copy
  at its interruption offset are not implemented. The private service does record
  durable operation state and reconcile interrupted attempts.
- A ChatGPT interface exposes backend operations through an authorized adapter.
  Local functionality does not establish a hosted, installed, account-wide
  integration or permission to modify provider data.

Keepmorrow's defensible distinction is the continuity, evidence, and verified
recovery it provides for supplied work. Every product claim must identify the
implemented version, its supported inputs, and the evidence behind the claim.

[official-export]: https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data
[edu-export]: https://help.openai.com/en/articles/20001279-exporting-data-from-a-chatgpt-edu-workspace
[conversation-transfer]: https://help.openai.com/en/articles/9106926-transfer-exported-conversations-between-chatgpt-accounts
[service-benchmark]: ../../benchmarks/PRIVATE_SERVICE_BENCHMARK.md
[open-source-transition]: ../governance/open-source-transition.md
