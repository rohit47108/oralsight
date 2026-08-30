import { resolve } from "node:path";

export function resolveWebBuildRoot(
  cwd: string,
  platform: NodeJS.Platform = process.platform,
): string {
  return resolve(cwd, platform === "win32" ? "../../../.." : "../..");
}
