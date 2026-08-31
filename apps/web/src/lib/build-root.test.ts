import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { resolveWebBuildRoot } from "@/lib/build-root";

describe("web build root", () => {
  const appDirectory = resolve("workspace", "apps", "web");

  it("keeps Vercel deployment tracing inside the repository", () => {
    expect(resolveWebBuildRoot(appDirectory, { VERCEL: "1" })).toBe(
      resolve(appDirectory, "../.."),
    );
  });

  it("includes the short external pnpm store for other builds", () => {
    expect(resolveWebBuildRoot(appDirectory, {})).toBe(
      resolve(appDirectory, "../../../.."),
    );
  });
});
