import { Auth0Client } from "@auth0/nextjs-auth0/server";

const audience = process.env.AUTH0_AUDIENCE?.trim();

export const auth0 = new Auth0Client({
  appBaseUrl: process.env.APP_BASE_URL,
  authorizationParameters: {
    ...(audience ? { audience } : {}),
    scope: process.env.AUTH0_SCOPE || "openid profile email",
  },
  routes: {
    login: "/auth/login",
    callback: "/auth/callback",
    logout: "/auth/logout",
  },
  enableAccessTokenEndpoint: true,
});
