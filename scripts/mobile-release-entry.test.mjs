import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const mobilePackageUrl = new URL(
  "../apps/mobile/package.json",
  import.meta.url,
);
const mobileEntryUrl = new URL("../apps/mobile/index.js", import.meta.url);

test("the mobile entry owns its route context for embedded release bundles", async () => {
  const mobilePackage = JSON.parse(await readFile(mobilePackageUrl, "utf8"));
  const mobileEntry = await readFile(mobileEntryUrl, "utf8");

  assert.equal(mobilePackage.main, "index.js");
  assert.match(mobileEntry, /require\.context\("\.\/app"\)/);
  assert.match(mobileEntry, /registerRootComponent\(App\)/);
});
