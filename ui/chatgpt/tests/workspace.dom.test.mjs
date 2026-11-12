// Test authored UI behavior with a controlled tool client. Deferred replies
// expose stale-selection and control responsiveness without network timing.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { JSDOM } from "jsdom";
import { Workspace } from "../src/workspace.ts";

const template = await readFile(new URL("../src/index.html", import.meta.url), "utf8");
const generation = "a".repeat(64);
const conversation = "b".repeat(64);
const revision = "c".repeat(64);
const hostile = '<img src=x onerror="window.sourceExecuted=true">';
const settle = () => new Promise((resolve) => setImmediate(resolve));

async function fixture({ empty = false } = {}) {
  const dom = new JSDOM(template, { url: "https://synthetic.example/app" });
  globalThis.document = dom.window.document;
  const calls = [];
  const links = [];
  let state = "running";
  let failNext = "";
  let pendingBrowse;
  const overrides = new Map();
  const operation = () => ({ operation_id: "operation_1", kind: "package", state, error_code: null });
  const client = {
    async callServerTool(request) {
      calls.push(request);
      if (request.name === failNext) {
        failNext = "";
        return { structuredContent: { response_version: 2, status: "error", error_code: "authorization_denied", message: "/private/source" } };
      }
      let data;
      if (overrides.has(request.name)) data = await overrides.get(request.name)(request.arguments);
      else if (request.name === "access_status") data = { portal_url: "https://keepmorrow.example/portal", policies: {}, grants: [] };
      else if (request.name === "list_collections") data = { items: empty ? [] : [{ collection_id: "collection_1", generation }], next_grant_id: null };
      else if (request.name === "browse_collection") {
        if (pendingBrowse) await pendingBrowse;
        data = { total: 1, next_offset: null, items: [{ conversation_key: conversation, association: { state: "association_unknown" }, revision_count: 1,
          revisions: [{ title: hostile, revision_id: revision }], revisions_truncated: false }] };
      } else if (request.name === "search_collection") data = { items: request.arguments.query === "missing" ? [] : [{ title: hostile, excerpt: hostile, conversation_key: conversation, revision_id: revision }], truncated: false };
      else if (request.name === "read_revision") data = { title: "Historical revision", revision_id: revision, total_nodes: 2, next_offset: request.arguments.offset === 0 ? 1 : null,
        nodes: [{ id: "question", role: "user", parent_id: null, text: hostile, child_count: 2, children_ids: ["answer", "alternative"] }] };
      else if (request.name === "verify_collection") data = { verified: true, summary: { conversation_count: 1, unavailable_artifact_references: 2 } };
      else if (request.name === "list_operations") data = { items: [operation()], next_before_operation_id: null };
      else if (request.name === "get_operation") data = operation();
      else if (request.name === "cancel_operation") { state = "cancel_requested"; data = { operation: operation() }; }
      else throw new Error("Unexpected synthetic tool request.");
      return { structuredContent: { response_version: 2, status: "ok", data } };
    },
    async openLink({ url }) { links.push(url); return {}; },
  };
  const workspace = new Workspace(client);
  await workspace.ready();
  const node = (id) => dom.window.document.getElementById(id);
  const click = async (id) => { node(id).click(); await settle(); };
  const choose = async () => {
    await click("load-collections");
    node("collection").value = "0";
    node("collection").dispatchEvent(new dom.window.Event("change"));
  };
  const clickText = async (label) => {
    const button = [...dom.window.document.querySelectorAll("button")].find((item) => item.textContent === label);
    assert.ok(button, `Expected action ${label}`);
    button.click();
    await settle();
  };
  return { dom, calls, links, node, click, choose, clickText, overrides,
    fail(name) { failNext = name; },
    holdBrowse() { let release; pendingBrowse = new Promise((resolve) => { release = resolve; }); return release; },
  };
}

test("content requires an explicit user action and an immutable generation", async () => {
  const f = await fixture();
  assert.deepEqual(f.calls.map((call) => call.name), ["access_status"]);
  await f.choose();
  assert.deepEqual(f.calls.map((call) => call.name), ["access_status", "list_collections"]);
  await f.click("browse");
  const request = f.calls.at(-1);
  assert.equal(request.name, "browse_collection");
  assert.equal(request.arguments.generation, generation);
  assert.equal(request.arguments.collection_id, "collection_1");
  assert.ok(!("terms_version" in request.arguments));
  assert.match(f.node("conversations").textContent, /Project association unknown/);
  f.dom.window.close();
});

test("source titles, excerpts, and message text remain inert across revision pagination", async () => {
  const f = await fixture();
  await f.choose();
  await f.click("browse");
  assert.equal(f.node("conversations").querySelectorAll("img").length, 0);
  await f.clickText("Read: " + hostile);
  assert.match(f.node("messages").textContent, /Branching node · 2 child nodes/);
  assert.ok(f.node("messages").textContent.includes(hostile));
  assert.equal(f.node("messages").querySelectorAll("img").length, 0);
  await f.click("more-messages");
  assert.equal(f.calls.at(-1).arguments.revision_id, revision);
  assert.equal(f.calls.at(-1).arguments.offset, 1);
  assert.equal(f.node("more-messages").hidden, true);
  f.dom.window.close();
});

test("a pending content read does not prevent operation inspection and cancellation", async () => {
  const f = await fixture();
  await f.choose();
  const release = f.holdBrowse();
  await f.click("browse");
  assert.equal(f.node("browse").disabled, true);
  assert.equal(f.node("load-operations").disabled, false);
  await f.click("load-operations");
  await f.clickText("Request cancellation");
  assert.match(f.node("operations").textContent, /cancel requested/);
  release();
  await settle();
  f.dom.window.close();
});

test("a changed collection discards the delayed response from the old generation", async () => {
  const f = await fixture();
  await f.choose();
  const release = f.holdBrowse();
  await f.click("browse");
  f.node("collection").value = "";
  f.node("collection").dispatchEvent(new f.dom.window.Event("change"));
  release();
  await settle();
  assert.ok(!f.node("conversations").textContent.includes(hostile));
  assert.equal(f.node("browse").disabled, true);
  f.dom.window.close();
});

test("authorization failure shows bounded copy and never a server filesystem path", async () => {
  const f = await fixture();
  await f.choose();
  f.fail("browse_collection");
  await f.click("browse");
  assert.equal(f.node("status").getAttribute("role"), "alert");
  assert.match(f.node("status").textContent, /Review your current permissions/);
  assert.ok(!f.node("status").textContent.includes("/private/source"));
  f.dom.window.close();
});

test("empty grants disable content actions and trusted portal links use the host API", async () => {
  const f = await fixture({ empty: true });
  await f.click("load-collections");
  assert.match(f.node("status").textContent, /No collection is currently available/);
  assert.equal(f.node("browse").disabled, true);
  await f.click("portal");
  assert.deepEqual(f.links, ["https://keepmorrow.example/portal"]);
  f.dom.window.close();
});

test("search is passed literally and empty results are distinct from request failure", async () => {
  const f = await fixture();
  await f.choose();
  f.node("query").value = "[literal].*";
  await f.click("search");
  assert.equal(f.calls.at(-1).arguments.query, "[literal].*");
  assert.equal(f.node("conversations").querySelectorAll("img").length, 0);
  f.node("query").value = "missing";
  await f.click("search");
  assert.match(f.node("conversations").textContent, /No preserved text matched/);
  assert.equal(f.node("status").getAttribute("role"), "status");
  f.dom.window.close();
});

test("verification reports unavailable artifacts without implying account completeness", async () => {
  const f = await fixture();
  await f.choose();
  await f.click("verify");
  assert.match(f.node("coverage").textContent, /2 unavailable artifact reference/);
  assert.match(f.node("coverage").textContent, /Account completeness is not asserted/);
  f.dom.window.close();
});
