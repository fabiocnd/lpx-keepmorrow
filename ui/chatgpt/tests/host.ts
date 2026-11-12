/** Synthetic MCP Apps host for browser evidence; never included in the app resource. */
import { AppBridge, PostMessageTransport } from "@modelcontextprotocol/ext-apps/app-bridge";

const scenario = new URLSearchParams(location.search).get("case");
const generation = "a".repeat(64);
const revision = "b".repeat(64);
const conversation = "c".repeat(64);
const title = scenario === "long" ? "A deliberately long preserved title ".repeat(12) : "A preserved design discussion";
const hostile = '<img src=x onerror="window.sourceExecuted=true">';
const testState = {
  calls: [] as { name: string; arguments: Record<string, unknown> }[],
  links: [] as string[],
  failNext: "",
  holdBrowse: false,
  releaseBrowse: null as (() => void) | null,
  operationState: "running",
};
(window as unknown as Record<string, unknown>).__keepTest = testState;

const frame = document.createElement("iframe");
frame.id = "keepmorrow";
frame.title = "LPX Keepmorrow synthetic host";
frame.style.cssText = "width:100%;height:1600px;border:0;display:block";
document.body.append(frame);
document.body.style.margin = "0";
const bridge = new AppBridge(null, { name: "Keepmorrow test host", version: "1.0.0" },
  { serverTools: {}, openLinks: {} }, { hostContext: { theme: "light", displayMode: "inline" } });

function operation() {
  return { operation_id: "operation_1", kind: "package", state: testState.operationState, error_code: null };
}

bridge.oncalltool = async (request) => {
  const args = request.arguments ?? {};
  testState.calls.push({ name: request.name, arguments: args });
  if (testState.failNext === request.name) {
    testState.failNext = "";
    return { content: [], isError: true, structuredContent: {
      response_version: 2, operation: request.name, status: "error", error_code: "authorization_denied",
      message: "/private/source must never be displayed",
    } };
  }
  let data: Record<string, unknown>;
  switch (request.name) {
    case "access_status":
      data = { portal_url: "https://keepmorrow.example/portal", policies: {}, grants: [] };
      break;
    case "list_collections":
      data = { items: scenario === "empty" ? [] : [{ collection_id: "collection_1", generation }], next_grant_id: null, content_inspected: false };
      break;
    case "browse_collection":
      if (testState.holdBrowse) await new Promise<void>((resolve) => { testState.releaseBrowse = resolve; });
      data = { total: 1, next_offset: null, items: [{
        conversation_key: conversation, association: { state: "association_unknown", project_id: null },
        revision_count: 2, revisions_truncated: false,
        revisions: [{ revision_id: revision, title, node_count: 3 }, { revision_id: "d".repeat(64), title: "A historical revision", node_count: 2 }],
      }] };
      break;
    case "search_collection":
      data = { items: args.query === "missing" ? [] : [{ conversation_key: conversation, revision_id: revision, title, excerpt: hostile, excerpt_truncated: false }], truncated: false };
      break;
    case "read_revision":
      data = { conversation_key: conversation, revision_id: args.revision_id, title, total_nodes: 2, next_offset: args.offset === 0 ? 1 : null,
        nodes: [{ id: "question", role: "user", parent_id: null, text: hostile + "\nKeep original bytes intact.", text_truncated: false,
          child_count: 2, children_ids: ["answer", "alternative"], children_truncated: false }] };
      break;
    case "verify_collection":
      data = { verified: true, summary: { conversation_count: 1, unavailable_artifact_references: 2 } };
      break;
    case "list_operations":
      data = { items: [operation()], next_before_operation_id: null };
      break;
    case "get_operation":
      data = operation();
      break;
    case "cancel_operation":
      testState.operationState = "cancel_requested";
      data = { disposition: "requested", operation: operation() };
      break;
    default: throw new Error("An unexpected tool was requested by the test application.");
  }
  return { content: [], structuredContent: { response_version: 2, operation: request.name, status: "ok", data } };
};
bridge.onopenlink = async ({ url }) => { testState.links.push(url); return {}; };
await bridge.connect(new PostMessageTransport(frame.contentWindow!, frame.contentWindow!));
frame.src = "/keepmorrow.html";
