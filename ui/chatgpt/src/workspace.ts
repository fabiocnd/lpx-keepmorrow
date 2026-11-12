/** Render server-owned records without interpreting imported markup or links.
 * Copyright 2026 Lopix Neural Inc. All rights reserved.
 */

import {
  associationLabel, collectionRef, integer, items, nextOffset, object, portalUrl,
  responseData, text, type CollectionRef, type Document, type ToolClient, type ToolReply,
} from "./contracts.ts";

function element<K extends keyof HTMLElementTagNameMap>(tag: K, content = "", className = ""): HTMLElementTagNameMap[K] {
  // Imported titles and message bodies are plain text even when they contain
  // markup or URLs. Creating a node never activates preserved source content.
  const node = document.createElement(tag);
  node.textContent = content;
  node.className = className;
  return node;
}

function byId<T extends HTMLElement>(id: string): T {
  const value = document.getElementById(id);
  if (!value) throw new Error("The interface document is incomplete.");
  return value as T;
}

function action(label: string, callback: () => Promise<void>, className = "secondary"): HTMLButtonElement {
  const button = element("button", label, className);
  button.type = "button";
  button.addEventListener("click", () => { void callback(); });
  return button;
}

const OPERATION_STATES = new Set([
  "queued", "running", "verifying", "completed", "partial", "cancel_requested",
  "cancelled", "interrupted", "failed", "expired",
]);

/**
 * Coordinate one view's bounded reads and operation controls through the host.
 * Selection versions discard stale replies; they do not cancel server work.
 * Human consent, plan review, and file transfer remain in the trusted portal.
 */
export class Workspace {
  private readonly client: ToolClient;
  private portal: string | null = null;
  private connected = false;
  private selected: CollectionRef | null = null;
  private collections: CollectionRef[] = [];
  private collectionCursor: string | null = null;
  private nextConversationOffset: number | null = null;
  private revision: { conversation_key: string; revision_id: string } | null = null;
  private nextMessageOffset: number | null = null;
  private operationCursor: string | null = null;
  private selectionVersion = 0;
  private readonly requests = new Set<string>();

  constructor(client: ToolClient) {
    this.client = client;
    byId("portal").addEventListener("click", () => void this.run("portal", async () => {
      if (!this.portal) throw new Error("A trusted portal address is not available.");
      if ((await this.client.openLink({ url: this.portal })).isError) {
        throw new Error("The host could not open the secure portal.");
      }
    }));
    byId("load-collections").addEventListener("click", () => void this.loadCollections(false));
    byId("more-collections").addEventListener("click", () => void this.loadCollections(true));
    byId<HTMLSelectElement>("collection").addEventListener("change", (event) => {
      const value = (event.target as HTMLSelectElement).value;
      this.selected = value === "" ? null : this.collections[Number(value)] ?? null;
      this.selectionVersion += 1;
      this.clearContent();
      this.controls();
    });
    byId("browse").addEventListener("click", () => void this.browse(0));
    byId("verify").addEventListener("click", () => void this.verify());
    byId("search-form").addEventListener("submit", (event) => {
      event.preventDefault();
      void this.search();
    });
    byId("more-conversations").addEventListener("click", () => {
      if (this.nextConversationOffset !== null) void this.browse(this.nextConversationOffset);
    });
    byId("more-messages").addEventListener("click", () => {
      if (this.revision && this.nextMessageOffset !== null) void this.readRevision(this.revision, this.nextMessageOffset);
    });
    byId("close-revision").addEventListener("click", () => {
      byId("revision-section").hidden = true;
      byId("messages").replaceChildren();
      this.revision = null;
      byId("browse").focus();
    });
    byId("load-operations").addEventListener("click", () => void this.loadOperations(false));
    byId("more-operations").addEventListener("click", () => void this.loadOperations(true));
  }

  async ready(): Promise<void> {
    // Establish available metadata without choosing a collection or reading
    // its contents on the user's behalf.
    this.connected = true;
    this.controls();
    await this.run("access", async () => this.renderAccess(await this.call("access_status")));
  }

  acceptToolResult(reply: ToolReply): void {
    // Host notifications may describe a model-initiated tool. Only access
    // metadata updates this initial view; content still requires an explicit
    // user selection and read action within the interface.
    try {
      const envelope = object(reply.structuredContent);
      if (envelope.operation === "render_keepmorrow" || envelope.operation === "access_status") {
        this.renderAccess(responseData(reply));
      }
    } catch {
      this.status("The host returned an unsupported interface response.", true);
    }
  }

  connectionFailed(): void {
    this.connected = false;
    this.controls();
    this.status("This interface needs a connected MCP Apps host. Reopen Keepmorrow from the authenticated connection.", true);
  }

  private renderAccess(data: Document): void {
    this.portal = portalUrl(data.portal_url);
    this.controls();
    this.status("Connected. Choose which authorized material to inspect.");
  }

  private controls(): void {
    for (const name of ["load-collections", "load-operations"]) {
      byId<HTMLButtonElement>(name).disabled = !this.connected;
    }
    byId<HTMLButtonElement>("portal").disabled = !this.connected || this.portal === null;
    byId<HTMLSelectElement>("collection").disabled = !this.connected || !this.collections.length;
    for (const name of ["browse", "verify", "search"]) {
      byId<HTMLButtonElement>(name).disabled = !this.connected || !this.selected || this.requests.has("content");
    }
    byId<HTMLInputElement>("query").disabled = !this.connected || !this.selected;
  }

  private status(message: string, failed = false): void {
    const target = byId("status");
    target.textContent = message;
    target.classList.toggle("error", failed);
    target.setAttribute("role", failed ? "alert" : "status");
  }

  private async call(name: string, args: Document = {}): Promise<Document> {
    return responseData(await this.client.callServerTool({ name, arguments: args }));
  }

  private async run(group: string, task: () => Promise<void>): Promise<void> {
    // Suppress duplicate work within a group without queuing browser requests.
    // Operation controls remain usable while a content read occupies its group.
    if (!this.connected || this.requests.has(group)) return;
    this.requests.add(group);
    this.controls();
    try {
      await task();
    } catch (error) {
      this.status(error instanceof Error ? error.message : "The request could not be completed.", true);
    } finally {
      this.requests.delete(group);
      this.controls();
    }
  }

  private clearContent(): void {
    byId("conversations").replaceChildren(element("p", "Select Browse conversations or search a phrase to inspect this generation.", "empty"));
    byId("revision-section").hidden = true;
    byId("messages").replaceChildren();
    byId("more-conversations").hidden = true;
    byId("coverage").textContent = "Only explicitly supplied material is available. Account completeness is not asserted.";
    this.revision = null;
    this.nextConversationOffset = null;
  }

  private async loadCollections(append: boolean): Promise<void> {
    await this.run("collections", async () => {
      this.status("Loading authorized collection references…");
      const data = await this.call("list_collections", { limit: 20, after_grant_id: append ? this.collectionCursor : null });
      const candidates = items(data.items, 50).map(collectionRef);
      const combined = append ? [...this.collections, ...candidates] : candidates;
      const unique = new Map(combined.map((item) => [item.collection_id + ":" + item.generation, item]));
      // Cap the selector's retained references independently of server paging.
      // The displayed count describes this view, not all account collections.
      this.collections = [...unique.values()].slice(0, 200);
      this.collectionCursor = data.next_grant_id === null || data.next_grant_id === undefined ? null : text(data.next_grant_id, 128);
      const selector = byId<HTMLSelectElement>("collection");
      selector.replaceChildren(element("option", this.collections.length ? "Choose a collection" : "No authorized collections"));
      selector.options[0]!.value = "";
      this.collections.forEach((item, index) => {
        const option = element("option", `${item.collection_id} · ${item.generation.slice(0, 12)}`);
        option.value = String(index);
        option.title = `Collection ${item.collection_id}; generation ${item.generation}`;
        selector.append(option);
      });
      this.selected = null;
      this.selectionVersion += 1;
      this.clearContent();
      byId("more-collections").hidden = !this.collectionCursor || this.collections.length >= 200;
      this.status(this.collections.length ? `${this.collections.length} authorized collection reference(s). Select a generation to continue.`
        : "No collection is currently available. Review consent and resource permissions in the secure portal.");
    });
  }

  private async browse(offset: number, revisionOffset = 0): Promise<void> {
    if (!this.selected) return;
    const selection = this.selected;
    const version = this.selectionVersion;
    await this.run("content", async () => {
      this.status("Verifying and browsing the selected generation…");
      const data = await this.call("browse_collection", {
        ...selection, offset, limit: 20, revision_offset: revisionOffset, revision_limit: 10,
      });
      if (version !== this.selectionVersion) return;
      const rows = items(data.items, 50);
      const cards = rows.map((row) => {
        const revisions = items(row.revisions, 20);
        const key = text(row.conversation_key, 128);
        const latest = revisions.at(-1);
        const card = element("article", "", "conversation");
        card.append(element("h3", latest ? text(latest.title, 512) : "Conversation"));
        card.append(element("p", `${associationLabel(row.association)} · ${integer(row.revision_count)} retained revision(s)`, "helper"));
        const buttons = element("div", "", "revision-buttons");
        for (const revision of revisions) {
          const revisionId = text(revision.revision_id, 128);
          buttons.append(action(`Read: ${text(revision.title, 512) || "Untitled revision"}`, () =>
            this.readRevision({ conversation_key: key, revision_id: revisionId }, 0)));
        }
        const next = nextOffset(row.next_revision_offset);
        if (next !== null) buttons.append(action("More retained revisions", () => this.browse(offset, next), "quiet"));
        card.append(buttons);
        if (row.revisions_truncated === true) card.append(element("p", "Only a page of revisions is shown.", "helper"));
        return card;
      });
      byId("conversations").replaceChildren(...(cards.length ? cards : [element("p", "No conversations are present in this page.", "empty")]));
      this.nextConversationOffset = nextOffset(data.next_offset);
      byId("more-conversations").hidden = this.nextConversationOffset === null;
      this.status(`Showing ${rows.length} of ${integer(data.total)} conversation(s), starting at ${offset + (rows.length ? 1 : 0)}.`);
    });
  }

  private async search(): Promise<void> {
    if (!this.selected) return;
    const selection = this.selected;
    const version = this.selectionVersion;
    const query = byId<HTMLInputElement>("query").value;
    if (!query.trim()) { this.status("Enter a phrase to search preserved text.", true); return; }
    await this.run("content", async () => {
      this.status("Searching retained revisions…");
      const data = await this.call("search_collection", { ...selection, query, limit: 20 });
      if (version !== this.selectionVersion) return;
      const rows = items(data.items, 50);
      const cards = rows.map((row) => {
        const card = element("article", "", "conversation");
        card.append(element("h3", text(row.title, 512)), element("p", text(row.excerpt, 4096), "excerpt"));
        const reference = { conversation_key: text(row.conversation_key, 128), revision_id: text(row.revision_id, 128) };
        card.append(action("Read this revision", () => this.readRevision(reference, 0)));
        if (row.excerpt_truncated === true) card.append(element("p", "This excerpt is shortened.", "helper"));
        return card;
      });
      byId("conversations").replaceChildren(...(cards.length ? cards : [element("p", "No preserved text matched this phrase.", "empty")]));
      byId("more-conversations").hidden = true;
      this.status(`${rows.length} matching result(s).${data.truncated === true ? " Results are limited; narrow the phrase to inspect more." : ""}`);
    });
  }

  private async readRevision(reference: { conversation_key: string; revision_id: string }, offset: number): Promise<void> {
    if (!this.selected) return;
    const selection = this.selected;
    const version = this.selectionVersion;
    await this.run("content", async () => {
      this.status("Reading the selected historical revision…");
      const data = await this.call("read_revision", { ...selection, ...reference, offset, limit: 20 });
      if (version !== this.selectionVersion) return;
      const nodes = items(data.nodes, 50);
      const cards = nodes.map((node) => {
        const card = element("article", "", "message");
        const role = node.role === null ? "Structural node" : text(node.role, 128);
        card.append(element("div", role, "message-role"), element("p", text(node.text, 4096), "message-body"));
        const children = integer(node.child_count);
        if (children > 1) card.append(element("p", `Branching node · ${children} child nodes.`, "helper"));
        if (node.text_truncated === true) card.append(element("p", "This message is shortened in this view.", "helper"));
        const details = element("details");
        details.append(element("summary", "Preserved graph identifiers"));
        if (!Array.isArray(node.children_ids) || node.children_ids.length > 32) throw new Error("The graph page is unsupported.");
        details.append(element("p", `Node: ${text(node.id)}\nParent: ${node.parent_id === null ? "No parent" : text(node.parent_id)}\nChildren: ${node.children_ids.map((value) => text(value)).join(", ") || "None"}`, "node-details"));
        if (node.children_truncated === true) details.append(element("p", "Child identifiers are shortened in this page."));
        card.append(details);
        return card;
      });
      byId("revision-title").textContent = text(data.title, 512) || "Untitled revision";
      byId("revision-context").textContent = `Explicit historical revision ${text(data.revision_id, 128).slice(0, 16)} · ${integer(data.total_nodes)} preserved node(s). Display order does not collapse branches.`;
      byId("messages").replaceChildren(...(cards.length ? cards : [element("p", "No message nodes are present in this page.", "empty")]));
      byId("revision-section").hidden = false;
      this.revision = reference;
      this.nextMessageOffset = nextOffset(data.next_offset);
      byId("more-messages").hidden = this.nextMessageOffset === null;
      this.status(`Showing ${nodes.length} node(s) from the selected revision.`);
    });
  }

  private async verify(): Promise<void> {
    if (!this.selected) return;
    const selection = this.selected;
    const version = this.selectionVersion;
    await this.run("content", async () => {
      this.status("Checking collection bytes and metadata…");
      const data = await this.call("verify_collection", { ...selection });
      if (version !== this.selectionVersion) return;
      if (data.verified !== true) throw new Error("The server did not report successful collection verification.");
      const summary = data.summary === undefined ? null : object(data.summary);
      byId("coverage").textContent = summary
        ? `Local collection verification passed. ${integer(summary.conversation_count)} conversation(s); ${integer(summary.unavailable_artifact_references)} unavailable artifact reference(s). Account completeness is not asserted.`
        : "Local collection verification passed. Account completeness and remote delivery are not asserted.";
      this.status("Collection verification passed for the selected generation.");
    });
  }

  private renderOperation(value: Document): HTMLElement {
    const id = text(value.operation_id, 128);
    const state = text(value.state, 32);
    if (!OPERATION_STATES.has(state)) throw new Error("The operation state is unsupported.");
    const card = element("article", "", "operation");
    const heading = element("div", "", "operation-heading");
    heading.append(element("h3", `${text(value.kind, 32)} · ${id}`), element("span", state.replaceAll("_", " "), "operation-status"));
    card.append(heading);
    if (state === "partial") card.append(element("p", "Verified output is available with documented coverage limits.", "helper"));
    if (value.disclosure === "authorization_required") card.append(element("p", "Current authorization is required to disclose this output.", "helper"));
    if (value.error_code !== null && value.error_code !== undefined) card.append(element("p", `Result category: ${text(value.error_code, 128)}`, "helper"));
    const actions = element("div", "", "operation-actions");
    actions.append(action("Refresh status", () => this.run("operation:" + id, async () => {
      const current = await this.call("get_operation", { operation_id: id });
      card.replaceWith(this.renderOperation(current));
      this.status("Operation status refreshed.");
    }), "secondary"));
    if (["queued", "running", "verifying", "interrupted"].includes(state)) {
      actions.append(action("Request cancellation", () => this.run("operation:" + id, async () => {
        await this.call("cancel_operation", { operation_id: id });
        card.replaceWith(this.renderOperation(await this.call("get_operation", { operation_id: id })));
        this.status("Cancellation was checked. A publication already authorized may finish privately.");
      }), "danger"));
    }
    card.append(actions);
    return card;
  }

  private async loadOperations(earlier: boolean): Promise<void> {
    await this.run("operations", async () => {
      this.status("Loading your operation status…");
      const data = await this.call("list_operations", { limit: 20, before_operation_id: earlier ? this.operationCursor : null });
      const rows = items(data.items, 100);
      const cards = rows.map((row) => this.renderOperation(row));
      byId("operations").replaceChildren(...(cards.length ? cards : [element("p", "No reviewed operations are available in this page.", "empty")]));
      this.operationCursor = data.next_before_operation_id === null || data.next_before_operation_id === undefined
        ? null : text(data.next_before_operation_id, 128);
      byId("more-operations").hidden = this.operationCursor === null;
      this.status(`${rows.length} operation(s) shown. Open the secure portal to review or download results.`);
    });
  }
}
