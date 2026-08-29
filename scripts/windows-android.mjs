#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  realpathSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

import {
  corepackEntrypointFromShim,
  createGradleBuildSteps,
  createWindowsAndroidPlan,
  formatWindowsBatchCommand,
  nodeEnvironmentForWindowsAndroidMode,
  parseWindowsAndroidArguments,
  parseSubstMappings,
} from "./windows-android-paths.mjs";

const HELP = `Usage: node scripts/windows-android.mjs <command> [--arch <architecture>]

Commands:
  doctor  Show the short-path configuration without changing anything
  setup   Install dependencies in the short store required by Windows
  prebuild  Regenerate the Android native project after setup
  build   Build the debug APK through the short drive alias
  install Build and install the debug app on a connected device
  build-release   Build the release APK with JavaScript embedded
  install-release Build and install the release app on a connected device

Architectures: x86_64 (default), arm64-v8a, armeabi-v7a, x86
`;

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(scriptDirectory, "..");
const generatedNodeModules = [
  join(repositoryRoot, "node_modules"),
  join(repositoryRoot, "apps", "mobile", "node_modules"),
  join(repositoryRoot, "apps", "web", "node_modules"),
  join(repositoryRoot, "packages", "contracts", "node_modules"),
];
const nativeCache = join(
  repositoryRoot,
  "apps",
  "mobile",
  "android",
  "app",
  ".cxx",
);
const removableDirectories = new Set(
  [...generatedNodeModules, nativeCache].map((path) =>
    resolve(path).toLowerCase(),
  ),
);

function run(command, arguments_, options = {}) {
  const result = spawnSync(command, arguments_, {
    cwd: options.cwd ?? repositoryRoot,
    encoding: "utf8",
    env: {
      ...process.env,
      NODE_ENV: process.env.NODE_ENV || "development",
    },
    shell: false,
    stdio: options.capture ? "pipe" : "inherit",
  });

  if (result.error) throw result.error;
  if (result.status !== 0) {
    const detail = options.capture ? `\n${result.stderr || result.stdout}` : "";
    throw new Error(`${command} exited with code ${result.status}${detail}`);
  }
  return result.stdout ?? "";
}

function readSubstOutput() {
  return run("subst.exe", [], { capture: true });
}

function runPnpm(arguments_) {
  const corepackShim = run("where.exe", ["corepack.cmd"], { capture: true })
    .split(/\r?\n/)
    .find(Boolean);
  if (!corepackShim) {
    throw new Error("Corepack is required to run the locked pnpm version");
  }
  const corepackEntrypoint = corepackEntrypointFromShim(corepackShim);
  if (!existsSync(corepackEntrypoint)) {
    throw new Error(`Corepack entrypoint was not found: ${corepackEntrypoint}`);
  }
  run(process.execPath, [corepackEntrypoint, "pnpm", ...arguments_]);
}

function runBatchFile(batchFile, arguments_, cwd) {
  const commandInterpreter =
    process.env.ComSpec || "C:\\Windows\\System32\\cmd.exe";
  run(
    commandInterpreter,
    ["/d", "/s", "/c", formatWindowsBatchCommand(batchFile, arguments_)],
    { cwd },
  );
}

function safeRemoveGeneratedDirectory(target) {
  const resolvedTarget = resolve(target);
  const relativeTarget = relative(repositoryRoot, resolvedTarget);
  const isInsideRepository =
    relativeTarget &&
    !relativeTarget.startsWith(`..${sep}`) &&
    relativeTarget !== "..";
  if (
    !isInsideRepository ||
    !removableDirectories.has(resolvedTarget.toLowerCase())
  ) {
    throw new Error(`Refusing to remove an unexpected path: ${resolvedTarget}`);
  }
  if (existsSync(resolvedTarget)) {
    rmSync(resolvedTarget, { force: true, maxRetries: 3, recursive: true });
  }
}

function isUsingVirtualStore(virtualStoreDirectory) {
  const reactNativePath = join(
    repositoryRoot,
    "apps",
    "mobile",
    "node_modules",
    "react-native",
  );
  if (!existsSync(reactNativePath)) return false;

  const installedPath = realpathSync(reactNativePath).toLowerCase();
  const storePrefix = `${resolve(virtualStoreDirectory).toLowerCase()}${sep}`;
  return installedPath.startsWith(storePrefix);
}

function ensureShortStore(plan) {
  if (!isUsingVirtualStore(plan.virtualStoreDirectory)) {
    for (const target of generatedNodeModules) {
      safeRemoveGeneratedDirectory(target);
    }
  }

  runPnpm([
    "install",
    "--frozen-lockfile",
    `--config.virtual-store-dir=${plan.virtualStoreDirectory}`,
  ]);

  if (!isUsingVirtualStore(plan.virtualStoreDirectory)) {
    throw new Error(
      `pnpm did not link the mobile workspace to ${plan.virtualStoreDirectory}`,
    );
  }
}

function ensureDriveAlias(plan) {
  if (plan.needsSubst) {
    run("subst.exe", [plan.drive, plan.repositoryRoot]);
  }

  const mappings = parseSubstMappings(readSubstOutput());
  const mappedTarget = mappings.get(plan.drive);
  if (
    !mappedTarget ||
    resolve(mappedTarget).toLowerCase() !==
      resolve(plan.repositoryRoot).toLowerCase()
  ) {
    throw new Error(`${plan.drive} is not mapped to ${plan.repositoryRoot}`);
  }
}

function ensureNativeProject() {
  const gradleWrapper = join(
    repositoryRoot,
    "apps",
    "mobile",
    "android",
    "gradlew.bat",
  );
  if (existsSync(gradleWrapper)) return;

  runPnpm([
    "--filter",
    "@oralsight/mobile",
    "exec",
    "expo",
    "prebuild",
    "--clean",
    "--platform",
    "android",
    "--no-install",
  ]);
}

function prepareNativeCache(plan) {
  const marker = join(nativeCache, ".oralsight-build-alias");
  const expected = plan.aliasRoot.toUpperCase();
  const existing = existsSync(marker)
    ? readFileSync(marker, "utf8").trim()
    : "";
  if (existsSync(nativeCache) && existing !== expected) {
    safeRemoveGeneratedDirectory(nativeCache);
  }
  mkdirSync(nativeCache, { recursive: true });
  writeFileSync(marker, `${expected}\n`);
}

function main() {
  if (process.argv.includes("--help") || process.argv.includes("-h")) {
    process.stdout.write(HELP);
    return;
  }
  if (process.platform !== "win32") {
    throw new Error("This helper is only needed on Windows");
  }

  const { architecture, command } = parseWindowsAndroidArguments(
    process.argv.slice(2),
    process.env.ORALSIGHT_ANDROID_ARCH || "x86_64",
  );
  process.env.NODE_ENV = nodeEnvironmentForWindowsAndroidMode(
    command,
    process.env.NODE_ENV,
  );
  const substOutput = readSubstOutput();
  const plan = createWindowsAndroidPlan({
    repositoryRoot,
    substOutput,
    userProfile: homedir(),
  });

  if (command === "doctor") {
    process.stdout.write(
      `${JSON.stringify(
        {
          ...plan,
          androidProjectExists: existsSync(
            join(repositoryRoot, "apps", "mobile", "android", "gradlew.bat"),
          ),
          dependenciesUseShortStore: isUsingVirtualStore(
            plan.virtualStoreDirectory,
          ),
        },
        null,
        2,
      )}\n`,
    );
    return;
  }

  if (
    ![
      "setup",
      "prebuild",
      "build",
      "install",
      "build-release",
      "install-release",
    ].includes(command)
  ) {
    throw new Error(`Unknown command: ${command}\n\n${HELP}`);
  }

  ensureShortStore(plan);
  if (command === "setup") return;

  if (command === "prebuild") {
    runPnpm([
      "--filter",
      "@oralsight/mobile",
      "exec",
      "expo",
      "prebuild",
      "--clean",
      "--platform",
      "android",
      "--no-install",
    ]);
    return;
  }

  ensureNativeProject();
  ensureDriveAlias(plan);
  prepareNativeCache(plan);
  const buildSteps = createGradleBuildSteps({
    architecture,
    mode: command,
    plan,
  });
  for (const step of buildSteps) {
    runBatchFile(step.executable, step.arguments, step.directory);
  }
}

try {
  main();
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : error}\n`);
  process.exitCode = 1;
}
