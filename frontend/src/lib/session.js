import { EncryptJWT, jwtDecrypt } from "jose";
import { cookies } from "next/headers";

const secretKey = process.env.SESSION_SECRET;
const encodedKey = new TextEncoder().encode(secretKey);

let _derivedKey = null;
async function getDerivedKey() {
  if (!_derivedKey) {
    const hash = await crypto.subtle.digest("SHA-256", encodedKey);
    _derivedKey = new Uint8Array(hash);
  }
  return _derivedKey;
}

export async function encrypt(payload, expiresAt) {
  const key = await getDerivedKey();
  return new EncryptJWT(payload)
    .setProtectedHeader({ alg: "dir", enc: "A256GCM" })
    .setIssuedAt()
    .setExpirationTime(expiresAt)
    .encrypt(key);
}

export async function decrypt(session) {
  try {
    const key = await getDerivedKey();
    const { payload } = await jwtDecrypt(session, key, {
      contentEncryptionAlgorithms: ["A256GCM"],
    });
    return payload;
  } catch {
    return null;
  }
}

export async function createSession({ user, token, expirationTime }) {
  const expiresAt = new Date(expirationTime);
  const session = await encrypt(
    { user, token, expiresAt: expiresAt.toISOString() },
    expiresAt,
  );
  const cookieStore = await cookies();

  cookieStore.set("session", session, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    expires: expiresAt,
    sameSite: "lax",
    path: "/",
  });
}

export async function updateSession() {
  const cookieStore = await cookies();
  const currentSession = cookieStore.get("session")?.value;
  const payload = await decrypt(currentSession);
  if (!currentSession || !payload) return null;

  const expiresAt = new Date(Date.now() + 12 * 60 * 60 * 1000);
  const session = await encrypt(
    {
      user: payload.user,
      token: payload.token,
      expiresAt: expiresAt.toISOString(),
    },
    expiresAt,
  );

  cookieStore.set("session", session, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    expires: expiresAt,
    sameSite: "lax",
    path: "/",
  });
}

export async function deleteSession() {
  const cookieStore = await cookies();
  cookieStore.delete("session");
}
