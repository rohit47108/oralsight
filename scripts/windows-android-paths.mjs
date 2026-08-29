import { existsSync } from "node:fs";
import { win32 } from "node:path";

const BUILD_DRIVES = "OPQRSTUVWXYZ".split("").map((letter) => `${letter}:`);
const ANDROID_ARCHITECTURES = new Set([
  "arm64-v8a",
  "armeabi-v7a",
  "x86",
  "x86_64",
]);

function normalizeComparablePath(value) {
  return win32
    .normalize(value)
    .replace(/[\\/]+$/, "")
    .toLowerCase();
}

export function corepackEntrypointFromShim(shimPath) {
  return win32.join(
    win32.dirname(shimPath),
    "node_modules",
    "corepack",
    "dist",
    "corepack.js",
  );
}

export function formatWindowsBatchCommand(batchFile, arguments_) {
  if (
    !/^[A-Za-z]:\\(?:[A-Za-z0-9_.-]+\\)*[A-Za-z0-9_.-]+\.bat$/.test(batchFile)
  ) {
    throw new Error(`Unsafe batch file path: ${batchFile}`);
  }
  const unsafeArgument = arguments_.find(
    (argument) => !/^[A-Za-z0-9_.:=\-\[\]]+$/.test(argument),
  );
  if (unsafeArgument) {
    throw new Error(`Unsafe batch argument: ${unsafeArgument}`);
  }
  return `${batchFile} ${arguments_.join(" ")}`;
}

export function parseSubstMappings(output) {
  const mappings = new Map();

  for (const line of output.split(/\r?\n/)) {
    const match = /^([A-Za-z]):\\: => (.+)$/.exec(line.trim());
    if (!match) continue;
    mappings.set(`${match[1].toUpperCase()}:`, win32.normalize(match[2]));
  }

  return mappings;
}

export function createWindowsAndroidPlan({
  repositoryRoot,
  userProfile,
  substOutput = "",
  driveExists = existsSync,
}) {
  const normalizedRepositoryRoot = win32.normalize(repositoryRoot);
  const repositoryKey = normalizeComparablePath(normalizedRepositoryRoot);
  const mappings = parseSubstMappings(substOutput);

  let drive = [...mappings].find(
    ([, target]) => normalizeComparablePath(target) === repositoryKey,
  )?.[0];
  let needsSubst = false;

  if (!drive) {
    drive = BUILD_DRIVES.find(
      (candidate) => !mappings.has(candidate) && !driveExists(`${candidate}\\`),
    );
    needsSubst = true;
  }

  if (!drive) {
    throw new Error(
      "No free drive letter is available for the short Android build path",
    );
  }

  const aliasRoot = `${drive}\\`;
  return {
    aliasRoot,
    drive,
    gradleDirectory: win32.join(aliasRoot, "apps", "mobile", "android"),
    needsSubst,
    repositoryRoot: normalizedRepositoryRoot,
    virtualStoreDirectory: win32.join(userProfile, ".osp"),
  };
}

export function createGradleInvocation(mode, architecture) {
  if (!ANDROID_ARCHITECTURES.has(architecture)) {
    throw new Error(`Unsupported Android architecture: ${architecture}`);
  }

  const tasks = {
    build: "app:assembleDebug",
    "build-release": "app:assembleRelease",
    install: "app:installDebug",
    "install-release": "app:installRelease",
  };
  const task = tasks[mode];
  if (!task) {
    throw new Error(`Unsupported Android build mode: ${mode}`);
  }

  const arguments_ = [
    task,
    `-PreactNativeArchitectures=${architecture}`,
    "-Pkotlin.incremental=false",
  ];
  if (mode.endsWith("-release")) {
    arguments_.push("-Poralsight.disableHermesSourceMaps=true");
  }
  arguments_.push("--stacktrace");

  return {
    arguments: arguments_,
    executable: "gradlew.bat",
  };
}

export function nodeEnvironmentForWindowsAndroidMode(mode, currentValue) {
  if (mode === "build-release" || mode === "install-release") {
    return "production";
  }
  return currentValue || "development";
}

export function createGradleBuildSteps({ architecture, mode, plan }) {
  const invocation = createGradleInvocation(mode, architecture);
  return [
    {
      arguments: invocation.arguments,
      directory: plan.gradleDirectory,
      executable: win32.join(plan.gradleDirectory, invocation.executable),
    },
  ];
}

export function parseWindowsAndroidArguments(
  arguments_,
  defaultArchitecture = "x86_64",
) {
  const [command = "doctor", ...rawArguments] = arguments_;
  const rest = rawArguments.filter((argument) => argument !== "--");
  let architecture = defaultArchitecture;

  for (let index = 0; index < rest.length; index += 1) {
    if (rest[index] !== "--arch" || !rest[index + 1]) {
      throw new Error(`Unknown argument: ${rest[index]}`);
    }
    architecture = rest[index + 1];
    index += 1;
  }

  return { architecture, command };
}
