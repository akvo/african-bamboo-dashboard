import { cn } from "@/lib/utils";

const statusConfig = {
  approved: {
    label: "Approved",
    className:
      "bg-status-approved/15 text-status-approved border-status-approved/30",
  },
  pending: {
    label: "Pending",
    className:
      "bg-status-pending/15 text-status-pending border-status-pending/30",
  },
  rejected: {
    label: "Rejected",
    className:
      "bg-status-rejected/15 text-status-rejected border-status-rejected/30",
  },
  flagged: {
    label: "Flagged",
    className:
      "bg-status-flagged/15 text-status-flagged border-status-flagged/30",
  },
};

export function StatusBadge({ status }) {
  const config = statusConfig[status] || statusConfig.pending;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        config.className,
      )}
    >
      {config.label}
    </span>
  );
}
