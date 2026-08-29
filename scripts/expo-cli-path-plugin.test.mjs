import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";

const require = createRequire(import.meta.url);
const {
  patchAppBuildGradle,
} = require("../apps/mobile/plugins/with-local-expo-cli.cjs");

test("keeps Expo CLI local and gates Hermes source maps for short-path builds", () => {
  const source = `react {
    reactNativeDir = new File(["node", "--print", "require.resolve('react-native/package.json')"].execute(null, rootDir).text.trim()).getParentFile().getAbsoluteFile()
    cliFile = new File(["node", "--print", "require.resolve('@expo/cli', { paths: [require.resolve('expo/package.json')] })"].execute(null, rootDir).text.trim())
    bundleCommand = "export:embed"
}`;

  assert.equal(
    patchAppBuildGradle(source),
    `react {
    reactNativeDir = new File(["node", "--print", "require.resolve('react-native/package.json')"].execute(null, rootDir).text.trim()).getParentFile().getAbsoluteFile()
    cliFile = file("\${projectRoot}/scripts/expo-cli-shim.cjs")
    bundleCommand = "export:embed"
    if ((findProperty("oralsight.disableHermesSourceMaps") ?: false).toBoolean()) {
        hermesFlags = ["-O"]
    }
}`,
  );
});

test("fails prebuild when Expo changes the CLI configuration template", () => {
  assert.throws(
    () =>
      patchAppBuildGradle(`react {
    reactNativeDir = new File(["node", "--print", "require.resolve('react-native/package.json')"].execute(null, rootDir).text.trim()).getParentFile().getAbsoluteFile()
    bundleCommand = "export:embed"
}`),
    /Expo CLI configuration line was not found/,
  );
});
