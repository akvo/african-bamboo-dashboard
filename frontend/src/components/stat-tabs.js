"use client";

export function StatTabs({
  value,
  onChange,
  options,
  ariaLabel = "Stats unit toggle",
}) {
  return (
    <div
      className="inline-flex rounded-md border border-border overflow-hidden"
      role="group"
      aria-label={ariaLabel}
    >
      {options.map((opt, idx) => {
        const isActive = value === opt.value;
        const Icon = opt.icon;
        return (
          <button
            key={opt.value}
            type="button"
            aria-label={opt.ariaLabel || opt.label}
            aria-pressed={isActive}
            onClick={() => onChange(opt.value)}
            className={`cursor-pointer flex items-center justify-center h-[34px] px-2.5 text-sm font-semibold transition-colors ${
              idx > 0 ? "border-l border-border" : ""
            } ${
              isActive
                ? "bg-white text-foreground"
                : "bg-muted text-muted-foreground"
            }`}
          >
            {Icon ? <Icon className="size-4" /> : opt.label}
          </button>
        );
      })}
    </div>
  );
}
