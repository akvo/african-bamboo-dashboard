"use client";

import { useCallback } from "react";
import { ExportProvider, useExport } from "@/hooks/useExport";
import ToastNotification from "@/components/map/toast-notification";

function ExportToast() {
  const { toast, dismissToast } = useExport();

  const handleDismiss = useCallback(() => {
    dismissToast();
  }, [dismissToast]);

  return (
    <ToastNotification
      message={toast.message}
      type={toast.type}
      onDismiss={handleDismiss}
    />
  );
}

export function ExportProviderWithToast({ children }) {
  return (
    <ExportProvider>
      {children}
      <ExportToast />
    </ExportProvider>
  );
}
