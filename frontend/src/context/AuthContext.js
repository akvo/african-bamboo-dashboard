"use client";

import { createContext, useContext, useEffect } from "react";
import { setApiToken } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ user, token, children }) {
  useEffect(() => {
    setApiToken(token);
    return () => setApiToken(null);
  }, [token]);

  return (
    <AuthContext.Provider value={{ user, token }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
