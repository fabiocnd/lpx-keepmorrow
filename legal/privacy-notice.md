# LPX Keepmorrow Privacy Notice

**DRAFT FOR OWNER AND QUALIFIED ONTARIO COUNSEL REVIEW**  
**Privacy notice version:** `2026-11-12-draft.1`  
**Prepared:** 2026-11-12  
**Production effective date:** Not assigned

This draft describes the local reference application and proposed privacy
commitments for a reviewed release. It is not an approved production notice or a
certification of compliance. Future delivery models must be assessed before
their processing starts.

## 1. Who Is Responsible

Lopix Neural Inc. publishes and maintains LPX Keepmorrow. Privacy questions and
requests may be directed to the Company, attention Fabio de Sousa Lopes, at
[fabio@lopixneural.com](mailto:fabio@lopixneural.com). A production release must
identify the person accountable for privacy operations and provide an accessible
request process.

The application currently runs in the environment chosen by the operator. The
Company does not automatically receive its source files, archives, or command
output. When the Company separately receives information, such as a support
message, it is responsible for handling that information as applicable law
requires. The legal role of each participant must be reassessed for any hosted or
integrated version.

## 2. Information Handled by the Local Application

| Information | Purpose and location |
| --- | --- |
| Selected file contents, including personal or confidential information they contain | Read locally to copy, hash, verify, or recover the material requested by the operator. |
| Relative file and directory names, byte counts, hashes, and archive format fields | Written in the local manifest to describe the archive and support integrity checks. Names can reveal private information. |
| Temporary file metadata and buffered bytes | Used in the running process and staging directory to perform and check the requested operation. |
| Operation results, errors, and affected paths where reported | Returned locally so the operator can assess success and problems. A terminal, shell, or surrounding application may separately retain this output. |
| Accepted document versions, UTC acceptance time, and requested operation | Returned as local acceptance metadata for the current CLI invocation. This does not identify or authenticate the person who supplied the command. |

The current application has no model inference, application network requests,
automatic telemetry, account tracking, or automatic upload to the Company.
Reading or copying a file can still cause activity by the operating system,
security software, backups, or independently configured synchronization tools.
Choose the execution environment and destination with those settings in mind.

The local archive format does not encrypt content or conceal filenames. Hashes
help detect inconsistency; they do not anonymize the archive or authenticate its
publisher. Protect archives and manifests according to the sensitivity of their
contents.

## 3. Purposes and Your Choices

The core purpose is to perform the specific local archive, verification, or
restore operation that you request. The application must obtain the required
document acceptance before inspecting selected data. You can decline and leave
the operation unstarted.

Acknowledging this notice and authorizing the necessary local operation is
separate from agreeing to additional uses. It does not authorize the Company or
developer to use your content for model training, promotion, advertising, or
unrelated analysis. The current application provides none of those features.

If another person's information is included, consider whether you have authority
to process it for this purpose. Your acceptance does not override that person's
rights or applicable confidentiality obligations.

## 4. Retention and Removal

| Location or record | Current handling and control |
| --- | --- |
| Original source material | Remains in its original location. The reference application provides no source-deletion operation. The source owner or provider controls its retention. |
| Completed local archive or recovered directory | Remains in the chosen destination until the operator removes it through storage tools. There is no automatic archive expiration in this release. |
| Temporary staging files | Normal operation attempts cleanup after completion or handled failure. Abrupt termination or device failure can leave remnants requiring operator review. Cleanup is not a secure-erasure guarantee. |
| CLI acceptance metadata and other command output | Not sent to a server or stored in an automatic consent database. It remains wherever the operator, shell, or surrounding system retains output. |
| Independently synchronized, shared, or backed-up copies | Governed by the chosen environment and provider. Removing one copy does not establish that every copy has been removed. |
| Information separately received by the Company | Must be subject to a documented purpose-based retention schedule, applicable legal retention requirements, and a removal process before production operation. No arbitrary fixed period is promised by this draft. |

If the Company receives information for support, it should retain only what is
needed to handle the request and any applicable legal obligation. A legal hold
or required incident record may justify retaining a limited record after a
request is otherwise complete. Production procedures must identify the category,
purpose, retention trigger, review responsibility, and removal method rather than
using an indefinite general retention statement.

## 5. Access, Withdrawal, and Privacy Requests

You control whether to initiate another local operation. Declining a later
invocation prevents that invocation; it does not reverse a completed copy.
Review your storage tools to remove local archives or other copies you control.

For information held by the Company, contact the address above to request access,
correction, withdrawal of consent, or removal as available under applicable law.
The Company may need proportionate information to verify and fulfill a request
without exposing someone else's information. It must explain an applicable legal
restriction or required retention rather than representing every request as an
unconditional deletion right.

The Company cannot directly erase data on a device or service it does not control.
Where another provider controls a copy, its own request process may be relevant.
You retain the right to contact a competent privacy regulator; a Company support
exchange is not a waiver of that right.

## 6. Security and Residual Risks

Access controls, encrypted storage where appropriate, device maintenance, and
independent backups remain relevant to local archives. Application integrity
checks address a narrower question: whether the examined archive agrees with its
manifest at verification time. They do not guarantee confidentiality, source
completeness, immunity from malware, or recovery after every storage failure.

Private content can remain in outputs, filenames, backup copies, logs created by
other tools, or storage remnants. Selecting a shared destination can expose it
to others with access. Incomplete exports and unsupported native relationships
can reduce the usefulness of recovered structures even when copied bytes match.
Use a separate destination and assess recovery before removing an independent
source copy.

If information controlled by the Company is involved in a security incident, the
Company must investigate and meet applicable assessment, recordkeeping, reporting,
and notification obligations. Acceptance of this notice does not release the
Company or Fabio de Sousa Lopes from legal duties that apply to them.

## 7. Future Cloud, AI, and Other Recipients

This draft does not authorize a future cloud or AI integration. Before enabling
one, the Company must identify the selected information, actual recipient,
purpose, relevant processing location, provider retention and reuse terms,
deletion limits, and material consequences. Optional uses require a separate,
unselected-by-default choice; a refusal must preserve access to the independent
local feature when that use is unnecessary for it.

No universal data-residency, international-compliance, or provider-deletion promise
is made. An operator's selection of a synchronized folder does not establish that
storage remains in Canada. New recipients or materially changed purposes require
review and the appropriate new consent before disclosure.

## 8. Changes

The application must make the applicable notice available when requesting
acceptance and preserve its version. Material privacy changes must be explained
before the affected operation. Keeping a draft version in a repository is not a
substitute for presenting understandable information to the people affected.
