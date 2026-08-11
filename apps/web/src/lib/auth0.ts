import { Auth0Client } from "@auth0/nextjs-auth0/server";

const audience = process.env.AUTH0_AUDIENCE ?? "oralsight-platform-api";

export const auth0 = new Auth0Client({
  authorizationParameters: {
    audience,
    scope: "openid profile email offline_access",
  },
  enableAccessTokenEndpoint: false,
  signInReturnToPath: "/app",
});
