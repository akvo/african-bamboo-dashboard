"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";

export function useFilterOptions({ formId, region } = {}) {
  const [options, setOptions] = useState({
    regions: [],
    sub_regions: [],
    dynamic_filters: [],
  });
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!formId) {
      setOptions({
        regions: [],
        sub_regions: [],
        dynamic_filters: [],
      });
      return;
    }
    setIsLoading(true);
    const params = { form_id: formId };
    if (region) params.region = region;
    api
      .get("/v1/odk/plots/filter_options/", { params })
      .then((res) => setOptions(res.data))
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, [formId, region]);

  return { ...options, isLoading };
}
