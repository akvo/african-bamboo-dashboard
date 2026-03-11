import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";

import { FilterBar, getDateRange } from "@/components/filter-bar";

const mockRegions = [
  { value: "ET04", label: "Amhara" },
  { value: "ET07", label: "Oromia" },
];

const mockSubRegions = [
  { value: "ET0408", label: "Bahir Dar" },
  { value: "ET0412", label: "Gondar" },
];

const mockDynamicFilters = [
  {
    name: "species",
    label: "Species",
    options: [
      { name: "bamboo", label: "Bamboo" },
      { name: "eucalyptus", label: "Eucalyptus" },
    ],
  },
];

describe("FilterBar", () => {
  it("renders region and sub-region dropdowns", () => {
    render(
      <FilterBar regions={mockRegions} sub_regions={mockSubRegions} />,
    );
    expect(screen.getByText("Region")).toBeInTheDocument();
    expect(screen.getByText("Sub-region")).toBeInTheDocument();
  });

  it("renders date range selector", () => {
    render(<FilterBar />);
    expect(screen.getByText("Date range")).toBeInTheDocument();
  });

  it("renders reset button when region filter is active", () => {
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

  it("does not render advanced filters button when no dynamic filters", () => {
    render(<FilterBar />);
    expect(
      screen.queryByRole("button", { name: /advanced filters/i }),
    ).not.toBeInTheDocument();
  });

  it("renders advanced filters button when dynamic filters are provided", () => {
    render(<FilterBar dynamicFilters={mockDynamicFilters} />);
    expect(
      screen.getByRole("button", { name: /advanced filters/i }),
    ).toBeInTheDocument();
  });

  it("shows dynamic filters and region/sub-region in dialog", () => {
    render(
      <FilterBar
        regions={mockRegions}
        sub_regions={mockSubRegions}
        dynamicFilters={mockDynamicFilters}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /advanced filters/i }),
    );
    expect(screen.getByText("Advanced Filters")).toBeInTheDocument();
    expect(screen.getByText("Species")).toBeInTheDocument();
    // Region and sub-region are also shown inside the dialog
    expect(screen.getByText("Select region")).toBeInTheDocument();
    expect(screen.getByText("Select sub-region")).toBeInTheDocument();
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
