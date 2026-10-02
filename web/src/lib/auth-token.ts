import { getAccessToken } from "@auth0/nextjs-auth0";

export class AuthenticationRequiredError extends Error {
  constructor(message = "请先登录后访问投资组合") {
    super(message);
    this.name = "AuthenticationRequiredError";
  }
}

let pendingAccessToken: Promise<string> | null = null;

async function requestPortfolioAccessToken(): Promise<string> {
  try {
    const token = await getAccessToken();
    if (!token) throw new AuthenticationRequiredError();
    return token;
  } catch (error) {
    if (error instanceof AuthenticationRequiredError) throw error;
    throw new AuthenticationRequiredError();
  }
}

export function getPortfolioAccessToken(): Promise<string> {
  if (!pendingAccessToken) {
    pendingAccessToken = requestPortfolioAccessToken().finally(() => { pendingAccessToken = null; });
  }
  return pendingAccessToken;
}
