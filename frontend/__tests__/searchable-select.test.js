import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";

// cmdk uses ResizeObserver internally
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// jsdom doesn't implement scrollIntoView
Element.prototype.scrollIntoView = jest.fn();

import { SearchableSelect } from "@/components/searchable-select";

const fewOptions = [
  { value: "b", label: "Banana" },
  { value: "a", label: "Apple" },
  { value: "c", label: "Cherry" },
];

const manyOptions = Array.from({ length: 20 }, (_, i) => ({
  value: `opt-${String(i).padStart(2, "0")}`,
  label: `Option ${String(i).padStart(2, "0")}`,
}));

describe("SearchableSelect", () => {
  it("renders as plain select when fewer than 15 options", () => {
    render(
      <SearchableSelect
        options={fewOptions}
        placeholder="Pick fruit"
      />,
    );
    expect(screen.getByText("Pick fruit")).toBeInTheDocument();
    // Should NOT have a search input
    expect(screen.queryByPlaceholderText("Search...")).not.toBeInTheDocument();
  });

  it("renders with search input when 15+ options", () => {
    render(
      <SearchableSelect
        options={manyOptions}
        value=""
        placeholder="Pick option"
      />,
    );
    // Click trigger to open popover
    fireEvent.click(screen.getByRole("combobox"));
    expect(screen.getByPlaceholderText("Search...")).toBeInTheDocument();
  });

  it("sorts options alphabetically by label", () => {
    render(
      <SearchableSelect
        options={fewOptions}
        placeholder="Pick fruit"
      />,
    );
    // Open select trigger
    fireEvent.click(screen.getByText("Pick fruit"));
    // Radix Select renders items as role="option"
    const items = screen.getAllByRole("option");
    const labels = items.map((el) => el.textContent);
    expect(labels).toEqual(["Apple", "Banana", "Cherry"]);
  });
});
