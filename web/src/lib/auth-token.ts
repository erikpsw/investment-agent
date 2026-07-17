import { getAccessToken } from "@auth0/nextjs-auth0";

export class AuthenticationRequiredError extends Error {
  constructor(message = "请先登录后访问投资组合") {
    super(message);
    this.name = "AuthenticationRequiredError";
  }
}

export async function getPortfolioAccessToken(): Promise<string> {
  try {
    const token = await getAccessToken();
    if (!token) throw new AuthenticationRequiredError();
    return token;
  } catch (error) {
    if (error instanceof AuthenticationRequiredError) throw error;
    throw new AuthenticationRequiredError();
  }
}
