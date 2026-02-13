import { cn } from "@/lib/utils";

const statusConfig = {
  approved: {
    label: "Approved",
    className:
      "bg-status-approved/15 text-status-approved border-status-approved/30",
  },
  on_hold: {
    label: "On hold",
    className:
      "bg-status-on-hold/15 text-status-on-hold border-status-on-hold/30",
  },
  rejected: {
    label: "Rejected",
    className:
      "bg-status-rejected/15 text-status-rejected border-status-rejected/30",
  },
};

export function StatusBadge({ status }) {
  const config = statusConfig[status] || statusConfig.on_hold;
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
