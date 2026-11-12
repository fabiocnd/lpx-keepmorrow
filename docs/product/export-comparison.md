# Keepmorrow and Official ChatGPT Data Export

**Review date:** 2026-11-12
**Product:** LPX Keepmorrow
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

| Need | Official export | Keepmorrow's current local milestone |
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

## Where the product should demonstrate value

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
  extension copies prior payloads; physical deduplication and resumable storage
  jobs are not implemented.
- A ChatGPT interface exposes backend operations through an authorized adapter.
  Local functionality does not establish a hosted, installed, account-wide
  integration or permission to modify provider data.

Keepmorrow's defensible distinction is the continuity, evidence, and verified
recovery it provides for supplied work. Every product claim must identify the
implemented version, its supported inputs, and the evidence behind the claim.

[official-export]: https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data
[edu-export]: https://help.openai.com/en/articles/20001279-exporting-data-from-a-chatgpt-edu-workspace
[conversation-transfer]: https://help.openai.com/en/articles/9106926-transfer-exported-conversations-between-chatgpt-accounts
