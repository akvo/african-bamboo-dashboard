"use client";

import { useState } from "react";
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StatTabs } from "@/components/stat-tabs";

export function A2FCard({ title, chart, rows, className }) {
  const [view, setView] = useState("chart");
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-md font-medium text-foreground">
          {title}
        </CardTitle>
        <CardAction>
          <StatTabs
            value={view}
            onChange={setView}
            ariaLabel={`${title} view toggle`}
            options={[
              {
                value: "chart",
                label: "Chart",
                ariaLabel: `Show ${title} as chart`,
              },
              {
                value: "table",
                label: "Table",
                ariaLabel: `Show ${title} as table`,
              },
            ]}
          />
        </CardAction>
      </CardHeader>
      <CardContent>
        {view === "chart" ? (
          <div className="space-y-5">{chart}</div>
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {rows.map(([label, value]) => (
                <tr key={label} className="border-b last:border-0">
                  <td className="py-2 text-muted-foreground">{label}</td>
                  <td className="py-2 text-right">{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

export function Bar({ label, value, note, share = null, muted = false }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-sm">{label}</span>
        <span className="font-semibold">{value}</span>
      </div>
      <ShareBar share={share} muted={muted} />
      {note && <p className="mt-1 text-xs text-muted-foreground">{note}</p>}
    </div>
  );
}

export function ShareBar({ share, muted = false }) {
  if (share == null) {
    return null;
  }
  return (
    <div className="mt-2 h-1.5 rounded-full bg-muted">
      <div
        className={`h-full rounded-full ${
          muted ? "bg-amber-300" : "bg-amber-500"
        }`}
        style={{ width: `${Math.max(0, Math.min(share, 1)) * 100}%` }}
      />
    </div>
  );
}
