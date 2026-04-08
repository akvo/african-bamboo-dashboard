"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import api from "@/lib/api";

export function useSubmissions({
  assetUid,
  status,
  search,
  region,
  subRegion,
  startDate,
  endDate,
  dynamicFilters,
  ordering,
  limit = 10,
} = {}) {
  const [data, setData] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [sortableFields, setSortableFields] = useState([]);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Serialize dynamicFilters for stable dependency
  const dynamicKey = useMemo(
    () => JSON.stringify(dynamicFilters || {}),
    [dynamicFilters],
  );

  // Reset offset when any filter changes
  const filterKey = `${assetUid}-${status}-${search}-${region}-${subRegion}-${startDate}-${endDate}-${dynamicKey}-${ordering}`;
  const prevFilterKey = useRef(filterKey);
  useEffect(() => {
    if (prevFilterKey.current !== filterKey) {
      prevFilterKey.current = filterKey;
      setOffset(0);
    }
  }, [filterKey]);

  const totalPages = Math.ceil(count / limit);
  const page = Math.floor(offset / limit) + 1;

  const fetchSubmissions = useCallback(async () => {
    if (!assetUid) {return;}
    setIsLoading(true);
    setError(null);
    try {
      const params = { asset_uid: assetUid, limit, offset };
      if (ordering) {params.ordering = ordering;}
      if (status && status !== "all") {params.status = status;}
      if (search) {params.search = search;}
      if (region) {params.region = region;}
      if (subRegion) {params.sub_region = subRegion;}
      if (startDate) {params.start_date = startDate;}
      if (endDate) {params.end_date = endDate;}
      // Dynamic filters: filter__<name>=<value>
      const parsed = JSON.parse(dynamicKey);
      for (const [key, val] of Object.entries(parsed)) {
        if (val) {params[`filter__${key}`] = val;}
      }
      const res = await api.get("/v1/odk/submissions/", { params });
      setData(res.data.results);
      setQuestions(res.data.questions || []);
      setSortableFields(res.data.sortable_fields || []);
      setCount(res.data.count);
    } catch (err) {
      setError(err.response?.data?.message || "Failed to fetch submissions");
    } finally {
      setIsLoading(false);
    }
  }, [
    assetUid,
    status,
    search,
    region,
    subRegion,
    startDate,
    endDate,
    dynamicKey,
    ordering,
    limit,
    offset,
  ]);

  useEffect(() => {
    fetchSubmissions();
  }, [fetchSubmissions]);

  const setPage = useCallback(
    (newPage) => {
      setOffset((newPage - 1) * limit);
    },
    [limit],
  );

  return {
    data,
    questions,
    sortableFields,
    count,
    isLoading,
    error,
    page,
    totalPages,
    setPage,
    refetch: fetchSubmissions,
  };
}
