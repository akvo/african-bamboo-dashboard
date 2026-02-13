"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";

export function useForms() {
  const [forms, setForms] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchForms() {
      setIsLoading(true);
      setError(null);
      try {
        const res = await api.get("/v1/odk/forms/");
        if (!cancelled) {
          setForms(res.data.results);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.message || "Failed to fetch forms");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    fetchForms();
    return () => {
      cancelled = true;
    };
  }, []);

  return { forms, isLoading, error };
}
