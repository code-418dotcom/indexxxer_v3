"use client";

import Image from "next/image";
import { ChevronLeft, ChevronRight, Download, X } from "lucide-react";
import { useEffect } from "react";
import { galleryImageUrl } from "@/lib/api/galleries";
import type { GalleryImage } from "@/types/api";

interface GalleryLightboxProps {
  galleryId: string;
  images: GalleryImage[];
  index: number;
  onClose: () => void;
  onNavigate: (index: number) => void;
}

export function GalleryLightbox({
  galleryId,
  images,
  index,
  onClose,
  onNavigate,
}: GalleryLightboxProps) {
  const current = images[index];
  const hasPrev = index > 0;
  const hasNext = index < images.length - 1;

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") { onClose(); return; }
      if (e.key === "ArrowLeft"  && hasPrev) { onNavigate(index - 1); return; }
      if (e.key === "ArrowRight" && hasNext) { onNavigate(index + 1); return; }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [index, hasPrev, hasNext, onClose, onNavigate]);

  // Lock body scroll while open
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  if (!current) return null;

  const imgUrl = galleryImageUrl(galleryId, current.index_order);
  const filename = current.filename.split("/").pop() ?? current.filename;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/95 flex flex-col"
      onClick={onClose}
    >
      {/* Header */}
      <div
        className="flex items-center gap-3 px-4 py-3 shrink-0"
        onClick={(e) => e.stopPropagation()}
      >
        <span className="flex-1 text-sm font-medium text-white/80 truncate min-w-0">
          {filename}
        </span>
        <span className="text-xs text-white/40 shrink-0">
          {index + 1} / {images.length}
        </span>
        <a
          href={imgUrl}
          download={filename}
          className="p-2 rounded-lg text-white/50 hover:text-white transition-colors shrink-0"
          title="Download"
          onClick={(e) => e.stopPropagation()}
        >
          <Download className="w-4 h-4" />
        </a>
        <button
          onClick={onClose}
          className="p-2 rounded-lg text-white/50 hover:text-white transition-colors shrink-0"
          title="Close (Esc)"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Image area */}
      <div
        className="flex-1 flex items-center justify-center min-h-0 relative px-16"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Prev button */}
        <button
          onClick={() => hasPrev && onNavigate(index - 1)}
          disabled={!hasPrev}
          className="absolute left-3 top-1/2 -translate-y-1/2 p-2 rounded-full bg-white/10 hover:bg-white/20 text-white disabled:opacity-20 disabled:cursor-not-allowed transition-all z-10"
          title="Previous (←)"
        >
          <ChevronLeft className="w-6 h-6" />
        </button>

        {/* Image */}
        <div className="relative w-full h-full">
          <Image
            key={`${galleryId}-${current.index_order}`}
            src={imgUrl}
            alt={filename}
            fill
            className="object-contain"
            unoptimized
            priority
          />
        </div>

        {/* Next button */}
        <button
          onClick={() => hasNext && onNavigate(index + 1)}
          disabled={!hasNext}
          className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-full bg-white/10 hover:bg-white/20 text-white disabled:opacity-20 disabled:cursor-not-allowed transition-all z-10"
          title="Next (→)"
        >
          <ChevronRight className="w-6 h-6" />
        </button>
      </div>

      {/* Bottom: thumbnail strip */}
      <div
        className="shrink-0 flex gap-1.5 px-4 py-3 overflow-x-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {images.map((img) => (
          <button
            key={img.id}
            onClick={() => onNavigate(img.index_order)}
            className={`relative shrink-0 w-14 h-14 rounded overflow-hidden transition-all ${
              img.index_order === index
                ? "ring-2 ring-white opacity-100"
                : "opacity-40 hover:opacity-70"
            }`}
          >
            <Image
              src={galleryImageUrl(galleryId, img.index_order)}
              alt={`${img.index_order + 1}`}
              fill
              className="object-cover"
              unoptimized
            />
          </button>
        ))}
      </div>
    </div>
  );
}
