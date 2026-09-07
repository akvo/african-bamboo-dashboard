"use client";

import { useState } from "react";
import { CheckCircle2, Loader2, AlertTriangle } from "lucide-react";
import api from "@/lib/api";

/**
 * Delivery state of the Telegram rejection notification.
 *
 * `telegram_status` is derived server-side so this component
 * never needs the bot config to decide what to render — the
 * only endpoint carrying that also returns the bot token.
 *
 * Renders nothing when the integration is disabled: never
 * imply a message that was never configured.
 */
export default function TelegramStatusBadge({ audit, onResent }) {
  const [resending, setResending] = useState(false);
  const status = audit?.telegram_status;

  if (!status || status === "disabled") {
    return null;
  }

  const handleResend = async () => {
    setResending(true);
    try {
      await api.post(
        `/v1/odk/rejection-audits/${audit.id}/resend_notification/`,
      );
      onResent?.({ message: "Notification re-queued" });
    } catch (err) {
      onResent?.({
        message:
          err?.response?.data?.detail || "Could not re-queue. Try again.",
        type: "error",
      });
    } finally {
      setResending(false);
    }
  };

  if (status === "sent") {
    const at = audit.telegram_sent_at
      ? new Date(audit.telegram_sent_at).toLocaleTimeString("en-GB", {
          hour: "2-digit",
          minute: "2-digit",
        })
      : null;
    return (
      <p className="flex items-center gap-1.5 text-xs text-status-approved">
        <CheckCircle2 className="size-3.5 shrink-0" />
        <span>Field team notified{at ? ` · ${at}` : ""}</span>
      </p>
    );
  }

  if (status === "pending") {
    return (
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Loader2 className="size-3.5 shrink-0 animate-spin" />
        <span>Notifying field team…</span>
      </p>
    );
  }

  // The Kobo sync failed, so nothing was ever sent. The cause
  // varies (expired credentials, a submission deleted in Kobo,
  // a renamed form), so name the consequence and point at the
  // log rather than guessing.
  if (status === "sync_failed") {
    return (
      <p className="flex items-start gap-1.5 text-xs text-amber-600">
        <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
        <span>
          This rejection did not reach KoboToolbox, so the field team was not
          notified. Ask an administrator to check the sync log for the reason.
        </span>
      </p>
    );
  }

  // failed — amber, not red. The rejection itself succeeded;
  // only the notification did not.
  return (
    <div className="flex flex-wrap items-center gap-2">
      <p className="flex items-center gap-1.5 text-xs text-amber-600">
        <AlertTriangle className="size-3.5 shrink-0" />
        <span>Telegram notification not delivered</span>
      </p>
      {audit.can_resend && (
        <button
          type="button"
          onClick={handleResend}
          disabled={resending}
          className="text-xs font-medium underline underline-offset-2 disabled:opacity-50"
        >
          {resending ? "Re-queuing…" : "Resend"}
        </button>
      )}
    </div>
  );
}
