/* Copyright 2026 Lopix Neural Inc. All rights reserved. */
"use strict";

// Preserved text enters the DOM only through textContent. Browser sessions stay
// in HttpOnly cookies; neither tokens nor selected file bytes enter localStorage.
const byId = (id) => document.getElementById(id);
// Versions fence delayed responses after selection or session changes. They
// protect presentation consistency; server-side grants remain authoritative.
const state = { session: null, config: null, resources: [], collections: [], consent: null,
  upload: null, plan: null, selected: new Set(), browseOffset: 0, operationCursor: null,
  workspaceVersion: 0, queryVersion: 0, consentVersion: 0, planVersion: 0, uploadVersion: 0 };
const pendingControls = new WeakSet();
// Submit only the reviewed declaration fields. Additional display metadata from
// a newer server must not silently become an accepted processing instruction.
const CONSENT_FIELDS = ["grant_id", "grant_version", "resource_id", "generation", "actions", "policies", "challenge",
  "purpose", "recipient", "eligibility_version", "eligibility_statement"];
const CONSENT_CHECKS = ["accepted_terms", "acknowledged_privacy", "authorized_scope", "eligible_content"];

class StaleSelection extends Error {}

function show(message, error = false) {
  const notice = byId("notice");
  notice.textContent = message;
  notice.classList.toggle("error", error);
  notice.setAttribute("role", error ? "alert" : "status");
  notice.hidden = false;
}

async function api(path, { method = "GET", body, headers = {} } = {}) {
  const options = { method, credentials: "same-origin", headers: { ...headers } };
  if (method !== "GET") options.headers["X-CSRF-Token"] = state.session?.csrf || "";
  // Pass the browser-owned File directly; do not copy binary content into JSON,
  // text, or browser storage. The server enforces the actual transfer limits.
  if (body instanceof File) options.body = body;
  else if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const document = await response.json();
  if (!document || typeof document !== "object" || Array.isArray(document)) {
    throw new Error("The service returned an unsupported response.");
  }
  if (!response.ok) {
    if (response.status === 401) {
      state.session = null;
      state.workspaceVersion += 1;
      state.planVersion += 1;
      state.consentVersion += 1;
      state.uploadVersion += 1;
      state.consent = state.plan = state.upload = null;
      byId("consent-dialog").close();
      byId("workspace").hidden = true;
      byId("login-panel").hidden = false;
      byId("logout").hidden = true;
    }
    const messages = { authentication_required: "Sign in through the secure portal to continue.",
      access_denied: "The requested access or human interaction is unavailable. Review your current scope.",
      busy: "A resource limit or active operation prevents admission. Inspect status before trying again.",
      validation_failed: "The selected material could not pass preservation verification.",
      invalid_request: "The request does not satisfy the supported input or current operation state." };
    throw new Error(messages[document.error_code] || "The request could not be completed. Review access and try again.");
  }
  return document;
}

function element(tag, text, className) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (className) item.className = className;
  return item;
}

function button(text, action, className = "secondary") {
  const item = element("button", text, className);
  item.type = "button";
  item.addEventListener("click", () => run(action, item));
  return item;
}

async function run(action, control) {
  // One pending action per control prevents duplicate submission without
  // blocking unrelated status, cancellation, or scope-review controls.
  if (control && pendingControls.has(control)) return;
  const buttons = control?.tagName === "FORM" ? [...control.querySelectorAll('button[type="submit"], button:not([type])')]
    : control ? [control] : [];
  const previous = buttons.map((item) => item.disabled);
  if (control) pendingControls.add(control);
  buttons.forEach((item) => { item.disabled = true; });
  try { await action(); }
  catch (error) {
    if (!(error instanceof StaleSelection)) show(error instanceof Error ? error.message : "The action could not be completed.", true);
  }
  finally {
    if (control) pendingControls.delete(control);
    buttons.forEach((item, index) => { item.disabled = previous[index]; });
    syncApprovalControls();
  }
}

function consentChecked() {
  return CONSENT_CHECKS.every((name) => byId("consent-form").elements.namedItem(name)?.checked === true);
}

function syncApprovalControls() {
  byId("accept-consent").disabled = !state.consent || !consentChecked() || pendingControls.has(byId("consent-form"));
  byId("start-plan").disabled = !state.plan || !byId("approve-plan").checked || pendingControls.has(byId("start-plan"));
  byId("decline-plan").disabled = state.plan?.startRequested === true && pendingControls.has(byId("start-plan"));
  byId("recover").disabled = !state.selected.size || pendingControls.has(byId("recover"));
}

function details(values) {
  const list = element("dl");
  for (const [key, value] of Object.entries(values)) {
    list.append(element("dt", key.replaceAll("_", " ")),
      element("dd", typeof value === "object" ? JSON.stringify(value, null, 2) : String(value ?? "Not selected")));
  }
  return list;
}

function options(select, items, label, initial) {
  select.replaceChildren();
  if (initial) {
    const option = element("option", initial);
    option.value = "";
    select.append(option);
  }
  items.forEach((item, index) => {
    const option = element("option", label(item));
    option.value = String(index);
    select.append(option);
  });
}

function resourceLabel(item) {
  return `${item.kind || "workspace"} · ${item.resource_id} · ${item.generation.slice(0, 12)}`;
}

function selectedCollection() {
  const selected = state.collections[Number(byId("collection-resource").value)];
  if (!selected) throw new Error("Choose an available collection generation first.");
  return selected;
}

function scopeActions() {
  const item = state.resources[Number(byId("scope-resource").value)];
  const fieldset = byId("scope-actions");
  fieldset.replaceChildren(element("legend", "Permitted actions"));
  for (const action of item?.actions || []) {
    const label = element("label", undefined, "check");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = action;
    label.append(input, element("span", action.replaceAll("_", " ")));
    fieldset.append(label);
  }
}

async function refresh() {
  const version = ++state.workspaceVersion;
  const session = await api("/api/session");
  if (version !== state.workspaceVersion) throw new StaleSelection();
  state.session = session;
  byId("login-panel").hidden = true;
  byId("workspace").hidden = false;
  byId("logout").hidden = false;
  const available = state.session.options;
  state.resources = [available.workspace, ...available.resources];
  state.collections = available.resources.filter((item) => item.kind === "collection");
  options(byId("scope-resource"), state.resources, resourceLabel);
  options(byId("collection-resource"), state.collections, resourceLabel);
  options(byId("extend-resource"), state.collections, resourceLabel, "Create a new collection");
  scopeActions();
  state.selected.clear();
  byId("collection-results").replaceChildren();
  byId("revision-results").replaceChildren();
  byId("selection").hidden = state.collections.length === 0;
  updateSelection();
  byId("upload-limit").textContent = `Selected upload limit: ${(available.max_upload_bytes / 1024 ** 2).toFixed(0)} MiB. Temporary uploads expire after ${Math.round(available.upload_lifetime_seconds / 60)} minutes.`;
  const grants = byId("grants");
  grants.replaceChildren();
  for (const grant of state.session.grants || []) {
    const card = element("article", undefined, "card");
    card.append(element("p", grant.resource_id, "identifier"),
      element("p", `Actions: ${grant.actions.join(", ")}`),
      element("p", `Generation: ${grant.generation}`, "identifier"),
      button("Revoke access", async () => {
        await api("/api/grants/revoke", { method: "POST", body: { grant_id: grant.grant_id, grant_version: grant.grant_version } });
        show("Access revoked. Future admission and delivery will be checked against this decision.");
        await refresh();
      }));
    grants.append(card);
  }
  if (!grants.children.length) grants.append(element("p", "No accepted access grants. Review a scope above to begin."));
  const downloads = byId("downloads");
  downloads.replaceChildren();
  for (const resource of available.resources.filter((item) => item.kind === "package")) {
    const card = element("article", undefined, "card");
    card.append(element("p", resource.resource_id, "identifier"));
    const authorized = (state.session.grants || []).some((grant) => grant.resource_id === resource.resource_id
      && grant.generation === resource.generation && grant.actions.includes("download"));
    if (authorized) {
      const link = element("a", "Download verified ZIP", "button");
      link.href = `/api/downloads/${encodeURIComponent(resource.resource_id)}?generation=${encodeURIComponent(resource.generation)}`;
      card.append(link);
    } else card.append(element("p", "Authorize this package's download scope above."));
    downloads.append(card);
  }
  if (!downloads.children.length) downloads.append(element("p", "No completed package downloads yet."));
  await loadOperations();
}

function updateSelection() {
  byId("selection-count").textContent = `${state.selected.size} conversation${state.selected.size === 1 ? "" : "s"} selected for recovery or classification.`;
  syncApprovalControls();
}

async function query(kind, extra = {}) {
  const collection = selectedCollection();
  const workspaceVersion = state.workspaceVersion;
  const queryVersion = ++state.queryVersion;
  const result = await api("/api/query", { method: "POST", body: { ...extra, kind,
    collection_id: collection.resource_id, generation: collection.generation } });
  // A delayed response must never repopulate selection controls for a newer
  // generation. This guard applies to browse, search, verification, and reads.
  if (workspaceVersion !== state.workspaceVersion || queryVersion !== state.queryVersion) throw new StaleSelection();
  return result;
}

async function browse(offset = 0) {
  const result = await query("browse", { offset, limit: 20 });
  const area = byId("collection-results");
  area.replaceChildren();
  for (const conversation of result.items || []) {
    const card = element("article", undefined, "card");
    const label = element("label", undefined, "check");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.selected.has(conversation.conversation_key);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.selected.add(conversation.conversation_key);
      else state.selected.delete(conversation.conversation_key);
      updateSelection();
    });
    label.append(checkbox, element("span", conversation.title || conversation.revisions?.at(-1)?.title || "Untitled conversation"));
    card.append(label, element("p", conversation.conversation_key, "identifier"),
      element("p", `Association: ${conversation.association?.state || "unknown"} · Revisions: ${conversation.revision_count ?? conversation.revisions?.length ?? 0}`));
    for (const revision of conversation.revisions || []) {
      card.append(button(`Read revision ${revision.revision_id.slice(0, 12)}`, () => read(conversation.conversation_key, revision.revision_id)));
    }
    if (conversation.revisions_truncated) card.append(element("p", "Additional revisions are available through the ChatGPT companion's revision pagination.", "help"));
    area.append(card);
  }
  if (!area.children.length) area.append(element("p", "No conversations match this page."));
  state.browseOffset = result.next_offset;
  byId("more-conversations").hidden = result.next_offset == null;
  byId("selection").hidden = false;
}

async function read(conversationKey, revisionId, offset = 0) {
  const result = await query("read", { conversation_key: conversationKey, revision_id: revisionId, offset, limit: 20 });
  const area = byId("revision-results");
  area.replaceChildren(element("h3", "Preserved revision"));
  area.append(details({ revision: result.revision_id || revisionId, selection_basis: result.selection_basis || "explicit_revision" }));
  for (const node of result.items || result.nodes || []) {
    const card = element("article", undefined, "card");
    card.append(element("p", `${node.role || "Structural node"} · ${node.node_id || node.id}`, "muted"),
      element("pre", node.text || "No message text at this node."),
      element("p", `Parent: ${node.parent_id || "root"} · Children: ${(node.children_ids || []).join(", ") || "none"}`, "identifier"));
    if (node.text_truncated) card.append(element("p", "This response truncates the displayed text; the preserved record remains unchanged.", "help"));
    area.append(card);
  }
  if (result.next_offset != null) area.append(button("Next node page", () => read(conversationKey, revisionId, result.next_offset)));
  area.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function prepareOperation(kind, resource, parameters) {
  const version = ++state.planVersion;
  const plan = await api("/api/operations/prepare", { method: "POST", body: { kind,
    resource_id: resource.resource_id, generation: resource.generation, parameters } });
  if (version !== state.planVersion) throw new StaleSelection();
  await openPlan(plan.plan_id);
}

async function openPlan(planId) {
  const version = ++state.planVersion;
  const prepared = await api(`/api/plans/${encodeURIComponent(planId)}`);
  if (version !== state.planVersion) throw new StaleSelection();
  // Loading a prepared plan always requires a fresh visible approval. A prior
  // selection or a model-created plan cannot preselect the user's decision.
  state.plan = { ...prepared, reviewed: false, reviewUncertain: false, reviewExpiresAt: 0,
    startRequested: false, idempotencyKey: null };
  byId("plan-id").value = state.plan.plan.plan_id;
  byId("plan-details").replaceChildren(details(state.plan.plan));
  byId("approve-plan").checked = false;
  byId("start-plan").disabled = true;
  byId("plan-review").hidden = false;
  byId("plan-review").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadOperations(older = false) {
  const suffix = older && state.operationCursor ? `?before_operation_id=${encodeURIComponent(state.operationCursor)}` : "";
  const result = await api(`/api/operations${suffix}`);
  const area = byId("operation-list");
  area.replaceChildren();
  for (const operation of result.items || []) {
    const card = element("article", undefined, "card");
    card.append(element("span", operation.state.replaceAll("_", " "), "badge"),
      element("h3", `${operation.kind} operation`), element("p", operation.operation_id, "identifier"));
    if (operation.result) card.append(details(operation.result));
    if (operation.output_id) card.append(element("p", `Output: ${operation.output_id}`, "identifier"));
    if (operation.error_code) card.append(element("p", `Outcome: ${operation.error_code.replaceAll("_", " ")}`));
    if (operation.disclosure === "authorization_required") card.append(element("p", "Current authorization prevents result disclosure."));
    if (["queued", "running", "verifying", "cancel_requested"].includes(operation.state)) {
      card.append(button("Request cancellation", async () => {
        await api(`/api/operations/${encodeURIComponent(operation.operation_id)}/cancel`, { method: "POST", body: {} });
        show("Cancellation requested. Publication already authorized may finish privately.");
        await loadOperations();
      }));
    }
    area.append(card);
  }
  if (!area.children.length) area.append(element("p", "No operations have been started."));
  state.operationCursor = result.next_before_operation_id || result.next_operation_id;
  byId("more-operations").hidden = !state.operationCursor;
}

function bind(id, event, handler) {
  byId(id).addEventListener(event, (eventObject) => {
    if (event === "submit") eventObject.preventDefault();
    run(() => handler(eventObject), ["click", "submit"].includes(event) ? eventObject.currentTarget : null);
  });
}

bind("operator-login", "submit", async () => {
  const key = byId("operator-key").value;
  byId("operator-key").value = "";
  await api("/auth/operator", { method: "POST", body: { key } });
  await refresh();
  show("Local identity established. Review access before processing any selected content.");
});
bind("logout", "click", async () => { await api("/auth/logout", { method: "POST", body: {} }); location.reload(); });
bind("refresh", "click", refresh);
bind("scope-resource", "change", () => { state.consentVersion += 1; scopeActions(); });
bind("scope-form", "submit", async () => {
  const version = ++state.consentVersion;
  const selected = state.resources[Number(byId("scope-resource").value)];
  const actions = [...byId("scope-actions").querySelectorAll("input:checked")].map((item) => item.value);
  if (!actions.length) throw new Error("Choose at least one intended action.");
  const prepared = await api("/api/consent/prepare", { method: "POST", body: { resource_id: selected.resource_id,
    generation: selected.generation, actions } });
  if (version !== state.consentVersion) throw new StaleSelection();
  state.consent = prepared;
  const { challenge, ...display } = state.consent;
  byId("consent-details").replaceChildren(details(display));
  if (state.consent.eligibility_statement) byId("eligibility-copy").textContent = state.consent.eligibility_statement;
  byId("consent-form").reset();
  byId("accept-consent").disabled = true;
  byId("consent-dialog").showModal();
});
byId("consent-form").addEventListener("change", () => {
  syncApprovalControls();
});
bind("decline-consent", "click", () => { state.consentVersion += 1; state.consent = null; byId("consent-dialog").close(); show("Access declined. No selected content was processed by this decision."); });
byId("consent-dialog").addEventListener("cancel", () => { state.consentVersion += 1; state.consent = null; syncApprovalControls(); });
bind("consent-form", "submit", async () => {
  if (!state.consent || !consentChecked()) throw new Error("Review the displayed scope and make each required acceptance decision.");
  const body = {};
  for (const field of CONSENT_FIELDS) if (Object.hasOwn(state.consent, field)) body[field] = state.consent[field];
  for (const name of CONSENT_CHECKS) body[name] = true;
  await api("/api/consent/accept", { method: "POST", body });
  byId("consent-dialog").close();
  state.consent = null;
  await refresh();
  show("The exact scope and document versions were recorded. Operations still require their own review.");
});
bind("browse", "click", () => browse());
bind("more-conversations", "click", () => browse(state.browseOffset));
bind("collection-resource", "change", () => { state.workspaceVersion += 1; state.selected.clear(); state.browseOffset = 0; updateSelection(); byId("collection-results").replaceChildren(); byId("revision-results").replaceChildren(); byId("more-conversations").hidden = true; });
bind("search", "click", async () => { const result = await query("search", { query: byId("search-text").value, limit: 20 }); byId("collection-results").replaceChildren(element("pre", JSON.stringify(result, null, 2))); });
bind("verify", "click", async () => { const result = await query("verify"); byId("collection-results").replaceChildren(details(result)); show("Verification completed. Review the reported scope and any limitations."); });
bind("recover", "click", () => prepareOperation("recovery", selectedCollection(), { conversation_keys: [...state.selected], project_id: null, revision_id: null }));
bind("package", "click", () => prepareOperation("package", selectedCollection(), {}));
bind("association-form", "submit", async () => {
  if (state.selected.size !== 1) throw new Error("Select exactly one conversation for an association decision.");
  const associationState = byId("association-state").value;
  await prepareOperation("association", selectedCollection(), { conversation_key: [...state.selected][0], state: associationState,
    project_id: associationState === "project_confirmed" ? byId("project-id").value : null, reason: byId("association-reason").value });
});
bind("upload-form", "submit", async () => {
  const version = ++state.uploadVersion;
  const file = byId("upload-file").files[0];
  if (!file || file.size > state.session.options.max_upload_bytes) throw new Error("Select one ZIP within the displayed upload limit.");
  show("Uploading the explicitly selected file…");
  const uploaded = await api("/api/uploads", { method: "POST", body: file,
    headers: { "Content-Type": "application/octet-stream", "X-File-Name": encodeURIComponent(file.name) } });
  if (version !== state.uploadVersion) throw new StaleSelection();
  state.upload = uploaded;
  byId("upload-receipt").replaceChildren(details(state.upload));
  byId("upload-receipt").hidden = false;
  byId("intake-form").hidden = false;
  show("Upload staged with a byte count, digest, and expiry. Import has not started.");
});
byId("upload-file").addEventListener("change", () => {
  state.uploadVersion += 1;
  state.upload = null;
  byId("upload-receipt").hidden = true;
  byId("intake-form").hidden = true;
});
bind("intake-form", "submit", async () => {
  if (!state.upload) throw new Error("Upload a selected file first.");
  const kind = byId("intake-kind").value;
  const previous = kind === "import" && byId("extend-resource").value !== "" ? state.collections[Number(byId("extend-resource").value)] : null;
  const parameters = { input_handle: state.upload.upload_id, input_sha256: state.upload.sha256 };
  if (kind === "import") Object.assign(parameters, { account_namespace: byId("account-namespace").value, previous_generation: previous?.generation || null });
  await prepareOperation(kind, previous || state.session.options.workspace, parameters);
});
bind("open-plan-form", "submit", () => openPlan(byId("plan-id").value.trim()));
byId("approve-plan").addEventListener("change", syncApprovalControls);
bind("decline-plan", "click", async () => {
  if (state.plan?.startRequested) {
    show("A start was already requested. Inspect operation status and request cancellation if needed.");
    await loadOperations();
    return;
  }
  state.planVersion += 1;
  state.plan = null;
  byId("plan-review").hidden = true;
  show("Operation declined. No execution was started.");
});
bind("start-plan", "click", async () => {
  if (!state.plan || !byId("approve-plan").checked) throw new Error("Review and approve the exact plan first.");
  const review = state.plan;
  const plan = review.plan;
  const keyName = `keepmorrow-start-${plan.plan_id}`;
  // Only the plan's retry identity is retained for this browser tab. Reusing it
  // after a lost response lets the server resolve the original start instead of
  // treating transport uncertainty as permission for another operation.
  if (!review.idempotencyKey) {
    try { review.idempotencyKey = sessionStorage.getItem(keyName); } catch { /* Storage can be unavailable in a private browser context. */ }
    if (!review.idempotencyKey) review.idempotencyKey = crypto.randomUUID();
    try { sessionStorage.setItem(keyName, review.idempotencyKey); } catch { /* The in-memory key still makes retries within this view stable. */ }
  }
  if (review.reviewed && review.reviewExpiresAt <= Date.now() / 1000) {
    review.reviewed = false;
    review.reviewUncertain = true;
  }
  if (review.reviewUncertain) {
    const current = await api(`/api/plans/${encodeURIComponent(plan.plan_id)}`);
    if (current.plan.parameter_digest !== plan.parameter_digest) {
      await openPlan(plan.plan_id);
      throw new Error("The plan changed. Review its current contents before approving it.");
    }
    review.challenge = current.challenge;
    review.reviewUncertain = false;
  }
  if (state.plan !== review || !byId("approve-plan").checked) throw new StaleSelection();
  if (!review.reviewed) {
    try {
      const receipt = await api(`/api/plans/${encodeURIComponent(plan.plan_id)}/review`, { method: "POST", body: {
        parameter_digest: plan.parameter_digest, challenge: review.challenge, approved: true } });
      review.reviewed = true;
      review.reviewExpiresAt = receipt.expires_at;
    } catch (error) {
      // A lost response may follow a consumed challenge. Retry with a fresh
      // challenge while keeping the same exact plan and idempotency identity.
      review.reviewUncertain = true;
      throw error;
    }
  }
  if (state.plan !== review || !byId("approve-plan").checked) throw new StaleSelection();
  // Record intent before awaiting the network: a lost response cannot establish
  // that execution never began, so later decline must direct the user to status.
  review.startRequested = true;
  syncApprovalControls();
  await api("/api/operations/start", { method: "POST", body: { plan_id: plan.plan_id, idempotency_key: review.idempotencyKey } });
  if (state.plan === review) {
    byId("plan-review").hidden = true;
    state.plan = null;
  }
  show("Reviewed operation queued. Refresh status to inspect the verified outcome.");
  await loadOperations();
});
bind("refresh-operations", "click", async () => { await refresh(); show("Workspace and operation status refreshed."); });
bind("more-operations", "click", () => loadOperations(true));

run(async () => {
  state.config = await api("/api/config");
  byId("mode").textContent = state.config.mode === "operator" ? "Local operator pilot" : "Authenticated private pilot";
  byId("operator-login").hidden = state.config.mode !== "operator";
  byId("oauth-login").hidden = state.config.mode !== "oauth";
  if (state.config.login_url) byId("oauth-login").href = state.config.login_url;
  try { await refresh(); }
  catch (error) {
    if (!state.session) byId("login-panel").hidden = false;
    else show(error instanceof Error ? error.message : "Workspace status could not be loaded.", true);
  }
});
