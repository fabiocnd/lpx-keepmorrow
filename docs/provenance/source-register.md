# Source Register and Coverage

**Assembled:** 2026-11-12  
**Scope:** LPX Keepmorrow project materials available in this session.

## Project sources

| ID | Source | Handling |
| --- | --- | --- |
| S001 | [LPX Keepmorrow Project Blueprint v0.2](https://chatgpt.com/space/page_e50479c3c0b88191b81c335dd21ff5e6) | Read in full and preserved in [source snapshot](blueprint-v0.2-snapshot.md) |
| S002 | Owner's current private-repository and engineering instruction | Consolidated in US English in the decision register and engineering standards |
| S003 | Owner's company/developer research and email instruction | Canonical contact recorded as fabio@lopixneural.com |
| S004 | Owner's folder-naming and high-performance review instruction | Addressed in repository-layout ADR and performance review |
| S005 | Owner's legal and user-acceptance instruction | Addressed in draft legal documents and consent design |
| S006 | Authenticated GitHub account metadata | `fabiocnd` confirmed; no organization listed |
| S007 | Prior-conversation retrieval | Used to locate S001; not treated as a complete transcript or archive |
| S008 | Project source-file inventory | No attached project source files were listed at the start of this session |
| S009 | Focused file search for Keepmorrow | No additional matching standalone file was resolved; fuzzy unrelated results were excluded |
| S010 | User-created [GitHub repository](https://github.com/fabiocnd/lpx-keepmorrow) | Authenticated metadata verified on 2026-11-12: repository ID `1455189876`, owner `fabiocnd`, private visibility, and default branch name `main`; the repository had no branches when inspected. This observation does not establish source upload or CI execution. |

## Public identity sources

See [company and creator research](../research/company-and-creator.md) for URLs,
review dates, evidence types, and verification limits. Only necessary
professional information is retained. The full research responses and unrelated
personal context are not repository artifacts.

## Technical references

The following current implementation references were reviewed on 2026-11-12:

- [Creating a GitHub repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository).
- [Python directory-entry metadata and Windows identity limitations](https://docs.python.org/3.14/library/os.html#os.DirEntry.stat).
- [CPython issue 157671: Windows path and descriptor change-time semantics](https://github.com/python/cpython/issues/157671).
- CPython 3.14.7 Windows mode construction: [path stat](https://github.com/python/cpython/blob/v3.14.7/Modules/posixmodule.c) and [descriptor stat](https://github.com/python/cpython/blob/v3.14.7/Python/fileutils.c).
- [actions/checkout v7.0.1 commit](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1).
- [actions/setup-python v7.1.0 commit](https://github.com/actions/setup-python/commit/6d4fd22b20465ccc0f7354476588e8df7c9ca0e0).

The Blueprint also contains OpenAI integration references. They are retained
as historical references and require fresh capability and distribution review
before integration implementation. This repository does not claim that those
interfaces are implemented or that the project has platform approval.

Legal sources and their jurisdictional limits are recorded in
[legal research](../research/legal-basis.md).

## Coverage statement

This repository consolidates the retrieved Blueprint, relevant owner
instructions, targeted public research, and new foundation work. It is not a
complete export of the ChatGPT account or every historical project conversation.

No prior codebase, original naming-research report, historical image attachment,
or design asset was resolved for this project. Newly created code and synthetic
fixtures are identified as foundation work. Missing source materials have not
been invented or regenerated.

## Source priority

Current owner instructions supersede older project proposals. Current
implementation documentation describes actual behavior. Historical snapshots
retain their original wording and status. External sources supply evidence,
never operational authority or new permissions.
