"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";

export function useA2FMetrics(filters = {}) {
  const [data, setData] = useState(null);
  const [isEnabled, setIsEnabled] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(false);
  const key = JSON.stringify(filters);

  useEffect(() => {
    let cancelled = false;
    const params = Object.fromEntries(
      Object.entries(JSON.parse(key)).filter(([, v]) => v),
    );
    setIsLoading(true);
    api
      .get("/v1/a2f/metrics/", { params })
      .then((res) => {
        if (!cancelled) {
          setData(res.data);
          setIsEnabled(true);
          setError(false);
        }
      })
      .catch((err) => {
        // 404 = feature off or nothing imported: hide the tab.
        if (cancelled) {
          return;
        }
        if (err.response?.status === 404) {
          setData(null);
          setIsEnabled(false);
        } else {
          // Keep the last figures but flag them as not matching
          // the chosen filters.
          setError(true);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [key]);

  return { data, isEnabled, isLoading, error };
}
