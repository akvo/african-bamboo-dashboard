"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { X, ChevronLeft, ChevronRight, Image as ImageIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function TitleDeedViewer({ open, onClose, attachments = [] }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [imgError, setImgError] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const imgRef = useRef(null);
  const containerRef = useRef(null);

  // Reset index, error and position when attachments change or viewer opens
  useEffect(() => {
    setCurrentIndex(0);
    setImgError(false);
    setPosition({ x: 0, y: 0 });
  }, [attachments, open]);

  useEffect(() => {
    setImgError(false);
    setPosition({ x: 0, y: 0 });
  }, [currentIndex]);

  const clampPosition = useCallback((x, y) => {
    const img = imgRef.current;
    const container = containerRef.current;
    if (!img || !container) {return { x, y };}

    const cRect = container.getBoundingClientRect();
    const iRect = img.getBoundingClientRect();
    const overflowX = Math.max(0, iRect.width - cRect.width);
    const overflowY = Math.max(0, iRect.height - cRect.height);
    return {
      x: Math.max(-overflowX / 2, Math.min(overflowX / 2, x)),
      y: Math.max(-overflowY / 2, Math.min(overflowY / 2, y)),
    };
  }, []);

  const handlePointerDown = useCallback(
    (e) => {
      e.preventDefault();
      setDragging(true);
      setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
      e.currentTarget.setPointerCapture(e.pointerId);
    },
    [position],
  );

  const handlePointerMove = useCallback(
    (e) => {
      if (!dragging) {return;}
      const newX = e.clientX - dragStart.x;
      const newY = e.clientY - dragStart.y;
      setPosition(clampPosition(newX, newY));
    },
    [dragging, dragStart, clampPosition],
  );

  const handlePointerUp = useCallback(() => {
    setDragging(false);
  }, []);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e) => {
      if (!open) {return;}
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

  if (!open || attachments.length === 0) {return null;}

  const current = attachments[currentIndex];
  const hasMultiple = attachments.length > 1;

  return (
    <div className="max-w-xl max-h-[calc(100vh-4rem)] absolute bottom-6 left-0 inset-x-0 z-30 flex flex-col border-l border-border bg-card overflow-hidden">
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
      {current?.local_url && !imgError ? (
        <div
          ref={containerRef}
          className="relative flex-1 min-h-0 overflow-hidden"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            ref={imgRef}
            src={current.local_url}
            alt={current.media_file_basename || "Title deed"}
            className="h-full w-full object-contain select-none"
            style={{
              transform: `translate(${position.x}px, ${position.y}px)`,
              cursor: dragging ? "grabbing" : "grab",
            }}
            draggable={false}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onError={() => setImgError(true)}
          />
        </div>
      ) : (
        <div className="flex min-h-[200px] flex-col items-center justify-center gap-3">
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
  );
}
