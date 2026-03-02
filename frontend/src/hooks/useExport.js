"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import api from "@/lib/api";

const POLL_INTERVAL_MS = 2000;

const ExportContext = createContext(null);

export function ExportProvider({ children }) {
  const [isExporting, setIsExporting] = useState(false);
  const [toast, setToast] = useState({ message: "", type: "success" });
  const intervalRef = useRef(null);

  const clearPolling = useCallback(() => {
    if (intervalRef.current) {
      clearTimeout(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      clearPolling();
    };
  }, [clearPolling]);

  const dismissToast = useCallback(() => {
    setToast({ message: "", type: "success" });
  }, []);

  const triggerDownload = useCallback(async (jobId) => {
    const res = await api.get(`/v1/jobs/${jobId}/download/`, {
      responseType: "blob",
    });

    const contentDisposition = res.headers["content-disposition"] || "";
    const filenameMatch = contentDisposition.match(/filename="?([^";\n]+)"?/);
    const filename = filenameMatch ? filenameMatch[1] : `export-${jobId}`;

    const url = URL.createObjectURL(res.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, []);

  const pollJob = useCallback(
    (jobId) => {
      clearPolling();

      const poll = async () => {
        try {
          const res = await api.get(`/v1/jobs/${jobId}/`);
          const { status } = res.data;

          if (status === "done") {
            intervalRef.current = null;
            await triggerDownload(jobId);
            setIsExporting(false);
            setToast({
              message: "Export downloaded successfully.",
              type: "success",
            });
          } else if (status === "failed") {
            intervalRef.current = null;
            setIsExporting(false);
            setToast({
              message: "Export failed. Please try again.",
              type: "error",
            });
          } else {
            intervalRef.current = setTimeout(poll, POLL_INTERVAL_MS);
          }
        } catch (err) {
          intervalRef.current = null;
          setIsExporting(false);
          setToast({
            message:
              err.response?.data?.message ||
              "An error occurred while checking export status.",
            type: "error",
          });
        }
      };

      intervalRef.current = setTimeout(poll, POLL_INTERVAL_MS);
    },
    [clearPolling, triggerDownload],
  );

  const startExport = useCallback(
    async ({ formId, status, search, format = "shp" }) => {
      if (isExporting) return;

      setIsExporting(true);
      setToast({
        message: "Preparing export...",
        type: "success",
      });

      try {
        const res = await api.post("/v1/odk/plots/export/", {
          form_id: formId,
          status,
          search,
          format,
        });

        const job = res.data;
        pollJob(job.id);
      } catch (err) {
        setIsExporting(false);
        setToast({
          message:
            err.response?.data?.message ||
            "Failed to start export. Please try again.",
          type: "error",
        });
      }
    },
    [isExporting, pollJob],
  );

  return (
    <ExportContext.Provider
      value={{
        startExport,
        isExporting,
        toast,
        dismissToast,
      }}
    >
      {children}
    </ExportContext.Provider>
  );
}

export function useExport() {
  const context = useContext(ExportContext);
  if (!context) {
    throw new Error("useExport must be used within an ExportProvider");
  }
  return context;
}
