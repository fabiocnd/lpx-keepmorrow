// Run the built resource in Chromium through the official synthetic SDK host.
// Browser and visual evidence here excludes live OAuth and account installation.
import { test, expect } from "@playwright/test";

async function connect(page, suffix = "") {
  await page.goto("/" + suffix);
  const app = page.frameLocator("#keepmorrow");
  await expect(app.getByRole("status")).toContainText("Connected.");
  return app;
}

async function select(app) {
  await app.getByRole("button", { name: "Load authorized collections" }).click();
  await app.getByLabel("Collection and generation").selectOption("0");
}

test("official SDK handshake reads no collection content until an explicit action", async ({ page }) => {
  const app = await connect(page);
  expect(await page.evaluate(() => window.__keepTest.calls.map((call) => call.name))).toEqual(["access_status"]);
  await select(app);
  expect(await page.evaluate(() => window.__keepTest.calls.map((call) => call.name))).toEqual(["access_status", "list_collections"]);
  await app.getByRole("button", { name: "Browse conversations" }).click();
  await expect(app.getByText("Project association unknown", { exact: false })).toBeVisible();
  const browse = await page.evaluate(() => window.__keepTest.calls.find((call) => call.name === "browse_collection"));
  expect(browse.arguments.generation).toBe("a".repeat(64));
  expect(browse.arguments.collection_id).toBe("collection_1");
  expect(browse.arguments).not.toHaveProperty("terms_version");
  expect(browse.arguments).not.toHaveProperty("bearer");
});

test("historical revision and graph branches preserve hostile source as inert text", async ({ page }) => {
  const app = await connect(page);
  await select(app);
  await app.getByRole("button", { name: "Browse conversations" }).click();
  await app.getByRole("button", { name: "Read: A historical revision" }).click();
  await expect(app.getByText("Branching node · 2 child nodes.")).toBeVisible();
  await expect(app.locator("#messages")).toContainText('<img src=x onerror="window.sourceExecuted=true">');
  await expect(app.locator("#messages img")).toHaveCount(0);
  await app.getByRole("button", { name: "Next message nodes" }).click();
  await expect(app.getByRole("button", { name: "Next message nodes" })).toBeHidden();
  const request = await page.evaluate(() => window.__keepTest.calls.filter((call) => call.name === "read_revision").at(-1));
  expect(request.arguments.revision_id).toBe("d".repeat(64));
  expect(request.arguments.offset).toBe(1);
});

test("search is literal, empty results explicit, and excerpts never become markup", async ({ page }) => {
  const app = await connect(page);
  await select(app);
  await app.getByLabel("Search preserved text").fill("[literal].*");
  await app.getByRole("button", { name: "Search", exact: true }).click();
  await expect(app.locator(".excerpt")).toContainText("<img");
  await expect(app.locator(".excerpt img")).toHaveCount(0);
  await app.getByLabel("Search preserved text").fill("missing");
  await app.getByLabel("Search preserved text").press("Enter");
  await expect(app.getByText("No preserved text matched this phrase.")).toBeVisible();
});

test("operation cancellation remains responsive during a pending content read", async ({ page }) => {
  const app = await connect(page);
  await select(app);
  await page.evaluate(() => { window.__keepTest.holdBrowse = true; });
  await app.getByRole("button", { name: "Browse conversations" }).click();
  await app.getByRole("button", { name: "Refresh operations" }).click();
  await app.getByRole("button", { name: "Request cancellation" }).click();
  await expect(app.getByText("cancel requested", { exact: true })).toBeVisible();
  await page.evaluate(() => window.__keepTest.releaseBrowse());
});

test("revoked access reports a bounded explanation without private exception details", async ({ page }) => {
  const app = await connect(page);
  await select(app);
  await page.evaluate(() => { window.__keepTest.failNext = "browse_collection"; });
  await app.getByRole("button", { name: "Browse conversations" }).click();
  await expect(app.getByRole("alert")).toContainText("Review your current permissions");
  await expect(app.locator("body")).not.toContainText("/private/source");
});

test("empty access state and trusted portal use the official host link request", async ({ page }) => {
  const app = await connect(page, "?case=empty");
  await app.getByRole("button", { name: "Load authorized collections" }).click();
  await expect(app.getByRole("status")).toContainText("No collection is currently available");
  await expect(app.getByRole("button", { name: "Browse conversations" })).toBeDisabled();
  await app.getByRole("button", { name: "Open secure portal" }).click();
  await expect.poll(() => page.evaluate(() => window.__keepTest.links)).toEqual(["https://keepmorrow.example/portal"]);
});

test("320px viewport, long source titles, and keyboard controls stay usable", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 900 });
  const app = await connect(page, "?case=long");
  await app.getByRole("button", { name: "Load authorized collections" }).focus();
  await page.keyboard.press("Enter");
  await app.getByLabel("Collection and generation").selectOption("0");
  await app.getByRole("button", { name: "Browse conversations" }).focus();
  await page.keyboard.press("Enter");
  await expect(app.locator(".conversation")).toBeVisible();
  expect(await app.locator("html").evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true);
  await page.screenshot({ path: "test-results/keepmorrow-narrow.png", fullPage: true });
});

test("verified coverage keeps unavailable references visible", async ({ page }) => {
  const app = await connect(page);
  await select(app);
  await app.getByRole("button", { name: "Verify collection" }).click();
  await expect(app.locator("#coverage")).toContainText("2 unavailable artifact reference(s)");
  await expect(app.locator("#coverage")).toContainText("Account completeness is not asserted");
  await page.screenshot({ path: "test-results/keepmorrow-desktop.png", fullPage: true });
});
