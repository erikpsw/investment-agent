import { auth0 } from "@/lib/auth0";
import { toPublicUserProfile } from "@/lib/user-profile";

export async function GET() {
  const session = await auth0.getSession();
  const profile = toPublicUserProfile(session?.user);
  const user = session ? profile : null;

  return Response.json(
    { user },
    { headers: { "Cache-Control": "private, no-store" } },
  );
}
