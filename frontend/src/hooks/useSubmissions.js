"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import api from "@/lib/api";

export function useSubmissions({ assetUid, status, limit = 10 } = {}) {
  const [data, setData] = useState([]);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const prevAssetUid = useRef(assetUid);
  const prevStatus = useRef(status);

  const totalPages = Math.ceil(count / limit);
  const page = Math.floor(offset / limit) + 1;

  // Reset offset when the form or status changes
  useEffect(() => {
    if (prevAssetUid.current !== assetUid || prevStatus.current !== status) {
      prevAssetUid.current = assetUid;
      prevStatus.current = status;
      setOffset(0);
    }
  }, [assetUid, status]);

  const fetchSubmissions = useCallback(async () => {
    if (!assetUid) return;
    setIsLoading(true);
    setError(null);
    try {
      const params = { asset_uid: assetUid, limit, offset };
      if (status && status !== "all") {
        params.status = status;
      }
      const res = await api.get("/v1/odk/submissions/", { params });
      setData(res.data.results);
      setCount(res.data.count);
    } catch (err) {
      setError(err.response?.data?.message || "Failed to fetch submissions");
    } finally {
      setIsLoading(false);
    }
  }, [assetUid, status, limit, offset]);

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
    count,
    isLoading,
    error,
    page,
    totalPages,
    setPage,
    refetch: fetchSubmissions,
  };
}
