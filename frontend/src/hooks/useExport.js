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
// Sits just above the server-side stale-job reaper (10 min) so the
// user normally gets the specific server reason rather than this
// generic client timeout.
const MAX_POLL_MS = 11 * 60 * 1000;
const SLOW_NOTICE_MS = 30 * 1000;
const MAX_CONSECUTIVE_ERRORS = 3;

const ExportContext = createContext(null);

export function ExportProvider({ children }) {
  const [isExporting, setIsExporting] = useState(false);
  const [toast, setToast] = useState({ message: "", type: "success" });
  const intervalRef = useRef(null);
  const deadlineRef = useRef(0);
  const startedAtRef = useRef(0);
  const errorCountRef = useRef(0);
  const slowNoticeShownRef = useRef(false);

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

      const fail = (message) => {
        clearPolling();
        setIsExporting(false);
        setToast({ message, type: "error" });
      };

      const poll = async () => {
        // Without this the hook polls forever when the worker is
        // down, leaving the Export button disabled indefinitely.
        if (Date.now() > deadlineRef.current) {
          fail(
            "Export timed out. The export service may be unavailable — " +
              "please try again or contact support.",
          );
          return;
        }

        try {
          const res = await api.get(`/v1/jobs/${jobId}/`);
          const { status, result } = res.data;
          errorCountRef.current = 0;

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
              message: result
                ? `Export failed: ${String(result).slice(0, 200)}`
                : "Export failed. Please try again.",
              type: "error",
            });
          } else {
            if (
              !slowNoticeShownRef.current &&
              Date.now() - startedAtRef.current > SLOW_NOTICE_MS
            ) {
              slowNoticeShownRef.current = true;
              setToast({
                message: "Still preparing your export…",
                type: "success",
              });
            }
            intervalRef.current = setTimeout(poll, POLL_INTERVAL_MS);
          }
        } catch (err) {
          // A single network blip should not kill an export that
          // is otherwise progressing.
          errorCountRef.current += 1;
          if (errorCountRef.current < MAX_CONSECUTIVE_ERRORS) {
            intervalRef.current = setTimeout(poll, POLL_INTERVAL_MS);
            return;
          }
          fail(
            err.response?.data?.message ||
              "An error occurred while checking export status.",
          );
        }
      };

      intervalRef.current = setTimeout(poll, POLL_INTERVAL_MS);
    },
    [clearPolling, triggerDownload],
  );

  const startExport = useCallback(
    async ({
      formId,
      status,
      search,
      format,
      region,
      subRegion,
      start_date,
      end_date,
      dynamic_filters,
    }) => {
      if (isExporting) {
        return;
      }

      setIsExporting(true);
      startedAtRef.current = Date.now();
      deadlineRef.current = Date.now() + MAX_POLL_MS;
      errorCountRef.current = 0;
      slowNoticeShownRef.current = false;
      setToast({
        message: "Preparing export...",
        type: "success",
      });

      try {
        const body = { form_id: formId, status, search, format };
        if (region) {
          body.region = region;
        }
        if (subRegion) {
          body.sub_region = subRegion;
        }
        if (start_date) {
          body.start_date = start_date;
        }
        if (end_date) {
          body.end_date = end_date;
        }
        if (dynamic_filters && Object.keys(dynamic_filters).length > 0) {
          body.dynamic_filters = dynamic_filters;
        }
        const res = await api.post("/v1/odk/plots/export/", body);

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
