"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileText, Search, ScanLine } from "lucide-react";
import { listPDFs, pdfCoverUrl, triggerPDFScan } from "@/lib/api/pdfs";
import { listSources } from "@/lib/api/sources";
import { PDFViewer } from "@/components/media/PDFViewer";
import type { PDFDocument } from "@/types/api";

export default function PDFsPage() {
  const [selectedPDF, setSelectedPDF] = useState<PDFDocument | null>(null);
  const [scanning, setScanning] = useState(false);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const limit = 60;

  const { data, refetch } = useQuery({
    queryKey: ["pdfs", page, search],
    queryFn: () => listPDFs({ limit, page, q: search || undefined }),
    staleTime: 30_000,
  });

  const { data: sources } = useQuery({
    queryKey: ["sources"],
    queryFn: () => listSources(),
  });

  async function handleScan() {
    if (!sources?.length) return;
    setScanning(true);
    try {
      for (const src of sources) {
        await triggerPDFScan(src.id);
      }
      setTimeout(() => { refetch(); setScanning(false); }, 3000);
    } catch {
      setScanning(false);
    }
  }

  const pdfs = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 md:px-6 py-4 border-b border-[hsl(217_33%_13%)] shrink-0">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-blue-400" />
          <h1 className="text-lg font-semibold text-white">PDFs</h1>
          {data && (
            <span className="text-sm text-neutral-500">({total})</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--color-muted-foreground)]" />
            <input
              type="text"
              placeholder="Search PDFs..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="pl-8 pr-3 py-1.5 rounded-lg text-xs w-48 bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
            />
          </div>
          <button
            onClick={handleScan}
            disabled={scanning}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg transition-colors"
          >
            <ScanLine className="w-4 h-4" />
            {scanning ? "Scanning..." : "Scan for PDFs"}
          </button>
        </div>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        {pdfs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-neutral-500 gap-3">
            <FileText className="w-12 h-12 opacity-30" />
            <p>{search ? "No PDFs match your search." : "No PDFs indexed yet. Click \"Scan for PDFs\" to start."}</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {pdfs.map((pdf) => (
              <PDFCard key={pdf.id} pdf={pdf} onClick={() => setSelectedPDF(pdf)} />
            ))}
          </div>
        )}

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1 rounded text-xs border border-[var(--color-border)] hover:bg-[var(--color-muted)] disabled:opacity-30 transition-colors"
            >
              Prev
            </button>
            <span className="text-xs text-[var(--color-muted-foreground)]">
              Page {page} of {pages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              disabled={page >= pages}
              className="px-3 py-1 rounded text-xs border border-[var(--color-border)] hover:bg-[var(--color-muted)] disabled:opacity-30 transition-colors"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Viewer overlay */}
      {selectedPDF && (
        <PDFViewer
          pdf={selectedPDF}
          initialPage={0}
          onClose={() => setSelectedPDF(null)}
        />
      )}
    </div>
  );
}

function PDFCard({ pdf, onClick }: { pdf: PDFDocument; onClick: () => void }) {
  const [imgError, setImgError] = useState(false);

  return (
    <button
      onClick={onClick}
      className="group flex flex-col gap-2 text-left cursor-pointer"
    >
      {/* Cover */}
      <div className="relative aspect-[3/4] w-full bg-[hsl(222_47%_8%)] rounded-lg overflow-hidden border border-[hsl(217_33%_13%)] group-hover:border-blue-500/50 transition-colors">
        {!imgError ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={pdfCoverUrl(pdf.id)}
            alt={pdf.title || pdf.filename}
            onError={() => setImgError(true)}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-neutral-600">
            <FileText className="w-8 h-8" />
            <span className="text-xs">No preview</span>
          </div>
        )}
        {/* Page count badge */}
        <div className="absolute bottom-1.5 right-1.5 bg-black/70 text-white text-xs px-1.5 py-0.5 rounded">
          {pdf.page_count}p
        </div>
      </div>

      {/* Info */}
      <div className="min-w-0">
        <p className="text-xs text-white font-medium truncate leading-tight">
          {pdf.title || pdf.filename}
        </p>
        {pdf.title && (
          <p className="text-xs text-neutral-500 truncate">{pdf.filename}</p>
        )}
      </div>
    </button>
  );
}
