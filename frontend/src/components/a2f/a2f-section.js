"use client";

import { format, parseISO } from "date-fns";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { A2FCard, Bar, ShareBar } from "@/components/a2f/a2f-card";

const ALL = "all";
const HIDDEN = "Not shown (n < 5)";
const GENDERS = { F: "Female", M: "Male" };

const etb = (v) =>
  v == null ? "—" : `ETB ${Math.round(v).toLocaleString("en-US")}`;
const pct = (v, digits = 1) =>
  v == null ? "—" : `${(v * 100).toFixed(digits)}%`;
const num = (v, digits = 0) =>
  v == null
    ? "—"
    : v.toLocaleString("en-US", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });

export function nextFilters(filters, name, value) {
  const next = { ...filters, [name]: value === ALL ? "" : value };
  if (name === "region") {
    next.woreda = "";
  }
  return next;
}

function FilterSelect({ label, value, options, onChange }) {
  return (
    <Select value={value || ""} onValueChange={onChange}>
      <SelectTrigger className="w-[150px]" aria-label={label}>
        <SelectValue placeholder={label} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>All</SelectItem>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function Kpi({ title, value, note, share }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-md font-medium text-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold">{value}</div>
        <p className="mt-1 text-sm text-muted-foreground">{note}</p>
        <ShareBar share={share} />
      </CardContent>
    </Card>
  );
}

const shown = (g, fmt) => (g.value == null ? HIDDEN : fmt(g.value));

export function A2FSection({
  data,
  filters,
  onFiltersChange,
  isLoading = false,
  error = false,
}) {
  if (!data) {
    return null;
  }
  const {
    filter_options: o,
    reach: r,
    volume: v,
    loan_terms: t,
    portfolio_quality: q,
    linked: k,
  } = data;
  const plain = (values) => values.map((x) => ({ value: x, label: x }));
  const woredas = filters.region
    ? o.woredas[filters.region] || []
    : Object.values(o.woredas).flat().sort();
  const selects = [
    ["region", "Region", plain(o.regions)],
    ["woreda", "Woreda", plain(woredas)],
    ["coop", "Cooperative", o.cooperatives],
    [
      "gender",
      "Gender",
      o.genders.map((g) => ({ value: g, label: GENDERS[g] || g })),
    ],
    ["target_group", "Target group", plain(o.target_groups)],
    [
      "youth",
      "Youth",
      [
        { value: "yes", label: `${data.youth_max_age} or under` },
        { value: "no", label: `Over ${data.youth_max_age}` },
      ],
    ],
    ["loan_type", "Loan type", plain(o.loan_types)],
  ];
  const incomeMax = Math.max(
    k.income_change_borrowers.value || 0,
    k.income_change_non_borrowers.value || 0,
  );
  const incomeShare = (g) =>
    g.value == null || !incomeMax ? null : g.value / incomeMax;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Data as of {format(parseISO(data.data_as_of), "d MMM yyyy")}
      </p>
      <div className="flex flex-wrap gap-2">
        {selects.map(([name, label, options]) => (
          <FilterSelect
            key={name}
            label={label}
            value={filters[name]}
            options={options}
            onChange={(val) => onFiltersChange(nextFilters(filters, name, val))}
          />
        ))}
      </div>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          Could not load figures for these filters. Showing the last figures
          loaded.
        </p>
      )}
      <div
        aria-busy={isLoading}
        className={`space-y-4 ${isLoading || error ? "opacity-50" : ""}`}
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi
            title="Borrowers"
            value={num(r.borrowers)}
            note={`Of ${num(r.members)} enrolled members`}
          />
          <Kpi
            title="Total disbursed"
            value={etb(v.disbursed)}
            note={`${num(v.loans)} loans`}
          />
          <Kpi
            title="Outstanding portfolio"
            value={etb(v.outstanding)}
            note="On active loans"
          />
          <Kpi
            title="Portfolio at risk (PAR30)"
            value={pct(q.par30)}
            note="Of outstanding balance over 30 days overdue"
            share={q.par30}
          />
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <A2FCard
            title="Reach"
            chart={
              <>
                <Bar
                  label="Enrolled members borrowing"
                  value={pct(r.borrowing_rate)}
                  share={r.borrowing_rate}
                  note={`${num(r.borrowers)} of ${num(r.members)} members`}
                />
                <Bar
                  label="Borrowers who are women"
                  value={pct(r.women_share)}
                  share={r.women_share}
                  note={`Of ${num(r.borrowers)} borrowers`}
                />
                <Bar
                  label={`Borrowers who are youth (${data.youth_max_age} or under)`}
                  value={pct(r.youth_share)}
                  share={r.youth_share}
                  note={`Of ${num(r.borrowers)} borrowers`}
                />
                <Bar
                  label="Cooperatives whose members hold active loans"
                  value={pct(r.coops_share)}
                  share={r.coops_share}
                  note={`${num(r.coops_with_active_loans)} of ${num(
                    r.coops,
                  )} cooperatives`}
                />
              </>
            }
            rows={[
              ["Borrowers", num(r.borrowers)],
              ["Enrolled members borrowing", pct(r.borrowing_rate)],
              ["Borrowers who are women", pct(r.women_share)],
              [
                `Borrowers who are youth (${data.youth_max_age} or under)`,
                pct(r.youth_share),
              ],
              [
                "Cooperatives whose members hold active loans",
                pct(r.coops_share),
              ],
            ]}
          />
          <A2FCard
            title="Volume"
            chart={
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm">Average loan</p>
                    <p className="font-semibold">{etb(v.average_loan)}</p>
                  </div>
                  <div>
                    <p className="text-sm">Median loan</p>
                    <p className="font-semibold">{etb(v.median_loan)}</p>
                  </div>
                </div>
                <Bar
                  label="Loan value per hectare of bamboo"
                  value={etb(v.value_per_ha)}
                  note={`${num(v.hectares, 2)} ha managed by borrowers`}
                />
                <Bar
                  label="Disbursed value still outstanding"
                  value={pct(v.outstanding_share)}
                  share={v.outstanding_share}
                  note={`${etb(v.outstanding)} of ${etb(v.disbursed)}`}
                />
              </>
            }
            rows={[
              ["Total disbursed", etb(v.disbursed)],
              ["Outstanding portfolio", etb(v.outstanding)],
              ["Average loan size", etb(v.average_loan)],
              ["Median loan size", etb(v.median_loan)],
              ["Loan value per hectare of bamboo", etb(v.value_per_ha)],
            ]}
          />
          <A2FCard
            title="Loan terms"
            chart={
              <>
                <Bar
                  label="Average interest rate"
                  value={pct(t.average_interest_rate, 2)}
                  note="Weighted by loan value"
                />
                <p className="text-sm">Loans by collateral type</p>
                {t.collateral.map((c) => (
                  <Bar
                    key={c.type}
                    label={c.type}
                    value={`${c.loans} loans · ${etb(c.amount)}`}
                    share={v.loans ? c.loans / v.loans : null}
                  />
                ))}
              </>
            }
            rows={[
              [
                "Average interest rate (weighted by loan value)",
                pct(t.average_interest_rate, 2),
              ],
              ...t.collateral.map((c) => [
                `Collateral: ${c.type}`,
                `${c.loans} loans · ${etb(c.amount)}`,
              ]),
            ]}
          />
          <A2FCard
            title="Portfolio quality"
            chart={
              <>
                <Bar
                  label="Portfolio at risk over 30 days (PAR30)"
                  value={pct(q.par30)}
                  share={q.par30}
                  note={`Of ${etb(v.outstanding)} outstanding`}
                />
                <Bar
                  label="Written off"
                  value={pct(q.written_off_share)}
                  share={q.written_off_share}
                  note={`${etb(q.written_off)} of ${etb(v.disbursed)} disbursed`}
                />
                <Bar
                  label="Average credit score of active borrowers"
                  value={num(q.credit_score)}
                  note={`${num(q.credit_score_borrowers)} active borrowers`}
                />
              </>
            }
            rows={[
              ["PAR30", pct(q.par30)],
              [
                "Written off, share of disbursed",
                `${pct(q.written_off_share)} (${etb(q.written_off)})`,
              ],
              ["Average credit score of active borrowers", num(q.credit_score)],
            ]}
          />
          <A2FCard
            title="Linked to other data"
            className="lg:col-span-2"
            chart={
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <div className="space-y-4">
                  <p className="text-sm">Borrowing rate by land title</p>
                  <Bar
                    label={`With title (members = ${k.borrowing_with_title.n})`}
                    value={shown(k.borrowing_with_title, pct)}
                    share={k.borrowing_with_title.value}
                  />
                  <Bar
                    label={`Without title (members = ${k.borrowing_without_title.n})`}
                    value={shown(k.borrowing_without_title, pct)}
                    share={k.borrowing_without_title.value}
                    muted
                  />
                  <p className="text-sm">Change in income since baseline</p>
                  <Bar
                    label={`Borrowers (members = ${k.income_change_borrowers.n})`}
                    value={shown(k.income_change_borrowers, etb)}
                    share={incomeShare(k.income_change_borrowers)}
                  />
                  <Bar
                    label={`Non-borrowers (members = ${k.income_change_non_borrowers.n})`}
                    value={shown(k.income_change_non_borrowers, etb)}
                    share={incomeShare(k.income_change_non_borrowers)}
                    muted
                  />
                </div>
                <div className="space-y-4">
                  <p className="text-sm">PAR30 by training</p>
                  <Bar
                    label={`Trained (active loans = ${k.par30_trained.n})`}
                    value={shown(k.par30_trained, pct)}
                    share={k.par30_trained.value}
                  />
                  <Bar
                    label={`Not trained (active loans = ${k.par30_untrained.n})`}
                    value={shown(k.par30_untrained, pct)}
                    share={k.par30_untrained.value}
                    muted
                  />
                  <Bar
                    label="Jobs created per ETB 1 million lent"
                    value={num(k.jobs_per_million, 1)}
                    note={`${num(k.jobs_created)} jobs created by borrowers`}
                  />
                </div>
                <p className="text-xs text-muted-foreground md:col-span-2">
                  Comparisons with fewer than 5 in a group are not shown.
                </p>
              </div>
            }
            rows={[
              [
                `Borrowing rate, with land title (n = ${k.borrowing_with_title.n})`,
                shown(k.borrowing_with_title, pct),
              ],
              [
                `Borrowing rate, without land title (n = ${k.borrowing_without_title.n})`,
                shown(k.borrowing_without_title, pct),
              ],
              [
                `PAR30, trained members (n = ${k.par30_trained.n})`,
                shown(k.par30_trained, pct),
              ],
              [
                `PAR30, untrained members (n = ${k.par30_untrained.n})`,
                shown(k.par30_untrained, pct),
              ],
              [
                `Income change, borrowers (n = ${k.income_change_borrowers.n})`,
                shown(k.income_change_borrowers, etb),
              ],
              [
                `Income change, non-borrowers (n = ${k.income_change_non_borrowers.n})`,
                shown(k.income_change_non_borrowers, etb),
              ],
              [
                "Jobs created per ETB 1 million lent",
                num(k.jobs_per_million, 1),
              ],
            ]}
          />
        </div>
      </div>
    </div>
  );
}
