"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
} from "react";
import { useForms } from "@/hooks/useForms";
import api from "@/lib/api";

const MapStateContext = createContext(null);

export function MapStateProvider({ children }) {
  const { activeForm } = useForms();

  const [plots, setPlots] = useState([]);
  const [count, setCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedPlotId, setSelectedPlotId] = useState(null);
  const [editingPlotId, setEditingPlotId] = useState(null);
  const [approvalDialogOpen, setApprovalDialogOpen] = useState(false);
  const [rejectionDialogOpen, setRejectionDialogOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("all");
  const [sortBy, setSortBy] = useState("priority");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const searchTimeoutRef = useRef(null);

  const handleSearchChange = useCallback((value) => {
    setSearchInput(value);
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    searchTimeoutRef.current = setTimeout(() => {
      setSearch(value);
    }, 500);
  }, []);

  useEffect(() => () => clearTimeout(searchTimeoutRef.current), []);

  const [startDate, setStartDate] = useState(null);
  const [endDate, setEndDate] = useState(null);
  const [region, setRegion] = useState("");
  const [subRegion, setSubRegion] = useState("");
  const [dynamicValues, setDynamicValues] = useState({});
  const [activeFilterFields, setActiveFilterFields] = useState(() => {
    if (typeof window === "undefined") return [];
    try {
      const stored = localStorage.getItem("activeFilterFields");
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });
  const [toast, setToast] = useState(null);

  const formId = activeForm?.asset_uid;

  // Persist activeFilterFields to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(
        "activeFilterFields",
        JSON.stringify(activeFilterFields),
      );
    } catch {
      // ignore storage errors
    }
  }, [activeFilterFields]);

  // Initialize activeFilterFields from form config
  useEffect(() => {
    if (activeForm?.filter_fields) {
      setActiveFilterFields(activeForm.filter_fields);
    }
  }, [activeForm]);

  // Debounced save of activeFilterFields to backend
  const saveFilterFieldsRef = useRef(null);
  const initializedRef = useRef(false);
  useEffect(() => {
    // Skip the first render (initialization from activeForm)
    if (!initializedRef.current) {
      initializedRef.current = true;
      return;
    }
    if (!formId) return;
    if (saveFilterFieldsRef.current) clearTimeout(saveFilterFieldsRef.current);
    saveFilterFieldsRef.current = setTimeout(() => {
      api
        .patch(`/v1/odk/forms/${formId}/`, {
          filter_fields:
            activeFilterFields.length > 0 ? activeFilterFields : null,
        })
        .catch(() => {});
    }, 1000);
    return () => {
      if (saveFilterFieldsRef.current)
        clearTimeout(saveFilterFieldsRef.current);
    };
  }, [formId, activeFilterFields]);
  const startMs = startDate ? startDate.getTime() : null;
  const endMs = endDate ? endDate.getTime() : null;

  const fetchPlots = useCallback(async () => {
    if (!formId) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const params = { form_id: formId, limit: 200 };
      if (activeTab && activeTab !== "all") params.status = activeTab;
      if (search) params.search = search;
      if (sortBy && sortBy !== "priority") params.sort = sortBy;
      if (startMs) params.start_date = startMs;
      if (endMs) params.end_date = endMs;
      if (region) params.region = region;
      if (subRegion) params.sub_region = subRegion;
      Object.entries(dynamicValues).forEach(([k, v]) => {
        if (v) params[`filter__${k}`] = v;
      });
      const res = await api.get("/v1/odk/plots/", { params });
      setPlots(res.data.results || []);
      setCount(res.data.count || 0);
    } catch (err) {
      setError(err.response?.data?.message || "Failed to fetch plots");
    } finally {
      setIsLoading(false);
    }
  }, [
    formId,
    activeTab,
    search,
    sortBy,
    startMs,
    endMs,
    region,
    subRegion,
    dynamicValues,
  ]);

  useEffect(() => {
    fetchPlots();
  }, [fetchPlots]);

  const setToastMessage = useCallback((msgOrObj) => {
    if (msgOrObj === null) {
      setToast(null);
    } else if (typeof msgOrObj === "string") {
      setToast({ message: msgOrObj, type: "success" });
    } else {
      setToast({ message: msgOrObj.message, type: msgOrObj.type || "success" });
    }
  }, []);

  const [selectedPlot, setSelectedPlot] = useState(null);
  const [isLoadingPlot, setIsLoadingPlot] = useState(false);
  const latestPlotRequestRef = useRef(0);

  const fetchSelectedPlot = useCallback(async (plotId) => {
    const requestId = ++latestPlotRequestRef.current;
    if (!plotId) {
      setSelectedPlot(null);
      setIsLoadingPlot(false);
      return;
    }
    setIsLoadingPlot(true);
    try {
      const res = await api.get(`/v1/odk/plots/${plotId}/`);
      if (requestId === latestPlotRequestRef.current) {
        setSelectedPlot(res.data);
      }
    } catch {
      if (requestId === latestPlotRequestRef.current) {
        setSelectedPlot(null);
      }
    } finally {
      if (requestId === latestPlotRequestRef.current) {
        setIsLoadingPlot(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchSelectedPlot(selectedPlotId);
  }, [selectedPlotId, fetchSelectedPlot]);

  const refetchSelectedPlot = useCallback(() => {
    return fetchSelectedPlot(selectedPlotId);
  }, [selectedPlotId, fetchSelectedPlot]);

  const handleSelectPlot = useCallback(
    (plotUuid) => {
      if (editingPlotId && plotUuid !== editingPlotId) return;
      setSelectedPlotId(plotUuid);
    },
    [editingPlotId],
  );

  const handleBackToList = useCallback(() => {
    setSelectedPlotId(null);
    setEditingPlotId(null);
  }, []);

  const handleStartEditing = useCallback(() => {
    if (selectedPlotId) {
      setEditingPlotId(selectedPlotId);
    }
  }, [selectedPlotId]);

  const handleCancelEditing = useCallback(() => {
    setEditingPlotId(null);
  }, []);

  const handleResetFilters = useCallback(() => {
    setSelectedPlotId(null);
    setActiveTab("all");
    setSortBy("priority");
    setSearchInput("");
    setSearch("");
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    setStartDate(null);
    setEndDate(null);
    setRegion("");
    setSubRegion("");
    setDynamicValues({});
  }, []);

  return (
    <MapStateContext.Provider
      value={{
        plots,
        count,
        isLoading,
        error,
        refetch: fetchPlots,
        selectedPlotId,
        selectedPlot,
        isLoadingPlot,
        refetchSelectedPlot,
        editingPlotId,
        approvalDialogOpen,
        rejectionDialogOpen,
        activeTab,
        sortBy,
        search,
        searchInput,
        startDate,
        endDate,
        region,
        subRegion,
        dynamicValues,
        activeFilterFields,
        toast,
        setActiveTab,
        setSortBy,
        handleSearchChange,
        setStartDate,
        setEndDate,
        setRegion,
        setSubRegion,
        setDynamicValues,
        setActiveFilterFields,
        setToastMessage,
        setApprovalDialogOpen,
        setRejectionDialogOpen,
        setSelectedPlotId,
        handleSelectPlot,
        handleBackToList,
        handleStartEditing,
        handleCancelEditing,
        handleResetFilters,
        setEditingPlotId,
      }}
    >
      {children}
    </MapStateContext.Provider>
  );
}

export function useMapState() {
  const context = useContext(MapStateContext);
  if (!context) {
    throw new Error("useMapState must be used within a MapStateProvider");
  }
  return context;
}
