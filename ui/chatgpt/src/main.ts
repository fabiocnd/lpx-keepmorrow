/** The official MCP Apps SDK owns transport, origin handling, and host lifecycle. */
import { App, applyDocumentTheme, applyHostStyleVariables } from "@modelcontextprotocol/ext-apps";
import { Workspace } from "./workspace.ts";

const app = new App({ name: "LPX Keepmorrow", version: "0.3.0" }, {}, { strict: true });
const workspace = new Workspace(app);

// Register notifications before connecting so initial host context and tool
// metadata cannot race handler installation during the SDK handshake.
app.ontoolresult = (result) => workspace.acceptToolResult(result);
app.onhostcontextchanged = (context) => {
  if (context.theme) applyDocumentTheme(context.theme);
  if (context.styles?.variables) applyHostStyleVariables(context.styles.variables);
};

try {
  await app.connect();
  const context = app.getHostContext();
  if (context?.theme) applyDocumentTheme(context.theme);
  if (context?.styles?.variables) applyHostStyleVariables(context.styles.variables);
  await workspace.ready();
} catch {
  workspace.connectionFailed();
}
