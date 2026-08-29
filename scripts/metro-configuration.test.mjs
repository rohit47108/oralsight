import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

test("Metro resolves pnpm's store without pre-crawling it", () => {
  const metadata = JSON.parse(
    readFileSync(join(repositoryRoot, "node_modules", ".modules.yaml"), "utf8"),
  );
  const config = require("../apps/mobile/metro.config.cjs");
  const watchedFolders = (config.watchFolders ?? []).map((folder) =>
    resolve(folder).toLowerCase(),
  );

  assert.equal(
    watchedFolders.includes(resolve(metadata.virtualStoreDir).toLowerCase()),
    false,
    `Metro must not pre-crawl ${metadata.virtualStoreDir}`,
  );
});
