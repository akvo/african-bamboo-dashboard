"use client";

import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
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

export default function ApprovalDialog({ open, onOpenChange, onConfirm }) {
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleConfirm = async () => {
    setIsSubmitting(true);
    try {
      await onConfirm(notes);
      setNotes("");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-status-approved/15">
            <CheckCircle2 className="h-6 w-6 text-status-approved" />
          </div>
          <DialogTitle className="text-center">
            Confirm Approval
          </DialogTitle>
          <DialogDescription className="text-center">
            Approve this plot to confirm the boundary mapping is valid.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <label htmlFor="approval-notes" className="text-sm font-medium">
            Notes to enumerator
          </label>
          <Textarea
            id="approval-notes"
            placeholder="Optional notes..."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            className="bg-status-approved text-white hover:bg-status-approved/90"
            onClick={handleConfirm}
            disabled={isSubmitting}
          >
            {isSubmitting ? "Approving..." : "Confirm"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
