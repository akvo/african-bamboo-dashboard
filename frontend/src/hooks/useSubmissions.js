"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";

export function useSubmissions({ assetUid, limit = 10 } = {}) {
  const [data, setData] = useState([]);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentForm, setCurrentForm] = useState(assetUid);

  const totalPages = Math.ceil(count / limit);
  const page = Math.floor(offset / limit) + 1;

  const fetchSubmissions = useCallback(async () => {
    if (!isLoading && currentForm !== assetUid) {
      setCurrentForm(assetUid);
      setIsLoading(true);
      setOffset(0);
    }
    if (!assetUid || !isLoading) {
      setIsLoading(false);
      return;
    }
    setError(null);
    try {
      const params = { asset_uid: assetUid, limit, offset };
      const res = await api.get("/v1/odk/submissions/", { params });
      setData(res.data.results);
      setCount(res.data.count);
    } catch (err) {
      setError(err.response?.data?.message || "Failed to fetch submissions");
    } finally {
      setIsLoading(false);
    }
  }, [assetUid, limit, isLoading, offset, currentForm]);

  useEffect(() => {
    fetchSubmissions();
  }, [fetchSubmissions]);

  const setPage = useCallback(
    (newPage) => {
      setIsLoading(true);
      setOffset((newPage - 1) * limit);
    },
    [limit],
  );

  return {
    data,
    count,
    isLoading,
    error,
    page,
    totalPages,
    setPage,
    refetch: fetchSubmissions,
  };
}
