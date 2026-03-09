import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import { FilterBar, getDateRange } from "@/components/filter-bar";

const mockRegions = [
  { value: "ET04", label: "Amhara" },
  { value: "ET07", label: "Oromia" },
];

const mockSubRegions = [
  { value: "ET0408", label: "Bahir Dar" },
  { value: "ET0412", label: "Gondar" },
];

describe("FilterBar", () => {
  it("renders region dropdown when regions are provided", () => {
    render(<FilterBar regions={mockRegions} />);
    expect(screen.getByText("Region")).toBeInTheDocument();
  });

  it("does not render region dropdown when regions are empty", () => {
    render(<FilterBar regions={[]} />);
    expect(screen.queryByText("Region")).not.toBeInTheDocument();
  });

  it("renders sub-region dropdown when sub_regions are provided", () => {
    render(<FilterBar sub_regions={mockSubRegions} />);
    expect(screen.getByText("Sub-region")).toBeInTheDocument();
  });

  it("does not render sub-region dropdown when sub_regions are empty", () => {
    render(<FilterBar sub_regions={[]} />);
    expect(screen.queryByText("Sub-region")).not.toBeInTheDocument();
  });

  it("renders date range selector", () => {
    render(<FilterBar />);
    expect(screen.getByText("Date range")).toBeInTheDocument();
  });

  it("renders reset button when filters are active", () => {
    render(<FilterBar region="ET04" />);
    expect(
      screen.getByRole("button", { name: /reset/i }),
    ).toBeInTheDocument();
  });

  it("does not render reset button when no filters are active", () => {
    render(<FilterBar />);
    expect(
      screen.queryByRole("button", { name: /reset/i }),
    ).not.toBeInTheDocument();
  });

  it("renders reset button when datePreset is active", () => {
    render(<FilterBar datePreset="7days" />);
    expect(
      screen.getByRole("button", { name: /reset/i }),
    ).toBeInTheDocument();
  });

  it("renders dynamic filter dropdowns", () => {
    const dynamicFilters = [
      {
        name: "species",
        label: "Species",
        options: [
          { name: "bamboo", label: "Bamboo" },
          { name: "eucalyptus", label: "Eucalyptus" },
        ],
      },
    ];
    render(<FilterBar dynamicFilters={dynamicFilters} />);
    expect(screen.getByText("Species")).toBeInTheDocument();
  });
});

describe("getDateRange", () => {
  it("returns null dates for no preset", () => {
    const { start, end } = getDateRange(null);
    expect(start).toBeNull();
    expect(end).toBeNull();
  });

  it("returns a 7-day range", () => {
    const { start, end } = getDateRange("7days");
    expect(end - start).toBe(7 * 86400000);
  });

  it("returns a 30-day range", () => {
    const { start, end } = getDateRange("30days");
    expect(end - start).toBe(30 * 86400000);
  });

  it("returns a 90-day range", () => {
    const { start, end } = getDateRange("90days");
    expect(end - start).toBe(90 * 86400000);
  });

  it("returns null dates for unknown preset", () => {
    const { start, end } = getDateRange("unknown");
    expect(start).toBeNull();
    expect(end).toBeNull();
  });
});
