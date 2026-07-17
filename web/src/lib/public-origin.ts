export function getPublicOrigin(request: Request): string {
  const configured = process.env.APP_BASE_URL?.trim();
  if (configured) return new URL(configured).origin;

  const forwardedHost = request.headers.get("x-forwarded-host");
  const forwardedProto = request.headers.get("x-forwarded-proto") || "https";
  if (forwardedHost) return `${forwardedProto}://${forwardedHost}`;
  return new URL(request.url).origin;
}
