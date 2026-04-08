"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import api from "@/lib/api";

export function useStats({
  formId,
  region,
  subRegion,
  startDate,
  endDate,
  dynamicFilters,
} = {}) {
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const dynamicKey = useMemo(
    () => JSON.stringify(dynamicFilters || {}),
    [dynamicFilters],
  );

  const fetchStats = useCallback(async () => {
    if (!formId) {
      setStats(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const params = { form_id: formId };
      if (region) {
        params.region = region;
      }
      if (subRegion) {
        params.sub_region = subRegion;
      }
      if (startDate) {
        params.start_date = startDate;
      }
      if (endDate) {
        params.end_date = endDate;
      }
      const parsed = JSON.parse(dynamicKey);
      for (const [key, val] of Object.entries(parsed)) {
        if (val) {
          params[`filter__${key}`] = val;
        }
      }
      const res = await api.get("/v1/odk/plots/stats/", { params });
      setStats(res.data);
    } catch {
      setStats(null);
    } finally {
      setIsLoading(false);
    }
  }, [formId, region, subRegion, startDate, endDate, dynamicKey]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return { stats, isLoading, refetch: fetchStats };
}
