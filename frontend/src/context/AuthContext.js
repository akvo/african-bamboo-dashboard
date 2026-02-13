"use client";

import { createContext, useContext, useEffect, useRef } from "react";
import { setApiToken } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ user, token, children }) {
  const prevToken = useRef(null);

  // Set token synchronously during render so it's available
  // before any child useEffect (e.g. useForms) fires API calls
  if (prevToken.current !== token) {
    setApiToken(token);
    prevToken.current = token;
  }

  useEffect(() => {
    return () => setApiToken(null);
  }, []);

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
