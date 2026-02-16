"use client";

import { useEffect } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

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

  const Icon = type === "success" ? CheckCircle2 : XCircle;

  return (
    <div
      className={cn(
        "fixed right-5 top-5 z-[99999] flex items-center rounded-lg py-3 px-5 shadow-lg",
        type === "success"
          ? "bg-status-approved text-white"
          : "bg-status-rejected text-white",
      )}
      role="alert"
      aria-live="assertive"
    >
      <Icon className="mr-3 h-5 w-5" />
      <span className="font-medium">{message}</span>
    </div>
  );
}
