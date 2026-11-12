# Decision Register

**Recorded:** 2026-11-12
**Owner:** Fabio de Sousa Lopes
**Publisher:** Lopix Neural Inc.

Status values: **owner-confirmed**, **implementation choice**, **proposal**,
**open**, and **historical**. An implementation choice is reviewable engineering
work, not a claim that the owner separately approved a permanent stack.

| ID | Decision | Status | Basis and consequence |
| --- | --- | --- | --- |
| D001 | Use LPX Keepmorrow and technical slug `lpx-keepmorrow` | Owner-confirmed | Naming adoption in Blueprint v0.2 |
| D002 | Keep persistent authored project content in US English | Owner-confirmed | Original and current language instructions; preserve imported original bytes in their source language |
| D003 | Keep the product free and nonmonetized | Owner-confirmed | Earlier product direction remains in force |
| D004 | Attribute publisher Lopix Neural Inc. and creator Fabio de Sousa Lopes | Owner-confirmed | Explicit ownership and visibility instruction |
| D005 | Create a private proprietary GitHub repository | Owner-confirmed | Current instruction resolves source availability for this repository |
| D006 | Use fabio@lopixneural.com for project contact and commit author identity | Owner-confirmed | Current email instruction; no mailbox validation implied |
| D007 | Apply Golden Coding Standard to documentation, code, comments, algorithms, and AI work | Owner-confirmed | Current quality instruction; project policy, not an external certification |
| D008 | Reevaluate performance and group folders by responsibility | Owner-confirmed | Current organization instruction |
| D009 | Require user acceptance before processing | Owner-confirmed | Current legal/consent instruction; scope-specific permissions remain separate |
| D010 | Draft protections for company and developer within applicable law | Owner-confirmed | Terms cannot waive mandatory obligations or authorize undisclosed retention/destruction |
| D011 | Use Python 3.11+ standard library for a small local reference core | Implementation choice | Minimizes setup and runtime dependencies; production runtime remains reviewable |
| D012 | Use a versioned directory snapshot for the first verifiable slice | Implementation choice | Makes byte preservation, manifest inspection, and recovery independently testable |
| D013 | Keep model assistance outside deterministic preservation | Working baseline | Blueprint architecture and current engineering requirements |
| D014 | Use `fabiocnd` as the repository owner | Implementation choice | Authenticated account verified; no installed organization was listed |
| D015 | Leave Google Drive as a storage-adapter candidate | Proposal | No provider integration or permission flow has been approved or implemented |
| D016 | Publish or distribute the product | Open | Separate owner decision after engineering, privacy, and legal review |
| D017 | Production hosting, retention, telemetry, and model provider | Open | Must be specified before relevant data processing is enabled |
| D018 | Treat the retrieved Blueprint as a historical source snapshot | Implementation choice | Preserve its original open decisions while recording superseding instructions here |
| D019 | Implement the recent preservation and product-differentiation recommendations | Owner-confirmed | Owner requested senior engineering refactoring and implementation after reviewing official export, binary, and image coverage |
| D020 | Use immutable collection generations over the existing archive contract | Implementation choice | Preserve previous outputs, keep originals distinct from derived catalogs, and expose full-copy costs; see ADR 0002 |
| D021 | Treat the ChatGPT mapping adapter as experimental until a representative real export is validated | Implementation choice | Synthetic compatibility evidence exists; no real account export has been supplied |
| D022 | Add a read-only local MCP development adapter with explicit grants | Implementation choice | Supports the intended ChatGPT integration boundary without deployment, unrestricted history access, or premature write tools |
| D023 | Revise legal drafts to version 2026-11-12-draft.2 for the changed local processing scope | Implementation choice | Catalogs, search results, association decisions, ZIP preservation, selection, and local MCP handling require accurate disclosure and fresh exact acceptance |
| D024 | Deliver a synthetic account connection, then an authenticated private read-only pilot, before remote writes | Proposal | Owner requested a senior delivery plan on 2026-11-12; the [plan](../architecture/chatgpt-delivery-plan.md) defines evidence gates and provisional effort, not a deployment approval or completed capability |
| D025 | Require server-recorded human acceptance and per-principal object grants before real connected content | Proposal | Current model-supplied version declarations do not establish human assent or authenticated authorization; the CLI contract remains unchanged |
| D026 | Review plugin content eligibility before promising full-history ingestion | Proposal | Current platform guidelines restrict certain data categories; retain originals under owner control and evaluate separately reviewed eligible selections without assuming an exemption |

## Superseded historical items

Blueprint v0.2 left source licensing open. D005 now establishes private,
proprietary source. The free product direction remains unchanged.

The Blueprint left implementation language open. D011 selects only the local
reference implementation, not a permanent production architecture.

Draft terms are preparatory documents. Their inclusion in a private repository
does not establish legal approval, public availability, or an effective contract
with end users.

## Change discipline

Record the decision, date, evidence, status, rationale, and consequence.
Material architecture choices also receive an
[architecture decision record](../architecture/decisions/0001-repository-layout.md).
Do not overwrite historical evidence to make it appear that a proposal was
always an accepted decision.
