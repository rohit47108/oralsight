"use strict";

const expoPackageJson = require.resolve("expo/package.json");
const expoCliEntry = require.resolve("@expo/cli", {
  paths: [expoPackageJson],
});

require(expoCliEntry);
