"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";

export function usePlots({ formId, limit = 200 } = {}) {
  const [plots, setPlots] = useState([]);
  const [count, setCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPlots = useCallback(async () => {
    if (!formId) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.get("/v1/odk/plots/", {
        params: { form_id: formId, limit },
      });
      setPlots(res.data.results || []);
      setCount(res.data.count || 0);
    } catch (err) {
      setError(err.response?.data?.message || "Failed to fetch plots");
    } finally {
      setIsLoading(false);
    }
  }, [formId, limit]);

  useEffect(() => {
    fetchPlots();
  }, [fetchPlots]);

  return { plots, setPlots, count, isLoading, error, refetch: fetchPlots };
}
