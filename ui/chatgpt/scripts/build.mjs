// Produce the self-contained MCP resource and its identical wheel asset from
// authored sources. Rebuild both outputs instead of editing generated copies.
import { build } from "esbuild";
import { readFile, readdir, mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const root = fileURLToPath(new URL("../", import.meta.url));
const result = await build({
  absWorkingDir: root,
  entryPoints: ["src/main.ts"],
  bundle: true,
  write: false,
  format: "esm",
  target: "es2022",
  platform: "browser",
  minify: true,
  legalComments: "inline",
  metafile: true,
});
// A script-closing sequence inside bundled literals must not end the enclosing
// HTML element. Function replacement also preserves literal dollar sequences.
const javascript = result.outputFiles[0].text.replaceAll("</script", "<\\/script");
const styles = await readFile(resolve(root, "src/styles.css"), "utf8");
const template = await readFile(resolve(root, "src/index.html"), "utf8");
const html = template.replace("/* KEEP_CSS */", styles).replace("/* KEEP_SCRIPT */", () => javascript);
await mkdir(resolve(root, "dist"), { recursive: true });
await writeFile(resolve(root, "dist/keepmorrow.html"), html);
const assets = resolve(root, "../../src/keepmorrow/integrations/chatgpt/assets");
await mkdir(assets, { recursive: true });
await writeFile(resolve(assets, "keepmorrow.html"), html);

// Record the licenses of actual bundled packages, not development dependencies.
// The private project's license does not supersede these upstream notices.
const includedInputs = new Set(Object.values(result.metafile.outputs).flatMap((output) =>
  Object.entries(output.inputs).filter(([, value]) => value.bytesInOutput > 0).map(([path]) => path)));
const packageNames = new Set([...includedInputs].flatMap((path) => {
  const match = /node_modules\/((?:@[^/]+\/)?[^/]+)/.exec(path);
  return match ? [match[1]] : [];
}));
let notices = "LPX Keepmorrow ChatGPT Interface — Third-Party Notices\n\n";
notices += "Project source: proprietary, Copyright 2026 Lopix Neural Inc. All rights reserved.\n";
notices += "The generated interface includes the following separately licensed packages.\n";
for (const name of [...packageNames].sort()) {
  const directory = resolve(root, "node_modules", name);
  const metadata = JSON.parse(await readFile(resolve(directory, "package.json"), "utf8"));
  const licenseName = (await readdir(directory)).find((name) => /^LICENSE(?:\.(?:md|txt))?$/i.test(name));
  if (!licenseName) throw new Error(`The bundled package ${name} has no recognized license file.`);
  const license = await readFile(resolve(directory, licenseName), "utf8");
  notices += `\n${"=".repeat(72)}\n${name} ${metadata.version} (${metadata.license})\n${"=".repeat(72)}\n${license.trim()}\n`;
}
await writeFile(resolve(root, "THIRD-PARTY-NOTICES.txt"), notices);
await writeFile(resolve(assets, "THIRD-PARTY-NOTICES.txt"), notices);
console.log(`Built bundled and wheel interface assets (${Buffer.byteLength(html)} HTML bytes).`);
