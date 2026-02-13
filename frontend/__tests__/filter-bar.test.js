import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

const mockForms = [
  { asset_uid: "form1", name: "Form One" },
  { asset_uid: "form2", name: "Form Two" },
];

jest.mock("../src/hooks/useForms", () => ({
  useForms: () => ({
    forms: mockForms,
    activeForm: mockForms[0],
    setActiveForm: jest.fn(),
  }),
}));

import { FilterBar } from "@/components/filter-bar";

describe("FilterBar", () => {
  it("renders the form selector", () => {
    render(<FilterBar />);
    expect(screen.getByText("Form One")).toBeInTheDocument();
  });

  it("renders the date range selector", () => {
    render(<FilterBar />);
    expect(screen.getByText("Last 7 days")).toBeInTheDocument();
  });

  it("renders the reset button", () => {
    render(<FilterBar />);
    expect(
      screen.getByRole("button", { name: /reset/i })
    ).toBeInTheDocument();
  });
});
