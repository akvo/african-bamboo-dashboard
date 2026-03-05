"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function ConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  icon: Icon,
  iconClassName = "text-primary",
  iconBgClassName = "bg-primary/15",
  title,
  description,
  confirmLabel = "Confirm",
  confirmingLabel = "Processing...",
  confirmVariant = "default",
  confirmClassName,
  textarea,
  select,
}) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectValue, setSelectValue] = useState("");
  const [notes, setNotes] = useState("");

  const needsInput = !!textarea;
  const needsSelect = !!select;
  const isDisabled =
    isSubmitting ||
    (textarea?.required && !notes.trim()) ||
    (select?.required && !selectValue);

  const handleConfirm = async () => {
    setIsSubmitting(true);
    try {
      await onConfirm({
        notes: needsInput ? notes : undefined,
        selectValue: needsSelect ? selectValue : undefined,
      });
      setNotes("");
      setSelectValue("");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenChange = (val) => {
    if (!val) {
      setSelectValue("");
      setNotes("");
    }
    onOpenChange(val);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          {Icon && (
            <div
              className={`mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full ${iconBgClassName}`}
            >
              <Icon className={`h-6 w-6 ${iconClassName}`} />
            </div>
          )}
          <DialogTitle className="text-center">{title}</DialogTitle>
          {description && (
            <DialogDescription className="text-center">
              {description}
            </DialogDescription>
          )}
        </DialogHeader>
        {select && (
          <div className="space-y-2">
            <label
              htmlFor="confirm-dialog-select"
              className="text-sm font-medium"
            >
              {select.label}
            </label>
            <Select value={selectValue} onValueChange={setSelectValue}>
              <SelectTrigger id="confirm-dialog-select" className="w-full">
                <SelectValue placeholder={select.placeholder || "Select..."} />
              </SelectTrigger>
              <SelectContent>
                {(select.options || []).map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        {textarea && (
          <div className="space-y-2">
            <label
              htmlFor="confirm-dialog-input"
              className="text-sm font-medium"
            >
              {textarea.label}
            </label>
            <Textarea
              id="confirm-dialog-input"
              placeholder={textarea.placeholder}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              required={textarea.required}
            />
          </div>
        )}
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            variant={confirmVariant}
            className={confirmClassName}
            onClick={handleConfirm}
            disabled={isDisabled}
          >
            {isSubmitting ? confirmingLabel : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
