import { renderHook, act, waitFor } from "@testing-library/react";

jest.mock("../src/lib/api", () => ({
  __esModule: true,
  default: { get: jest.fn() },
}));

import { useSubmissions } from "@/hooks/useSubmissions";
import api from "@/lib/api";

const MOCK_RESPONSE = {
  data: {
    results: [{ uuid: "sub-1" }],
    questions: [{ name: "q1", label: "Q1", type: "text" }],
    sortable_fields: ["First_Name"],
    count: 1,
  },
};

function mockApiGet(response = MOCK_RESPONSE) {
  api.get.mockResolvedValue(response);
}

describe("useSubmissions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("ordering param in API call", () => {
    it("includes ordering in request params when provided", async () => {
      mockApiGet();
      renderHook(() =>
        useSubmissions({ assetUid: "formX", ordering: "start" }),
      );

      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      const params = api.get.mock.calls[0][1].params;
      expect(params.ordering).toBe("start");
    });

    it("includes descending ordering in request params", async () => {
      mockApiGet();
      renderHook(() =>
        useSubmissions({ assetUid: "formX", ordering: "-area_ha" }),
      );

      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      const params = api.get.mock.calls[0][1].params;
      expect(params.ordering).toBe("-area_ha");
    });

    it("omits ordering from params when null", async () => {
      mockApiGet();
      renderHook(() =>
        useSubmissions({ assetUid: "formX", ordering: null }),
      );

      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      const params = api.get.mock.calls[0][1].params;
      expect(params).not.toHaveProperty("ordering");
    });

    it("omits ordering from params when undefined", async () => {
      mockApiGet();
      renderHook(() => useSubmissions({ assetUid: "formX" }));

      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      const params = api.get.mock.calls[0][1].params;
      expect(params).not.toHaveProperty("ordering");
    });
  });

  describe("pagination reset on ordering change", () => {
    it("resets page to 1 when ordering changes", async () => {
      mockApiGet({
        data: {
          results: Array.from({ length: 10 }, (_, i) => ({ uuid: `s-${i}` })),
          questions: [],
          sortable_fields: [],
          count: 30,
        },
      });

      const { result, rerender } = renderHook(
        ({ ordering }) =>
          useSubmissions({ assetUid: "formX", ordering }),
        { initialProps: { ordering: null } },
      );

      await waitFor(() => {
        expect(api.get).toHaveBeenCalledTimes(1);
      });

      // Navigate to page 2
      act(() => {
        result.current.setPage(2);
      });

      await waitFor(() => {
        expect(result.current.page).toBe(2);
      });

      // Change ordering — should reset to page 1
      rerender({ ordering: "start" });

      await waitFor(() => {
        expect(result.current.page).toBe(1);
      });
    });

    it("resets page to 1 when ordering direction changes", async () => {
      mockApiGet({
        data: {
          results: Array.from({ length: 10 }, (_, i) => ({ uuid: `s-${i}` })),
          questions: [],
          sortable_fields: [],
          count: 30,
        },
      });

      const { result, rerender } = renderHook(
        ({ ordering }) =>
          useSubmissions({ assetUid: "formX", ordering }),
        { initialProps: { ordering: "start" } },
      );

      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      // Navigate to page 3
      act(() => {
        result.current.setPage(3);
      });

      await waitFor(() => {
        expect(result.current.page).toBe(3);
      });

      // Change from asc to desc — should reset
      rerender({ ordering: "-start" });

      await waitFor(() => {
        expect(result.current.page).toBe(1);
      });
    });

    it("resets page to 1 when ordering is cleared", async () => {
      mockApiGet({
        data: {
          results: Array.from({ length: 10 }, (_, i) => ({ uuid: `s-${i}` })),
          questions: [],
          sortable_fields: [],
          count: 30,
        },
      });

      const { result, rerender } = renderHook(
        ({ ordering }) =>
          useSubmissions({ assetUid: "formX", ordering }),
        { initialProps: { ordering: "-start" } },
      );

      await waitFor(() => {
        expect(api.get).toHaveBeenCalled();
      });

      act(() => {
        result.current.setPage(2);
      });

      await waitFor(() => {
        expect(result.current.page).toBe(2);
      });

      // Clear ordering
      rerender({ ordering: null });

      await waitFor(() => {
        expect(result.current.page).toBe(1);
      });
    });
  });

  describe("sortableFields from API response", () => {
    it("returns sortableFields from response", async () => {
      mockApiGet();
      const { result } = renderHook(() =>
        useSubmissions({ assetUid: "formX" }),
      );

      await waitFor(() => {
        expect(result.current.sortableFields).toEqual(["First_Name"]);
      });
    });

    it("defaults to empty array when not in response", async () => {
      api.get.mockResolvedValue({
        data: { results: [], questions: [], count: 0 },
      });
      const { result } = renderHook(() =>
        useSubmissions({ assetUid: "formX" }),
      );

      await waitFor(() => {
        expect(result.current.sortableFields).toEqual([]);
      });
    });
  });

  describe("does not fetch without assetUid", () => {
    it("skips API call when assetUid is not provided", async () => {
      renderHook(() => useSubmissions({ ordering: "start" }));

      // Give it a tick to potentially fire
      await new Promise((r) => setTimeout(r, 50));
      expect(api.get).not.toHaveBeenCalled();
    });
  });
});