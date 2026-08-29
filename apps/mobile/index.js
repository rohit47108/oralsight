import { registerRootComponent } from "expo";
import { ExpoRoot } from "expo-router";
import React from "react";

const routeContext = require.context("./app");

function App() {
  return <ExpoRoot context={routeContext} />;
}

registerRootComponent(App);
