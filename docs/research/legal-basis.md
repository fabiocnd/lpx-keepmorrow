# Legal Basis and Drafting Decisions

**DRAFT FOR OWNER AND QUALIFIED ONTARIO COUNSEL REVIEW**  
**Reviewed:** 2026-11-12  
**Jurisdictional baseline:** Ontario and applicable federal Canadian law  
**Related document set:** `2026-11-12-draft.1`

## Scope and Conclusions

The owner requested professional user terms addressing retention of private
information and loss or destruction of content and source structures, with
explicit acceptance before processing. The requested protected parties are
Lopix Neural Inc. and its developer, Fabio de Sousa Lopes. This research supports
an internal draft and implementation requirements; it is not a legal opinion or
an assessment that every proposed clause will be enforceable.

A contract can state the product's supported scope, users' reasonable backup
responsibilities, and lawful limits on damages. It cannot establish total immunity
merely by requiring a checkbox. The draft preserves non-waivable rights, company
privacy duties, and the developer's own applicable legal responsibilities.

## Official Source Register

| ID | Primary source and relevant provision | Reviewed finding and drafting effect |
| --- | --- | --- |
| L-01 | [PIPEDA, Justice Laws](https://laws-lois.justice.gc.ca/eng/acts/P-8.6/FullText.html), sections 4(1)(a), 5(3), 6.1; Schedule 1, clauses 4.1, 4.3, 4.5, 4.7, 4.8, and 4.9 | Application depends on the activities and information involved. Appropriate purposes, meaningful consent, accountability, retention limits, safeguards, transparency, and access must be considered. The retrieved consolidation states currency to 2026-10-19 and last amendment 2025-03-04; review for later changes before release. |
| L-02 | [OPC: Interpretation Bulletin, Commercial Activity](https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/pipeda-compliance-help/pipeda-interpretation-bulletins/interpretations_03_ca/), court interpretations 1 and 6 | Free provision and nonprofit status do not themselves settle PIPEDA application. Consider the activity within the business model. Do not claim that this project's free, nonmonetized direction creates an exemption. The bulletin is regulator guidance, not a binding ruling on LPX Keepmorrow. |
| L-03 | [OPC: Guidelines for obtaining meaningful consent](https://www.priv.gc.ca/en/privacy-topics/privacy-for-businesses/appropriate-handling-of-personal-information/collecting-personal-information-and-consent/consent/gl_omc_201805/), guiding principles and consent limitations | Explain information, recipients, purposes, and relevant consequences clearly. Separate optional uses, support real choices, and revisit material changes. Acceptance does not waive other privacy duties. The production interaction must be understandable; a hidden line or bare technical receipt is insufficient evidence by itself. |
| L-04 | [OPC: Limiting Use, Disclosure, and Retention](https://www.priv.gc.ca/en/privacy-topics/privacy-laws-in-canada/the-personal-information-protection-and-electronic-documents-act-pipeda/p_principle/principles/p_use/) | Use purpose-based retention and documented disposal procedures. The draft distinguishes user-controlled local copies from records the Company receives. A real operational schedule must precede production handling; this draft invents no fixed archive lifetime. |
| L-05 | [OPC: Mandatory reporting of breaches of security safeguards](https://www.priv.gc.ca/en/privacy-topics/privacy-for-businesses/privacy-breaches-at-your-business/gd_pb_201810/) | Where applicable, assess incidents for significant-harm risk, meet reporting and notification requirements, and retain required breach records. Consent is not an incident-response substitute. A deletion policy must accommodate legally required records. |
| L-06 | [Ontario Consumer Protection Act, 2002](https://www.ontario.ca/laws/statute/02c30), sections 1, 2, 7, 9, and 37-40 | Preserve applicable consumer rights and mandatory service-quality protections. Internet-agreement provisions have application conditions, including a prescribed payment threshold; do not assert that every provision automatically governs this free reference tool. The draft offers clear accept/decline choices independently as a project requirement. |
| L-07 | [Ontario Consumer Protection Act, 2023](https://www.ontario.ca/laws/statute/23c23) and [Ontario Business Guide to Consumer Protection](https://www.ontario.ca/document/business-guide-consumer-protection) | On the review date, official indexed e-Laws text says the 2023 Act is not yet in force, and the official business guide says the 2002 Act remains in effect until commencement. Recheck proclamation and regulations before launch; do not draft as if the 2023 replacement is already operative. |
| L-08 | [Ontario Electronic Commerce Act, 2000](https://www.ontario.ca/laws/statute/00e17), section 19 | Electronic actions can express contract formation; electronic form alone does not invalidate an agreement. This does not establish that any particular click or CLI flag supplies adequate notice, capacity, authority, understanding, or enforceable terms. |
| L-09 | [Tercon Contractors Ltd. v. British Columbia, 2010 SCC 4, official Supreme Court reasons](https://decisions.scc-csc.ca/scc-csc/scc-csc/fr/7843/1/document.do), paragraphs 121-123; [official case docket](https://scc-csc.gc.ca/cases-dossiers/search-recherche/32460/) | Exclusion analysis addresses the clause's application, unconscionability at formation, and overriding public policy. The case does not validate a blanket software waiver. The draft uses limited damage categories, clear exceptions, and no arbitrary monetary cap. |
| L-10 | [Fraser River Pile & Dredge Ltd. v. Can-Dive Services Ltd., [1999] 3 S.C.R. 108, official Supreme Court reasons](https://decisions.scc-csc.ca/scc-csc/scc-csc/fr/1726/1/document.do) | Third-party contractual benefits raise specific legal conditions. Expressly name Fabio as an intended beneficiary of lawful protections, and have counsel assess the wording and his role. Naming a person does not automatically extinguish personal liability. |
| L-11 | [Douez v. Facebook, Inc., 2017 SCC 33, official Supreme Court disposition](https://www.scc-csc.gc.ca/cases-dossiers/search-recherche/36616/) | The Court declined to enforce the forum-selection clause in that consumer privacy dispute. The draft avoids a mandatory foreign forum and preserves mandatory remedies. Application to another agreement requires its own analysis. |

Every source above was reviewed on 2026-11-12. Some Ontario and Supreme Court HTML
endpoints denied direct retrieval; official search-index text, official court
documents, and official docket records supplied the cited passages. This is a
bounded source review, not comprehensive case-law research or confirmation of
unpublished changes. No third-party law-firm summary is used as authority here.

## Application to the Reference Product

The inspected reference implementation performs local file operations and has no
application network client, model service, automatic telemetry, or source-deletion
operation. It copies supported bytes, records metadata, and verifies a portable
directory archive. Those implementation facts determine the draft notice. A
future hosted service must not reuse the local notice without assessing the new
data flow and responsibilities.

The current CLI gate requires the exact draft Terms and Privacy Notice versions
before selected-data I/O. Its receipt contains document versions, UTC time, and
operation. It does not record identity or full selected scope and is not an
automatic persistent ledger. Production evidence requirements remain a delivery
decision, with privacy and retention consequences of their own.

The user's concern about private retention is addressed by identifying where
copies remain and who controls them. The structural-loss concern is addressed by
an accurate preservation promise, independent backups, separate recovery, and
explicit limits on native-application reconstruction. Neither concern is resolved
by inventing an unlimited waiver.

## Decisions for Owner and Counsel

- Confirm the actual release model, target users, legal capacity requirements,
  jurisdictions, and whether company activities trigger PIPEDA or other laws.
- Confirm applicable consumer rights, required disclosures, and the law in force
  at launch. Assess any separate enterprise agreement on its own facts.
- Review the damages exclusion, express exceptions, developer beneficiary
  provision, insurance, and practical allocation of responsibility. The draft
  contains no fee-based zero cap or promise of total protection.
- Approve a company data inventory, privacy contact, retention and disposal
  schedule, request procedure, and incident process before live service operation.
- Assess the actual acceptance presentation, accessible decline and correction
  controls, operation scope, evidence, and withdrawal behavior. A command flag
  cannot by itself prove informed legal acceptance.
- Review every future cloud or AI provider, transfer, reuse condition, and
  destructive operation before enabling it. No GDPR or worldwide compliance
  claim is established by this Ontario/Canada baseline.

## Related Documents

- [Legal package and release status](../../legal/README.md)
- [Terms of Use](../../legal/terms-of-use.md)
- [Privacy Notice](../../legal/privacy-notice.md)
- [Consent and Operation Authorization](../../legal/consent-and-operation-authorization.md)
