import { Auth0Client } from "@auth0/nextjs-auth0/server";

import { hostedWorkspaceEnabled } from "@/lib/production-env";

let client: Auth0Client | null = null;

export function getAuth0Client(): Auth0Client {
  if (!hostedWorkspaceEnabled()) {
    throw new Error(
      "Stoma3D hosted accounts are disabled for this public-site deployment.",
    );
  }
  if (!client) {
    client = new Auth0Client({
      authorizationParameters: {
        audience: process.env.AUTH0_AUDIENCE ?? "stoma3d-platform-api",
        scope: "openid profile email offline_access",
      },
      enableAccessTokenEndpoint: false,
      signInReturnToPath: "/app",
    });
  }
  return client;
}
