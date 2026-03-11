"use client";

import { useState, useEffect, useCallback } from "react";
import Image from "next/image";
import { X, ChevronLeft, ChevronRight, Image as ImageIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function TitleDeedViewer({ open, onClose, attachments = [] }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [imgError, setImgError] = useState(false);

  // Reset index and error when attachments change or viewer opens
  useEffect(() => {
    setCurrentIndex(0);
    setImgError(false);
  }, [attachments, open]);

  useEffect(() => {
    setImgError(false);
  }, [currentIndex]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e) => {
      if (!open) return;
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowLeft" && currentIndex > 0) {
        setCurrentIndex((i) => i - 1);
      } else if (
        e.key === "ArrowRight" &&
        currentIndex < attachments.length - 1
      ) {
        setCurrentIndex((i) => i + 1);
      }
    },
    [open, onClose, currentIndex, attachments.length],
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  if (!open || attachments.length === 0) return null;

  const current = attachments[currentIndex];
  const hasMultiple = attachments.length > 1;

  return (
    <div className="max-w-lg h-[400px] absolute bottom-16 left-0 inset-x-0 z-30 flex flex-col border-l border-border bg-card">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b border-border px-4 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <ImageIcon className="size-4 shrink-0 text-muted-foreground" />
          <span className="truncate text-xs text-muted-foreground">
            {current?.media_file_basename}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {hasMultiple && (
            <>
              <span className="whitespace-nowrap text-xs text-muted-foreground">
                Page {currentIndex + 1} of {attachments.length}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="size-7"
                disabled={currentIndex === 0}
                onClick={() => setCurrentIndex((i) => i - 1)}
                aria-label="Previous image"
              >
                <ChevronLeft className="size-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="size-7"
                disabled={currentIndex === attachments.length - 1}
                onClick={() => setCurrentIndex((i) => i + 1)}
                aria-label="Next image"
              >
                <ChevronRight className="size-3.5" />
              </Button>
            </>
          )}
          <span className="text-muted-foreground/30">|</span>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={onClose}
          >
            Close
            <X className="ml-1 size-3.5" />
          </Button>
        </div>
      </div>

      {/* Image area */}
      <div className="relative min-h-0 flex-1">
        {current?.local_url && !imgError ? (
          <Image
            src={current.local_url}
            alt={current.media_file_basename || "Title deed"}
            fill
            className="object-contain p-2"
            onError={() => setImgError(true)}
            sizes="50vw"
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-3">
            <ImageIcon className="size-12 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">
              {imgError
                ? "Unable to load title deed image."
                : "No title deed uploaded"}
            </p>
            {imgError && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setImgError(false)}
              >
                Retry
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
