// Execute the authored portal script against controlled HTTP responses. These
// synthetic form gestures validate UI behavior and are not human legal consent.
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { JSDOM } from "jsdom";

const assetRoot = new URL("../../../src/keepmorrow/integrations/chatgpt/portal_assets/", import.meta.url);
const html = await readFile(new URL("index.html", assetRoot), "utf8");
const javascript = await readFile(new URL("portal.js", assetRoot), "utf8");
const generation = "a".repeat(64);
const conversation = "b".repeat(64);
const revision = "c".repeat(64);
const digest = "d".repeat(64);
const hostile = '<img src=x onerror="window.sourceExecuted=true">';
const settle = () => new Promise((resolve) => setImmediate(resolve));

async function fixture() {
  const dom = new JSDOM(html, { url: "https://keepmorrow.example/portal", runScripts: "outside-only" });
  const { window } = dom;
  // JSDOM does not implement browser scrolling or modal presentation. Stub only
  // those surfaces; request sequencing and approval state use the actual script.
  window.HTMLElement.prototype.scrollIntoView = function () {};
  window.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  window.HTMLDialogElement.prototype.close = function () { this.open = false; };
  Object.defineProperty(window.crypto, "randomUUID", { value: randomUUID });
  const workspace = { resource_id: "workspace_1", generation: "workspace_v1", actions: ["upload", "import", "unpack"] };
  const resources = [
    { resource_id: "collection_1", generation, kind: "collection", actions: ["browse", "read", "search", "verify", "recover", "package", "associate"] },
    { resource_id: "collection_2", generation: "e".repeat(64), kind: "collection", actions: ["browse", "read"] },
  ];
  const policies = { terms: { version: "terms-v1", sha256: "f".repeat(64) }, privacy: { version: "privacy-v1", sha256: "1".repeat(64) } };
  const consent = { grant_id: "grant_1", grant_version: 1, resource_id: workspace.resource_id,
    generation: workspace.generation, actions: ["upload"], policies, challenge: "consent_challenge",
    purpose: "eligible_preservation", recipient: "local_operator", eligibility_version: "eligible-content-v1",
    eligibility_statement: "I have authority to process this selection.", future_display_metadata: "ignored by strict submission" };
  const plan = { plan_id: "plan_1", kind: "package", state: "prepared", parameters: {}, scope: resources[0],
    reservation_bytes: 128, parameter_digest: digest, created_at: 100, expires_at: 9_999_999_999 };
  const calls = [];
  const overrides = new Map();
  let planReads = 0;
  window.fetch = async (path, options = {}) => {
    const body = typeof options.body === "string" ? JSON.parse(options.body) : options.body;
    const call = { path, method: options.method, headers: options.headers, credentials: options.credentials, body };
    calls.push(call);
    if (overrides.has(path)) return overrides.get(path)(call);
    let data;
    if (path === "/api/config") data = { mode: "operator", login_url: null };
    else if (path === "/api/session") data = { csrf: "synthetic_csrf", grants: [], options: {
      workspace, resources, policies, max_upload_bytes: 1024, upload_lifetime_seconds: 3600, artifact_lifetime_seconds: 3600,
    } };
    else if (path === "/api/operations") data = { items: [], next_before_operation_id: null };
    else if (path === "/api/consent/prepare") data = consent;
    else if (path === "/api/consent/accept") data = { accepted: true, acceptance_id: "acceptance_1" };
    else if (path === "/api/uploads") data = { upload_id: "u_" + "a".repeat(32), sha256: digest, size_bytes: body.size,
      display_name: body.name, expires_at: 9_999_999_999 };
    else if (path === "/api/operations/prepare") data = { ...plan, kind: body.kind, parameters: body.parameters };
    else if (path === "/api/plans/plan_1") { planReads += 1; data = { plan, challenge: "review_challenge_" + planReads }; }
    else if (path === "/api/plans/plan_1/review") data = { reviewed: true, expires_at: 9_999_999_999, review_id: "review_1", plan_id: "plan_1" };
    else if (path === "/api/operations/start") data = { operation_id: "operation_1", state: "queued" };
    else if (path === "/api/query") {
      if (body.kind === "browse") data = { items: [{ conversation_key: conversation, association: { state: "association_unknown" },
        revision_count: 1, revisions: [{ revision_id: revision, title: hostile }], revisions_truncated: false }], total: 1, next_offset: null };
      else if (body.kind === "read") data = { revision_id: revision, selection_basis: "explicit_revision", nodes: [{ id: "node_1", role: "user",
        text: hostile, parent_id: null, children_ids: ["answer", "alternative"] }], next_offset: null };
      else if (body.kind === "search") data = { items: [{ conversation_key: conversation, revision_id: revision, title: hostile, excerpt: hostile }] };
      else data = { verified: true, summary: { conversation_count: 1 } };
    } else throw new Error("Unexpected synthetic portal route: " + path);
    return { ok: true, status: 200, json: async () => structuredClone(data) };
  };
  window.eval(javascript);
  await settle();
  const node = (id) => window.document.getElementById(id);
  const click = async (id) => { node(id).click(); await settle(); };
  const submit = async (id) => { node(id).dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true })); await settle(); };
  const change = (element) => element.dispatchEvent(new window.Event("change", { bubbles: true }));
  const file = (name = "selected.zip") => {
    const value = new window.File([new Uint8Array([0, 255, 1])], name, { type: "application/zip" });
    Object.defineProperty(node("upload-file"), "files", { configurable: true, value: [value] });
    change(node("upload-file"));
    return value;
  };
  const openPlan = async () => { node("plan-id").value = "plan_1"; await submit("open-plan-form"); };
  const approvePlan = () => { node("approve-plan").checked = true; change(node("approve-plan")); };
  return { dom, window, calls, overrides, node, click, submit, change, file, openPlan, approvePlan,
    callsTo: (path) => calls.filter((call) => call.path === path) };
}

test("portal initialization neither accepts policies nor uploads or executes content", async () => {
  const f = await fixture();
  assert.deepEqual(f.calls.map((call) => call.path), ["/api/config", "/api/session", "/api/operations"]);
  assert.ok(f.calls.every((call) => call.method === "GET"));
  assert.ok([...f.window.document.querySelectorAll('input[type="checkbox"]')].every((input) => !input.checked));
  assert.equal(f.node("accept-consent").disabled, true);
  assert.equal(f.node("start-plan").disabled, true);
  f.dom.window.close();
});

test("all consent decisions are required and only the displayed strict snapshot is submitted", async () => {
  const f = await fixture();
  const selected = f.node("scope-actions").querySelector('input[value="upload"]');
  selected.checked = true;
  await f.submit("scope-form");
  assert.equal(f.node("consent-dialog").open, true);
  assert.equal(f.node("accept-consent").disabled, true);
  await f.submit("consent-form");
  assert.equal(f.callsTo("/api/consent/accept").length, 0);
  const checks = [...f.node("consent-form").querySelectorAll('input[type="checkbox"]')];
  for (const input of checks.slice(0, -1)) { input.checked = true; f.change(input); }
  assert.equal(f.node("accept-consent").disabled, true);
  checks.at(-1).checked = true;
  f.change(checks.at(-1));
  await f.submit("consent-form");
  const accepted = f.callsTo("/api/consent/accept")[0];
  assert.equal(accepted.body.grant_id, "grant_1");
  assert.equal(accepted.body.challenge, "consent_challenge");
  assert.equal(accepted.body.generation, "workspace_v1");
  for (const name of ["accepted_terms", "acknowledged_privacy", "authorized_scope", "eligible_content"]) assert.equal(accepted.body[name], true);
  assert.ok(!("future_display_metadata" in accepted.body));
  assert.equal(accepted.headers["X-CSRF-Token"], "synthetic_csrf");
  assert.equal(accepted.credentials, "same-origin");
  f.dom.window.close();
});

test("choosing a file sends no bytes; an explicit upload and import bind its receipt", async () => {
  const f = await fixture();
  const file = f.file("selected export.zip");
  await settle();
  assert.equal(f.callsTo("/api/uploads").length, 0);
  await f.submit("upload-form");
  const uploaded = f.callsTo("/api/uploads")[0];
  assert.equal(uploaded.body, file);
  assert.equal(uploaded.headers["Content-Type"], "application/octet-stream");
  assert.equal(uploaded.headers["X-File-Name"], "selected%20export.zip");
  assert.equal(uploaded.headers["X-CSRF-Token"], "synthetic_csrf");
  await f.submit("intake-form");
  assert.deepEqual(f.callsTo("/api/operations/prepare")[0].body, {
    kind: "import", resource_id: "workspace_1", generation: "workspace_v1",
    parameters: { input_handle: "u_" + "a".repeat(32), input_sha256: digest,
      account_namespace: "my-supplied-export", previous_generation: null },
  });
  assert.equal(f.callsTo("/api/operations/start").length, 0);
  assert.equal(f.node("approve-plan").checked, false);
  f.file("different.zip");
  assert.equal(f.node("intake-form").hidden, true);
  await f.submit("intake-form");
  assert.equal(f.callsTo("/api/operations/prepare").length, 1);
  f.dom.window.close();
});

test("browse matches the server shape and selected recovery uses exact conversation identities", async () => {
  const f = await fixture();
  await f.click("browse");
  assert.ok(f.node("collection-results").textContent.includes(hostile));
  assert.equal(f.node("collection-results").querySelectorAll("img").length, 0);
  const selected = f.node("collection-results").querySelector('input[type="checkbox"]');
  selected.checked = true;
  f.change(selected);
  await f.click("recover");
  assert.deepEqual(f.callsTo("/api/operations/prepare")[0].body, {
    kind: "recovery", resource_id: "collection_1", generation,
    parameters: { conversation_keys: [conversation], project_id: null, revision_id: null },
  });
  assert.equal(f.callsTo("/api/operations/start").length, 0);
  f.dom.window.close();
});

test("extended import and package unpack use their distinct exact parameter contracts", async () => {
  const f = await fixture();
  f.file();
  await f.submit("upload-form");
  f.node("extend-resource").value = "1";
  f.node("account-namespace").value = "stable-synthetic-account";
  await f.submit("intake-form");
  assert.deepEqual(f.callsTo("/api/operations/prepare").at(-1).body, {
    kind: "import", resource_id: "collection_2", generation: "e".repeat(64),
    parameters: { input_handle: "u_" + "a".repeat(32), input_sha256: digest,
      account_namespace: "stable-synthetic-account", previous_generation: "e".repeat(64) },
  });
  f.node("intake-kind").value = "unpack";
  await f.submit("intake-form");
  assert.deepEqual(f.callsTo("/api/operations/prepare").at(-1).body, {
    kind: "unpack", resource_id: "workspace_1", generation: "workspace_v1",
    parameters: { input_handle: "u_" + "a".repeat(32), input_sha256: digest },
  });
  assert.equal(f.callsTo("/api/operations/start").length, 0);
  f.dom.window.close();
});

test("association evidence and whole-collection packaging require separate reviewed plans", async () => {
  const f = await fixture();
  await f.click("browse");
  const selected = f.node("collection-results").querySelector('input[type="checkbox"]');
  selected.checked = true;
  f.change(selected);
  f.node("association-state").value = "project_confirmed";
  f.node("project-id").value = "synthetic-project";
  f.node("association-reason").value = "The owner supplied an explicit project association.";
  await f.submit("association-form");
  assert.deepEqual(f.callsTo("/api/operations/prepare").at(-1).body, {
    kind: "association", resource_id: "collection_1", generation,
    parameters: { conversation_key: conversation, state: "project_confirmed", project_id: "synthetic-project",
      reason: "The owner supplied an explicit project association." },
  });
  await f.click("package");
  assert.deepEqual(f.callsTo("/api/operations/prepare").at(-1).body,
    { kind: "package", resource_id: "collection_1", generation, parameters: {} });
  assert.equal(f.callsTo("/api/operations/start").length, 0);
  assert.equal(f.node("approve-plan").checked, false);
  f.dom.window.close();
});

test("a delayed old-generation response cannot repopulate current selection controls", async () => {
  const f = await fixture();
  let release;
  f.overrides.set("/api/query", () => new Promise((resolve) => { release = resolve; }));
  await f.click("browse");
  f.node("collection-resource").value = "1";
  f.change(f.node("collection-resource"));
  release({ ok: true, status: 200, json: async () => ({ items: [{ conversation_key: conversation, title: "Stale result" }], next_offset: null }) });
  await settle();
  assert.equal(f.node("collection-results").children.length, 0);
  assert.equal(f.node("recover").disabled, true);
  assert.equal(f.callsTo("/api/query")[0].body.generation, generation);
  f.dom.window.close();
});

test("an unchecked operation review cannot start even through a synthetic click event", async () => {
  const f = await fixture();
  await f.openPlan();
  f.node("start-plan").dispatchEvent(new f.window.MouseEvent("click", { bubbles: true }));
  await settle();
  assert.equal(f.callsTo("/api/plans/plan_1/review").length, 0);
  assert.equal(f.callsTo("/api/operations/start").length, 0);
  assert.equal(f.node("start-plan").disabled, true);
  f.dom.window.close();
});

test("retry after a lost start response keeps its idempotency key and consumes no second review", async () => {
  const f = await fixture();
  let starts = 0;
  f.overrides.set("/api/operations/start", async () => {
    if (++starts === 1) throw new TypeError("Synthetic lost response");
    return { ok: true, status: 200, json: async () => ({ operation_id: "operation_1", state: "queued" }) };
  });
  await f.openPlan();
  f.approvePlan();
  await f.click("start-plan");
  assert.equal(f.callsTo("/api/plans/plan_1/review").length, 1);
  assert.equal(f.node("plan-review").hidden, false);
  await f.click("start-plan");
  const requests = f.callsTo("/api/operations/start");
  assert.equal(requests.length, 2);
  assert.equal(requests[0].body.idempotency_key, requests[1].body.idempotency_key);
  assert.equal(f.callsTo("/api/plans/plan_1/review").length, 1);
  assert.equal(f.node("plan-review").hidden, true);
  f.dom.window.close();
});

test("an uncertain review retries with a fresh challenge only after another explicit click", async () => {
  const f = await fixture();
  let reviews = 0;
  f.overrides.set("/api/plans/plan_1/review", async () => {
    if (++reviews === 1) throw new TypeError("Synthetic lost review response");
    return { ok: true, status: 200, json: async () => ({ reviewed: true, expires_at: 9_999_999_999 }) };
  });
  await f.openPlan();
  f.approvePlan();
  await f.click("start-plan");
  assert.equal(f.callsTo("/api/operations/start").length, 0);
  assert.equal(f.callsTo("/api/plans/plan_1").length, 1);
  await f.click("start-plan");
  assert.equal(f.callsTo("/api/plans/plan_1").length, 2);
  const requests = f.callsTo("/api/plans/plan_1/review");
  assert.notEqual(requests[0].body.challenge, requests[1].body.challenge);
  assert.equal(requests[0].body.parameter_digest, requests[1].body.parameter_digest);
  assert.equal(f.callsTo("/api/operations/start").length, 1);
  f.dom.window.close();
});

test("declining while review is pending prevents a later start request", async () => {
  const f = await fixture();
  let release;
  f.overrides.set("/api/plans/plan_1/review", () => new Promise((resolve) => { release = resolve; }));
  await f.openPlan();
  f.approvePlan();
  await f.click("start-plan");
  await f.click("decline-plan");
  release({ ok: true, status: 200, json: async () => ({ reviewed: true, expires_at: 9_999_999_999 }) });
  await settle();
  assert.equal(f.callsTo("/api/operations/start").length, 0);
  assert.equal(f.node("plan-review").hidden, true);
  assert.equal(f.node("start-plan").disabled, true);
  f.dom.window.close();
});

test("declining after an uncertain start never claims the operation did not execute", async () => {
  const f = await fixture();
  f.overrides.set("/api/operations/start", async () => { throw new TypeError("Synthetic lost response"); });
  await f.openPlan();
  f.approvePlan();
  await f.click("start-plan");
  await f.click("decline-plan");
  assert.match(f.node("notice").textContent, /A start was already requested/);
  assert.equal(f.node("plan-review").hidden, false);
  f.dom.window.close();
});

test("duplicate upload submission is bounded and a changed file invalidates the pending receipt", async () => {
  const f = await fixture();
  let release;
  f.overrides.set("/api/uploads", () => new Promise((resolve) => { release = resolve; }));
  f.file("first.zip");
  await f.submit("upload-form");
  await f.submit("upload-form");
  assert.equal(f.callsTo("/api/uploads").length, 1);
  f.file("second.zip");
  release({ ok: true, status: 200, json: async () => ({ upload_id: "u_first", sha256: digest, size_bytes: 3 }) });
  await settle();
  assert.equal(f.node("intake-form").hidden, true);
  assert.equal(f.node("upload-receipt").hidden, true);
  f.dom.window.close();
});

test("every authenticated mutation and query carries CSRF and preserves source text as text", async () => {
  const f = await fixture();
  await f.click("browse");
  const revisionButton = f.node("collection-results").querySelector("button");
  revisionButton.click();
  await settle();
  assert.ok(f.node("revision-results").textContent.includes(hostile));
  assert.equal(f.node("revision-results").querySelectorAll("img").length, 0);
  f.node("search-text").value = "[literal].*";
  await f.click("search");
  assert.equal(f.callsTo("/api/query").at(-1).body.query, "[literal].*");
  for (const request of f.calls.filter((call) => call.method === "POST")) {
    assert.equal(request.headers["X-CSRF-Token"], "synthetic_csrf");
    assert.equal(request.credentials, "same-origin");
  }
  f.dom.window.close();
});
