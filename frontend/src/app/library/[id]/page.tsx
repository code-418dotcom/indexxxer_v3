"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getMedia } from "@/lib/api/media";
import { MediaDetail } from "@/components/media/MediaDetail";
import { Topbar } from "@/components/layout/Topbar";
import { ChevronLeft, Loader2 } from "lucide-react";

export default function MediaDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const { data: item, isLoading } = useQuery({
    queryKey: ["media", id],
    queryFn: () => getMedia(id),
  });

  return (
    <div className="flex flex-col h-full">
      <Topbar title={item?.filename ?? "Media detail"}>
        <Link
          href="/library"
          className="flex items-center gap-1 text-xs text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
          Back to library
        </Link>
      </Topbar>

      <div className="flex-1 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-full gap-2 text-[var(--color-muted-foreground)]">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">Loading…</span>
          </div>
        ) : item ? (
          <MediaDetail item={item} />
        ) : (
          <div className="flex items-center justify-center h-full text-[var(--color-muted-foreground)] text-sm">
            Media not found
          </div>
        )}
      </div>
    </div>
  );
}
