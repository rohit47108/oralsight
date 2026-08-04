export function routeRequiresConsent(segments: readonly string[]): boolean {
  const root = segments[0];
  return Boolean(root && root !== "index" && root !== "onboarding");
}
