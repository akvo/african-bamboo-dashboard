"use server";

import { redirect } from "next/navigation";
import { createSession, deleteSession } from "@/lib/session";

export async function login(_prevState, formData) {
  const koboUrl = formData.get("kobo_url");
  const koboUsername = formData.get("kobo_username");
  const koboPassword = formData.get("kobo_password");

  const baseUrl = process.env.WEBDOMAIN;

  let res;
  try {
    res = await fetch(`${baseUrl}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kobo_url: koboUrl,
        kobo_username: koboUsername,
        kobo_password: koboPassword,
      }),
    });
  } catch {
    return { error: "Unable to connect to the server. Please try again." };
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return {
      error: data.message || "Invalid KoboToolbox credentials",
    };
  }

  const data = await res.json();

  await createSession({
    user: data.user,
    token: data.token,
    expirationTime: data.expiration_time,
  });

  redirect("/dashboard");
}

export async function logout() {
  await deleteSession();
  redirect("/login");
}
