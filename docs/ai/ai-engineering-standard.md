# AI Engineering Standard

**Owner:** Lopix Neural Inc.  
**Engineering lead:** Fabio de Sousa Lopes  
**Contact:** fabio@lopixneural.com  
**Effective date:** 2026-11-12  
**Status:** Policy for future model-assisted features; no runtime model selected

LPX Keepmorrow's preservation core must operate without a model. Optional AI may
help explain supplied material, propose organization, generate derived summaries,
or improve retrieval. Every such output remains a labeled derivative with
provenance. The presence of this policy does not implement an AI feature,
authorize a provider, or select a production model.

## 1. Keep authority in deterministic code

Models must not decide which original bytes to discard, calculate authoritative
hashes, replace originals, silently merge identities, confirm historical project
membership, mark an archive complete, or authorize a transfer. A suggestion can
be submitted to a deterministic validator and, when appropriate, an explicit
user decision workflow. Record the resulting decision separately from the
suggestion and from historical source evidence.

A missing project identifier must remain `association_unknown` unless reliable
evidence or an explicit user decision establishes another state. A model's
confidence score alone is not that evidence.

## 2. Define the feature contract

Before selecting a model, document the task, accepted inputs, output schema,
allowed uses, failure behavior, privacy boundary, latency and cost assumptions,
and evaluation criteria. Include a non-model baseline where it can solve the
same task. Prefer deterministic processing when it satisfies the requirement.

Return structured outputs where downstream code needs structure. Validate
schema, types, lengths, enumerations, cited source identifiers, and field
relationships. Treat malformed or unsupported responses as explicit outcomes.
Do not hide parsing failures behind a successful empty result.

## 3. Record model and data provenance

Each evaluation and enabled feature configuration must identify:

- Provider, model identifier, pinned revision where available, and the exact
  response model identifier when returned.
- Prompt template version and hash, system configuration, generation parameters,
  tool definitions, and output schema version.
- Preprocessing and retrieval versions, chunking policy, and selected source
  identifiers or hashes sufficient to reproduce the input selection.
- Evaluation dataset version, run identifier, date, and application commit.
- Runtime, quantization, hardware, and inference settings for a local model.

Capture enough provenance to explain a result without copying private content
into general logs. If a provider cannot pin a revision, record that limitation
and require regression evaluation when its observed behavior changes.

## 4. Treat source content as untrusted data

Conversation text, attachments, retrieved snippets, and model responses may
contain instructions. They must not alter application policy, tool access,
credentials, file destinations, or the set of authorized operations.

Separate instructions from source content in the request. Delimiters alone are
not an authorization mechanism. Enforce tool allowlists and argument validation
outside the model. Do not place credentials in model context. Do not execute
generated code or shell commands as part of preservation or summarization.

If a feature uses tools, limit them to the minimum documented scope. Validate
paths, resource identifiers, destinations, and budgets after generation and
before execution. An embedded URL or model-generated destination is not user
authorization to access it.

## 5. Preserve user control and privacy

Process only the material needed for the selected task. An archive import does
not implicitly authorize sending the archive to an external model or training
on its contents. Document processing location, data sent, provider terms,
retention, deletion, and operational ownership before enabling that integration.
Use the user's existing authorization without demanding redundant confirmations.

Do not use private conversations for training, fine-tuning, demonstrations, or
evaluation without authorization for that use. Synthetic fixtures are the
default. Review model weights, datasets, embeddings, and dependencies for their
source, version, intended-use constraints, and applicable license.

## 6. Bound work and expose failure

Set explicit limits for input size, output size, request duration, concurrency,
tool calls, retry count, and total task budget. Retry only documented transient
failures, using stable operation identifiers where the provider supports them.
Handle cancellation without losing deterministic preservation work.

Do not silently switch to an unapproved provider or send more data on fallback.
Provider unavailability, refusal, budget exhaustion, validation failure, and
insufficient evidence must remain distinguishable. Core archive creation and
verification must remain available when the optional AI feature fails.

## 7. Evaluate behavior before release

Follow the [AI Evaluation Plan](evaluation-plan.md). Evaluate factual grounding,
unsupported claims, evidence attribution, abstention, ambiguity, injection
resistance, privacy, latency, and cost for the particular task. Include a held-out
set and inspect actual errors, not only aggregate scores.

A model or prompt change is a behavioral change. Keep a reproducible baseline,
compare meaningful regressions, and record the release decision. Do not describe
lower sampling temperature as a guarantee of determinism or a benchmark score
as a guarantee of correctness on unseen inputs.

Every generated view must identify itself as generated and link to the source
evidence available to the user. Unavailable originals must stay unavailable;
generated reconstructions cannot stand in for them.
