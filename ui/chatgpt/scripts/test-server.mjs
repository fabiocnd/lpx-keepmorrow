import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { build } from "esbuild";

const host = await build({ entryPoints: ["tests/host.ts"], bundle: true, write: false, platform: "browser", format: "esm", target: "es2022" });
const html = await readFile("dist/keepmorrow.html");
const index = '<!doctype html><html lang="en-US"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Synthetic Keepmorrow MCP Apps host</title></head><body><script type="module" src="/host.js"></script></body></html>';
createServer((request, response) => {
  const path = new URL(request.url, "http://127.0.0.1:4173").pathname;
  const content = path === "/" ? index : path === "/host.js" ? host.outputFiles[0].text : path === "/keepmorrow.html" ? html : null;
  response.statusCode = content === null ? 404 : 200;
  response.setHeader("Content-Type", path.endsWith(".js") ? "text/javascript; charset=utf-8" : "text/html; charset=utf-8");
  response.setHeader("Cache-Control", "no-store");
  response.end(content ?? "Not found");
}).listen(4173, "127.0.0.1");
