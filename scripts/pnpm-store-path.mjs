import { existsSync, readdirSync, readFileSync } from "node:fs";
import { isAbsolute, join, resolve } from "node:path";

export function findPnpmVirtualStore(workspaceRoot, pathExists = existsSync) {
  const modulesMetadata = join(workspaceRoot, "node_modules", ".modules.yaml");
  if (pathExists(modulesMetadata)) {
    const contents = readFileSync(modulesMetadata, "utf8");
    let configuredStore;
    try {
      configuredStore = JSON.parse(contents).virtualStoreDir;
    } catch {
      configuredStore = /^virtualStoreDir:\s*["']?(.+?)["']?\s*$/m.exec(
        contents,
      )?.[1];
    }
    if (typeof configuredStore === "string") {
      const resolvedStore = isAbsolute(configuredStore)
        ? configuredStore
        : resolve(workspaceRoot, configuredStore);
      if (pathExists(resolvedStore)) return resolvedStore;
    }
  }

  const candidates = [
    join(workspaceRoot, ".pnpm"),
    join(workspaceRoot, "node_modules", ".pnpm"),
  ];
  const virtualStore = candidates.find(pathExists);

  if (!virtualStore) {
    throw new Error(
      "pnpm virtual store was not found; run pnpm install --frozen-lockfile",
    );
  }

  return virtualStore;
}

export function findInstalledPackageRootOrNull(
  virtualStore,
  packageName,
  packageVersion,
) {
  for (const entry of readdirSync(virtualStore, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;

    const packageRoot = join(
      virtualStore,
      entry.name,
      "node_modules",
      ...packageName.split("/"),
    );
    const manifestPath = join(packageRoot, "package.json");
    if (!existsSync(manifestPath)) continue;

    const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
    if (manifest.name === packageName && manifest.version === packageVersion) {
      return packageRoot;
    }
  }

  return null;
}

export function findInstalledPackageRoot(
  virtualStore,
  packageName,
  packageVersion,
) {
  const packageRoot = findInstalledPackageRootOrNull(
    virtualStore,
    packageName,
    packageVersion,
  );
  if (packageRoot) return packageRoot;

  throw new Error(
    `${packageName}@${packageVersion} is not installed in the pnpm virtual store`,
  );
}
