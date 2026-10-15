import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import { A2FSection, nextFilters } from "@/components/a2f/a2f-section";

const group = (n, value) => ({ n, value });

const DATA = {
  data_as_of: "2026-09-30",
  youth_max_age: 29,
  filter_options: {
    regions: ["Oromia", "Sidama"],
    woredas: { Oromia: ["Bore"], Sidama: ["Hula"] },
    cooperatives: [{ value: "CO001", label: "Hula Coop" }],
    genders: ["F", "M"],
    target_groups: ["SHF", "YW"],
    loan_types: ["Group loan"],
  },
  reach: {
    members: 36,
    borrowers: 29,
    borrowing_rate: 0.806,
    women_share: 0.241,
    youth_share: 0.448,
    coops: 6,
    coops_with_active_loans: 5,
    coops_share: 0.833,
  },
  volume: {
    loans: 34,
    disbursed: 995500,
    outstanding: 492475,
    average_loan: 29279.4,
    median_loan: 23250,
    hectares: 13.85,
    value_per_ha: 71877.3,
    outstanding_share: 0.495,
  },
  loan_terms: {
    average_interest_rate: 0.12994,
    collateral: [{ type: "Equipment", loans: 8, amount: 171500 }],
  },
  portfolio_quality: {
    par30: 0.143,
    written_off: 56420,
    written_off_share: 0.0567,
    credit_score: 688.6,
    credit_score_borrowers: 24,
  },
  linked: {
    borrowing_with_title: group(15, 0.867),
    borrowing_without_title: group(21, 0.762),
    par30_trained: group(21, 0.107),
    par30_untrained: group(4, null),
    income_change_borrowers: group(29, 3144.8),
    income_change_non_borrowers: group(7, 3428.6),
    jobs_created: 28,
    jobs_per_million: 28.13,
  },
};

describe("A2FSection", () => {
  it("renders the data date and headline numbers", () => {
    render(<A2FSection data={DATA} filters={{}} onFiltersChange={() => {}} />);
    expect(screen.getByText("Data as of 30 Sep 2026")).toBeInTheDocument();
    expect(screen.getByText("ETB 995,500")).toBeInTheDocument();
    expect(screen.getByText("Of 36 enrolled members")).toBeInTheDocument();
    expect(screen.getByText("12.99%")).toBeInTheDocument();
    expect(screen.getByText("689")).toBeInTheDocument();
    expect(screen.getByText("28.1")).toBeInTheDocument();
  });

  it("marks small comparison groups as not shown", () => {
    render(<A2FSection data={DATA} filters={{}} onFiltersChange={() => {}} />);
    expect(screen.getByText("Not shown (n < 5)")).toBeInTheDocument();
  });
});

describe("A2FSection stale figures", () => {
  it("says the figures failed to load for the chosen filters", () => {
    render(
      <A2FSection
        data={DATA}
        filters={{ region: "Sidama" }}
        onFiltersChange={() => {}}
        error
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Could not load figures for these filters",
    );
  });
});

describe("nextFilters", () => {
  it("clears woreda when region changes", () => {
    expect(
      nextFilters({ region: "Sidama", woreda: "Hula" }, "region", "Oromia"),
    ).toEqual({ region: "Oromia", woreda: "" });
  });

  it("maps the All option to blank", () => {
    expect(nextFilters({ gender: "F" }, "gender", "all")).toEqual({
      gender: "",
    });
  });
});
