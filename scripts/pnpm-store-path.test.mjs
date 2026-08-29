import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { test } from "node:test";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { findPnpmVirtualStore } from "./pnpm-store-path.mjs";

test("prefers the short workspace-root virtual store", () => {
  const workspaceRoot = join("C:", "workspace");
  const expected = join(workspaceRoot, ".pnpm");

  assert.equal(
    findPnpmVirtualStore(workspaceRoot, (candidate) => candidate === expected),
    expected,
  );
});

test("supports the default pnpm virtual store as a fallback", () => {
  const workspaceRoot = join("C:", "workspace");
  const expected = join(workspaceRoot, "node_modules", ".pnpm");

  assert.equal(
    findPnpmVirtualStore(workspaceRoot, (candidate) => candidate === expected),
    expected,
  );
});

test("finds a package when pnpm hashes the virtual-store directory name", async (t) => {
  const { findInstalledPackageRoot } = await import("./pnpm-store-path.mjs");
  assert.equal(typeof findInstalledPackageRoot, "function");

  const virtualStore = mkdtempSync(join(tmpdir(), "oralsight-pnpm-store-"));
  t.after(() => rmSync(virtualStore, { force: true, recursive: true }));

  const packageRoot = join(
    virtualStore,
    "image-s_cff0d02e04907eba2d1d1be0f37ccd93",
    "node_modules",
    "image-size",
  );
  mkdirSync(packageRoot, { recursive: true });
  writeFileSync(
    join(packageRoot, "package.json"),
    JSON.stringify({ name: "image-size", version: "1.2.1" }),
  );

  assert.equal(
    findInstalledPackageRoot(virtualStore, "image-size", "1.2.1"),
    packageRoot,
  );
});

test("uses the external virtual store recorded by pnpm", (t) => {
  const workspaceRoot = mkdtempSync(join(tmpdir(), "oralsight-workspace-"));
  t.after(() => rmSync(workspaceRoot, { force: true, recursive: true }));

  const staleWorkspaceStore = join(workspaceRoot, ".pnpm");
  const externalStore = join(workspaceRoot, "short-store");
  mkdirSync(join(workspaceRoot, "node_modules"), { recursive: true });
  mkdirSync(staleWorkspaceStore);
  mkdirSync(externalStore);
  writeFileSync(
    join(workspaceRoot, "node_modules", ".modules.yaml"),
    JSON.stringify({ virtualStoreDir: externalStore }),
  );

  assert.equal(findPnpmVirtualStore(workspaceRoot), externalStore);
});
