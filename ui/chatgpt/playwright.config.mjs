import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";

const chromiumPath = process.env.KEEPMORROW_CHROMIUM ?? (existsSync("/usr/bin/chromium") ? "/usr/bin/chromium" : undefined);
// Own the fixed-port fixture server for each run. Reusing an unrelated process
// would make screenshots and assertions describe an unverified application.
export default defineConfig({
  testDir: "./tests",
  testMatch: "*.spec.mjs",
  timeout: 20_000,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:4173",
    browserName: "chromium",
    launchOptions: chromiumPath ? { executablePath: chromiumPath } : {},
    screenshot: "only-on-failure",
  },
  webServer: { command: "node scripts/test-server.mjs", url: "http://127.0.0.1:4173", reuseExistingServer: false },
});
