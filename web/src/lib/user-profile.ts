export interface PublicUserProfile {
  name?: string;
  email?: string;
  picture?: string;
}

function cleanString(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const cleaned = value.trim();
  return cleaned || undefined;
}

function safeImageUrl(value: unknown): string | undefined {
  const cleaned = cleanString(value);
  if (!cleaned) return undefined;
  try {
    const url = new URL(cleaned);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : undefined;
  } catch {
    return undefined;
  }
}

export function toPublicUserProfile(user: Record<string, unknown> | null | undefined): PublicUserProfile {
  if (!user) return {};
  const profile: PublicUserProfile = {};
  const name = cleanString(user.name);
  const email = cleanString(user.email);
  const picture = safeImageUrl(user.picture);
  if (name) profile.name = name;
  if (email) profile.email = email;
  if (picture) profile.picture = picture;
  return profile;
}

export function profileInitials(profile: PublicUserProfile): string {
  const source = profile.name || profile.email || "";
  return source.trim().charAt(0).toUpperCase();
}
