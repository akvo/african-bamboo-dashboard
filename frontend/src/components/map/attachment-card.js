"use client";

import { useState } from "react";
import { Image as ImageIcon } from "lucide-react";

const AttachmentCard = ({ filename, imageUrl, caption, onEdit }) => {
  const [imgError, setImgError] = useState(false);

  return (
    <div className="flex flex-col overflow-hidden rounded-md border border-card-foreground/10">
      {/* File header */}
      <div className="flex items-center gap-3 border-b border-card-foreground/10 bg-white p-3">
        <ImageIcon className="size-5 shrink-0 text-muted-foreground" />
        <span className="flex-1 truncate text-sm text-muted-foreground">
          {filename}
        </span>
        {onEdit && (
          <button
            type="button"
            onClick={onEdit}
            className="cursor-pointer text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Edit
          </button>
        )}
      </div>

      {/* Image preview */}
      {imageUrl && !imgError ? (
        <div className="relative aspect-video w-full bg-muted">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt={caption || filename || "Attachment"}
            className="absolute inset-0 size-full object-cover"
            onError={() => setImgError(true)}
          />
        </div>
      ) : (
        <div className="flex aspect-video w-full items-center justify-center bg-muted">
          <ImageIcon className="size-10 text-muted-foreground/40" />
        </div>
      )}

      {/* Caption */}
      {caption && (
        <div className="bg-white p-3">
          <span className="text-sm text-muted-foreground">{caption}</span>
        </div>
      )}
    </div>
  );
};

export default AttachmentCard;
