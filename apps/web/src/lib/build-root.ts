import { resolve } from "node:path";

export function resolveWebBuildRoot(
  cwd: string,
  environment: Readonly<Record<string, string | undefined>> = process.env,
): string {
  return resolve(cwd, environment.VERCEL === "1" ? "../.." : "../../../..");
}
