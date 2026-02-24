"use client";

import { useEffect } from "react";
import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const TOAST_STYLES = {
  success: {
    icon: CheckCircle2,
    className: "bg-status-approved text-white",
  },
  warning: {
    icon: AlertTriangle,
    className: "bg-amber-500 text-white",
  },
  error: {
    icon: XCircle,
    className: "bg-status-rejected text-white",
  },
};

export default function ToastNotification({
  message,
  type = "success",
  onDismiss,
}) {
  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => {
      onDismiss();
    }, 3000);
    return () => clearTimeout(timer);
  }, [message, onDismiss]);

  if (!message) return null;

  const style = TOAST_STYLES[type] || TOAST_STYLES.success;
  const Icon = style.icon;

  return (
    <div
      className={cn(
        "fixed right-5 top-5 z-[99999] flex items-center rounded-lg py-3 px-5 shadow-lg",
        style.className,
      )}
      role="alert"
      aria-live="assertive"
    >
      <Icon className="mr-3 h-5 w-5" />
      <span className="font-medium">{message}</span>
    </div>
  );
}
