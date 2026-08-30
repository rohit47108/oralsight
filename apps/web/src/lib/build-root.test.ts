import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { resolveWebBuildRoot } from "@/lib/build-root";

describe("web build root", () => {
  const appDirectory = resolve("workspace", "apps", "web");

  it("keeps Linux deployment tracing inside the repository", () => {
    expect(resolveWebBuildRoot(appDirectory, "linux")).toBe(
      resolve(appDirectory, "../.."),
    );
  });

  it("includes the short external pnpm store for Windows builds", () => {
    expect(resolveWebBuildRoot(appDirectory, "win32")).toBe(
      resolve(appDirectory, "../../../.."),
    );
  });
});
