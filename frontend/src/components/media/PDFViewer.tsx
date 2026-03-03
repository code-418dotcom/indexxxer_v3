"use client";

import { useEffect, useState, useCallback } from "react";
import { X, ChevronLeft, ChevronRight, Download } from "lucide-react";
import { pdfPageUrl } from "@/lib/api/pdfs";
import type { PDFDocument } from "@/types/api";

interface PDFViewerProps {
  pdf: PDFDocument;
  initialPage?: number;
  onClose: () => void;
}

export function PDFViewer({ pdf, initialPage = 0, onClose }: PDFViewerProps) {
  const [page, setPage] = useState(initialPage);
  const [loaded, setLoaded] = useState(false);

  const prev = useCallback(() => setPage((p) => Math.max(0, p - 1)), []);
  const next = useCallback(
    () => setPage((p) => Math.min(pdf.page_count - 1, p + 1)),
    [pdf.page_count]
  );

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "ArrowRight") next();
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, prev, next]);

  // Lock body scroll
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  // Reset loaded state when page changes
  useEffect(() => setLoaded(false), [page]);

  const pageUrl = pdfPageUrl(pdf.id, page);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/95" onClick={onClose}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 bg-[hsl(222_47%_5%)] border-b border-[hsl(217_33%_13%)] shrink-0"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-white font-medium truncate">
            {pdf.title || pdf.filename}
          </span>
          <span className="text-neutral-500 text-sm shrink-0">
            Page {page + 1} / {pdf.page_count}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <a
            href={`/api/v1/pdfs/${pdf.id}/download`}
            download={pdf.filename}
            className="p-1.5 rounded text-neutral-400 hover:text-white hover:bg-white/10 transition-colors"
            title="Download PDF"
          >
            <Download className="w-4 h-4" />
          </a>
          <button
            onClick={onClose}
            className="p-1.5 rounded text-neutral-400 hover:text-white hover:bg-white/10 transition-colors"
            title="Close (Esc)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Page display */}
      <div
        className="flex-1 flex items-center justify-center relative overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Prev button */}
        <button
          onClick={prev}
          disabled={page === 0}
          className="absolute left-3 z-10 p-2 rounded-full bg-black/60 text-white hover:bg-black/80 disabled:opacity-20 disabled:cursor-not-allowed transition-all"
          title="Previous page (←)"
        >
          <ChevronLeft className="w-6 h-6" />
        </button>

        {/* Page image */}
        <div className="flex items-center justify-center w-full h-full px-16 py-4">
          {!loaded && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            key={pageUrl}
            src={pageUrl}
            alt={`Page ${page + 1}`}
            onLoad={() => setLoaded(true)}
            className="max-w-full max-h-full object-contain shadow-2xl"
            style={{ maxHeight: "calc(100vh - 120px)", opacity: loaded ? 1 : 0, transition: "opacity 0.15s" }}
          />
        </div>

        {/* Next button */}
        <button
          onClick={next}
          disabled={page === pdf.page_count - 1}
          className="absolute right-3 z-10 p-2 rounded-full bg-black/60 text-white hover:bg-black/80 disabled:opacity-20 disabled:cursor-not-allowed transition-all"
          title="Next page (→)"
        >
          <ChevronRight className="w-6 h-6" />
        </button>
      </div>

      {/* Page indicator bar */}
      <div
        className="flex items-center justify-center gap-2 py-3 bg-[hsl(222_47%_5%)] border-t border-[hsl(217_33%_13%)] shrink-0"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={prev}
          disabled={page === 0}
          className="px-3 py-1 text-sm text-neutral-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
        >
          ← Prev
        </button>
        <span className="text-neutral-500 text-sm min-w-[80px] text-center">
          {page + 1} / {pdf.page_count}
        </span>
        <button
          onClick={next}
          disabled={page === pdf.page_count - 1}
          className="px-3 py-1 text-sm text-neutral-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Next →
        </button>
      </div>
    </div>
  );
}
