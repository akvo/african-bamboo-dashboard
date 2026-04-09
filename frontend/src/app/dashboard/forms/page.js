"use client";

import { useState } from "react";
import { useForms } from "@/hooks/useForms";
import { FormRegisterCard } from "@/components/form-register-card";
import { FormsTable } from "@/components/forms-table";
import { FieldMappingDialog } from "@/components/field-mapping-dialog";

export default function FormsPage() {
  const {
    forms,
    isLoading,
    registerForm,
    syncForm,
    updateForm,
    fetchFormFields,
  } = useForms();
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [configForm, setConfigForm] = useState(null);

  function handleConfigureClick(form) {
    setConfigForm(form);
    setConfigDialogOpen(true);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Forms</h1>
        <p className="text-sm text-muted-foreground">
          Manage your registered KoboToolbox forms
        </p>
      </div>

      <FormRegisterCard registerForm={registerForm} />

      <FormsTable
        forms={forms}
        isLoading={isLoading}
        syncForm={syncForm}
        onConfigureClick={handleConfigureClick}
      />

      <FieldMappingDialog
        open={configDialogOpen}
        onOpenChange={setConfigDialogOpen}
        form={configForm}
        fetchFormFields={fetchFormFields}
        updateForm={updateForm}
      />
    </div>
  );
}
