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
import { useMapState } from "@/hooks/useMapState";

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
}) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { notes, setNotes } = useMapState();

  const needsInput = !!textarea;
  const isDisabled = isSubmitting || (textarea?.required && !notes.trim());

  const handleConfirm = async () => {
    setIsSubmitting(true);
    try {
      await onConfirm(needsInput ? notes : undefined);
      setNotes("");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
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
            onClick={() => onOpenChange(false)}
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
