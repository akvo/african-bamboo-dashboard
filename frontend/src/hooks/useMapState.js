"use client";

import { useState, useCallback, useMemo } from "react";

export function useMapState({ plots, initialPlotId = null }) {
  const [selectedPlotId, setSelectedPlotId] = useState(initialPlotId);
  const [panelMode, setPanelMode] = useState(initialPlotId ? "detail" : "list");
  const [editingPlotId, setEditingPlotId] = useState(null);
  const [approvalDialogOpen, setApprovalDialogOpen] = useState(false);
  const [rejectionDialogOpen, setRejectionDialogOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("all");
  const [sortBy, setSortBy] = useState("priority");
  const [search, setSearch] = useState("");
  const [toast, setToast] = useState(null);

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
      if (plotUuid) setPanelMode("detail");
    },
    [editingPlotId],
  );

  const handleBackToList = useCallback(() => {
    setSelectedPlotId(null);
    setPanelMode("list");
    setEditingPlotId(null);
  }, []);

  const handleStartEditing = useCallback(() => {
    if (selectedPlotId) setEditingPlotId(selectedPlotId);
  }, [selectedPlotId]);

  const handleCancelEditing = useCallback(() => {
    setEditingPlotId(null);
  }, []);

  return {
    selectedPlotId,
    selectedPlot,
    panelMode,
    editingPlotId,
    approvalDialogOpen,
    rejectionDialogOpen,
    activeTab,
    sortBy,
    search,
    toast,
    setActiveTab,
    setSortBy,
    setSearch,
    setToastMessage,
    setApprovalDialogOpen,
    setRejectionDialogOpen,
    handleSelectPlot,
    handleBackToList,
    handleStartEditing,
    handleCancelEditing,
    setEditingPlotId,
  };
}
