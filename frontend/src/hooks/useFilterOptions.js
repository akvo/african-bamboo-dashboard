"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";

export function useFilterOptions({ formId, region, allEligible = false } = {}) {
  const [options, setOptions] = useState({
    regions: [],
    sub_regions: [],
    dynamic_filters: [],
    available_filters: [],
  });
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!formId) {
      setOptions({
        regions: [],
        sub_regions: [],
        dynamic_filters: [],
        available_filters: [],
      });
      return;
    }
    setIsLoading(true);
    const params = { form_id: formId };
    if (region) params.region = region;
    if (allEligible) params.all_eligible = "true";
    api
      .get("/v1/odk/plots/filter_options/", { params })
      .then((res) =>
        setOptions({
          regions: res.data.regions || [],
          sub_regions: res.data.sub_regions || [],
          dynamic_filters: res.data.dynamic_filters || [],
          available_filters: res.data.available_filters || [],
        }),
      )
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, [formId, region, allEligible]);

  return { ...options, isLoading };
}
