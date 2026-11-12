// Exercise the installed SDK's real protocol over an in-memory transport. This
// proves compatibility with the synthetic bridge, not a live ChatGPT connection.
import assert from "node:assert/strict";
import test from "node:test";
import { App } from "@modelcontextprotocol/ext-apps";
import { AppBridge } from "@modelcontextprotocol/ext-apps/app-bridge";
import { InMemoryTransport } from "@modelcontextprotocol/client";
import { responseData } from "../src/contracts.ts";

test("official App and AppBridge negotiate and exchange the versioned tool result", async () => {
  const app = new App({ name: "Keepmorrow protocol test", version: "0.3.0" }, {}, { autoResize: false, strict: true });
  const bridge = new AppBridge(null, { name: "Synthetic host", version: "1.0.0" }, { serverTools: {}, openLinks: {} },
    { hostContext: { theme: "light", displayMode: "inline" } });
  const [host, view] = InMemoryTransport.createLinkedPair();
  const calls = [];
  const opened = [];
  bridge.oncalltool = async (request) => {
    calls.push(request);
    return { content: [], structuredContent: { response_version: 2, status: "ok", data: { portal_url: "https://keepmorrow.example/portal" } } };
  };
  bridge.onopenlink = async ({ url }) => { opened.push(url); return {}; };
  try {
    await bridge.connect(host);
    await app.connect(view);
    const data = responseData(await app.callServerTool({ name: "access_status", arguments: {} }));
    assert.equal(data.portal_url, "https://keepmorrow.example/portal");
    assert.equal(calls.length, 1);
    assert.equal(calls[0].name, "access_status");
    await app.openLink({ url: data.portal_url });
    assert.deepEqual(opened, ["https://keepmorrow.example/portal"]);
    assert.equal(app.getHostContext().theme, "light");
  } finally {
    await app.close();
    await bridge.close();
  }
});
