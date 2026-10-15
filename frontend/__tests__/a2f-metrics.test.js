import "@testing-library/jest-dom";
import {
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";

jest.mock("../src/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn() },
}));

import api from "@/lib/api";
import { useA2FMetrics } from "@/hooks/useA2FMetrics";
import { A2FCard, Bar } from "@/components/a2f/a2f-card";

describe("useA2FMetrics", () => {
  beforeEach(() => jest.clearAllMocks());

  it("is enabled with data on 200 and omits blank filters", async () => {
    api.get.mockResolvedValue({ data: { data_as_of: "2026-09-30" } });
    const { result } = renderHook(() =>
      useA2FMetrics({ region: "Sidama", woreda: "" }),
    );
    await waitFor(() => expect(result.current.isEnabled).toBe(true));
    expect(result.current.data.data_as_of).toBe("2026-09-30");
    expect(api.get).toHaveBeenCalledWith("/v1/a2f/metrics/", {
      params: { region: "Sidama" },
    });
  });

  it("is disabled on 404", async () => {
    api.get.mockRejectedValue({ response: { status: 404 } });
    const { result } = renderHook(() => useA2FMetrics({}));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isEnabled).toBe(false);
    expect(result.current.data).toBeNull();
  });
});

describe("A2FCard", () => {
  it("toggles between chart and table", () => {
    render(
      <A2FCard
        title="Reach"
        chart={<Bar label="Borrowing" value="80.6%" share={0.806} />}
        rows={[["Borrowers", "29"]]}
      />,
    );
    expect(screen.getByText("Borrowing")).toBeInTheDocument();
    expect(screen.queryByText("Borrowers")).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Show Reach as table" }),
    );
    expect(screen.getByText("Borrowers")).toBeInTheDocument();
    expect(screen.queryByText("Borrowing")).not.toBeInTheDocument();
  });
});
