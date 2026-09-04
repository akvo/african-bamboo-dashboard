import { renderHook, act, waitFor } from "@testing-library/react";

jest.mock("../src/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn() },
}));

import { ExportProvider, useExport } from "@/hooks/useExport";
import api from "@/lib/api";

const wrapper = ({ children }) => (
  <ExportProvider>{children}</ExportProvider>
);

const renderExport = () => renderHook(() => useExport(), { wrapper });

const start = async (result) => {
  await act(async () => {
    result.current.startExport({ formId: "formX", format: "xlsx" });
  });
};

const POLL_INTERVAL_MS = 2000;

/**
 * Run N poll cycles.
 *
 * Each poll awaits a promise before scheduling the next timer, so a
 * single advanceTimersByTime cannot chain them — the interval has to
 * be advanced once per cycle, with microtasks flushed in between.
 */
const tick = async (cycles) => {
  for (let i = 0; i < cycles; i += 1) {
    await act(async () => {
      jest.advanceTimersByTime(POLL_INTERVAL_MS);
    });
  }
};

describe("useExport", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    api.post.mockResolvedValue({ data: { id: 7 } });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("gives up and reports an error when the job never finishes", async () => {
    // The TC02 regression: a worker that is not consuming leaves the
    // job at "pending" forever. The hook used to poll indefinitely,
    // so the Export button stayed disabled with no error at all.
    api.get.mockResolvedValue({ data: { status: "pending" } });
    const { result } = renderExport();
    await start(result);

    await tick(400);

    await waitFor(() => {
      expect(result.current.isExporting).toBe(false);
    });
    expect(result.current.toast.type).toBe("error");
    expect(result.current.toast.message).toMatch(/timed out/i);
  });

  it("surfaces the backend failure reason", async () => {
    api.get.mockResolvedValue({
      data: { status: "failed", result: "GEOS geometry invalid" },
    });
    const { result } = renderExport();
    await start(result);

    await tick(2);

    await waitFor(() => {
      expect(result.current.isExporting).toBe(false);
    });
    expect(result.current.toast.message).toContain("GEOS geometry invalid");
  });

  it("falls back to a generic message when there is no reason", async () => {
    api.get.mockResolvedValue({ data: { status: "failed" } });
    const { result } = renderExport();
    await start(result);

    await tick(2);

    await waitFor(() => {
      expect(result.current.toast.message).toMatch(/Export failed\./);
    });
  });

  it("shows a slow notice but keeps polling", async () => {
    api.get.mockResolvedValue({ data: { status: "pending" } });
    const { result } = renderExport();
    await start(result);

    await tick(25);

    expect(result.current.isExporting).toBe(true);
    expect(result.current.toast.message).toMatch(/Still preparing/i);
  });

  it("keeps polling through transient network errors", async () => {
    api.get
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValue({ data: { status: "pending" } });
    const { result } = renderExport();
    await start(result);

    await tick(3);

    expect(result.current.isExporting).toBe(true);
  });

  it("fails after repeated consecutive errors", async () => {
    api.get.mockRejectedValue(new Error("network"));
    const { result } = renderExport();
    await start(result);

    await tick(5);

    await waitFor(() => {
      expect(result.current.isExporting).toBe(false);
    });
    expect(result.current.toast.type).toBe("error");
  });
});
