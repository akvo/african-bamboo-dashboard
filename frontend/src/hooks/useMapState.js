"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  useEffect,
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
  const [search, setSearch] = useState("");
  const [toast, setToast] = useState(null);
  const [notes, setNotes] = useState("");

  const formId = activeForm?.asset_uid;

  const fetchPlots = useCallback(async () => {
    if (!formId) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.get("/v1/odk/plots/", {
        params: { form_id: formId, limit: 200 },
      });
      setPlots(res.data.results || []);
      setCount(res.data.count || 0);
    } catch (err) {
      setError(err.response?.data?.message || "Failed to fetch plots");
    } finally {
      setIsLoading(false);
    }
  }, [formId]);

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

  const selectedPlot = useMemo(
    () => plots.find((p) => p.uuid === selectedPlotId) || null,
    [plots, selectedPlotId],
  );

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
        editingPlotId,
        approvalDialogOpen,
        rejectionDialogOpen,
        activeTab,
        sortBy,
        search,
        toast,
        notes,
        setNotes,
        setActiveTab,
        setSortBy,
        setSearch,
        setToastMessage,
        setApprovalDialogOpen,
        setRejectionDialogOpen,
        setSelectedPlotId,
        handleSelectPlot,
        handleBackToList,
        handleStartEditing,
        handleCancelEditing,
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
