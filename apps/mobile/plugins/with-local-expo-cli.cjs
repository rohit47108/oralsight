const { withAppBuildGradle } = require("expo/config-plugins");

function replaceConfigurationLine(lines, matcher, replacement, label) {
  const matchingIndexes = lines.flatMap((line, index) =>
    matcher(line) ? [index] : [],
  );

  if (matchingIndexes.length !== 1) {
    throw new Error(`${label} configuration line was not found exactly once`);
  }

  const index = matchingIndexes[0];
  const indentation = lines[index].match(/^\s*/)?.[0] ?? "";
  lines[index] = `${indentation}${replacement}`;
}

function patchAppBuildGradle(contents) {
  const lines = contents.split("\n");
  replaceConfigurationLine(
    lines,
    (line) => line.includes("cliFile = new File") && line.includes("@expo/cli"),
    'cliFile = file("${projectRoot}/scripts/expo-cli-shim.cjs")',
    "Expo CLI",
  );
  const bundleCommandIndexes = lines.flatMap((line, index) =>
    line.trim() === 'bundleCommand = "export:embed"' ? [index] : [],
  );
  if (bundleCommandIndexes.length !== 1) {
    throw new Error(
      "Expo bundle command configuration line was not found exactly once",
    );
  }
  const bundleCommandIndex = bundleCommandIndexes[0];
  const indentation = lines[bundleCommandIndex].match(/^\s*/)?.[0] ?? "";
  lines.splice(
    bundleCommandIndex + 1,
    0,
    `${indentation}if ((findProperty("stoma3d.disableHermesSourceMaps") ?: false).toBoolean()) {`,
    `${indentation}    hermesFlags = ["-O"]`,
    `${indentation}}`,
  );
  return lines.join("\n");
}

function withLocalExpoCli(config) {
  return withAppBuildGradle(config, (androidConfig) => {
    if (androidConfig.modResults.language !== "groovy") {
      throw new Error("The local Expo CLI path plugin requires Groovy Gradle");
    }
    androidConfig.modResults.contents = patchAppBuildGradle(
      androidConfig.modResults.contents,
    );
    return androidConfig;
  });
}

module.exports = withLocalExpoCli;
module.exports.patchAppBuildGradle = patchAppBuildGradle;
