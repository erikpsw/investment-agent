import {
  generateProtectedResourceMetadata,
  metadataCorsOptionsRequestHandler,
} from "mcp-handler";

import { getAuth0Issuer } from "@/lib/auth0-token";
import { getPublicOrigin } from "@/lib/public-origin";

const optionsHandler = metadataCorsOptionsRequestHandler();

export async function GET(request: Request) {
  try {
    const metadata = generateProtectedResourceMetadata({
      authServerUrls: [getAuth0Issuer()],
      resourceUrl: getPublicOrigin(request),
    });
    return Response.json(metadata, {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "max-age=3600",
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Auth0 is not configured";
    return Response.json({ error: message }, { status: 503 });
  }
}

export { optionsHandler as OPTIONS };
