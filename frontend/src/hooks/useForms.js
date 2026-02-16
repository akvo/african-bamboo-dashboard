"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import api from "@/lib/api";

const FormsContext = createContext(null);

export function FormsProvider({ children }) {
  const [forms, setForms] = useState([]);
  const [activeForm, setActiveForm] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchForms = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.get("/v1/odk/forms/");
      const list = res.data.results || [];
      setForms(list);
      setActiveForm((prev) => {
        if (prev && list.some((f) => f.asset_uid === prev.asset_uid)) {
          return prev;
        }
        return list[0] || null;
      });
    } catch (err) {
      setError(err.response?.data?.message || "Failed to fetch forms");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchForms();
  }, [fetchForms]);

  const registerForm = useCallback(
    async ({ assetUid, name }) => {
      const res = await api.post("/v1/odk/forms/", {
        asset_uid: assetUid,
        name,
      });
      await fetchForms();
      return res.data;
    },
    [fetchForms],
  );

  const syncForm = useCallback(
    async (formId) => {
      const res = await api.post(`/v1/odk/forms/${formId}/sync/`);
      await fetchForms();
      return res.data;
    },
    [fetchForms],
  );

  const updateForm = useCallback(
    async (assetUid, data) => {
      const res = await api.patch(`/v1/odk/forms/${assetUid}/`, data);
      await fetchForms();
      return res.data;
    },
    [fetchForms],
  );

  const fetchFormFields = useCallback(async (assetUid) => {
    const res = await api.get(`/v1/odk/forms/${assetUid}/form_fields/`);
    return res.data.fields;
  }, []);

  return (
    <FormsContext.Provider
      value={{
        forms,
        activeForm,
        setActiveForm,
        isLoading,
        error,
        registerForm,
        syncForm,
        updateForm,
        fetchFormFields,
        refetch: fetchForms,
      }}
    >
      {children}
    </FormsContext.Provider>
  );
}

export function useForms() {
  const context = useContext(FormsContext);
  if (!context) {
    throw new Error("useForms must be used within a FormsProvider");
  }
  return context;
}
