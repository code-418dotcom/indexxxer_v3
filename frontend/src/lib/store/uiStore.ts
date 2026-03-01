"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ViewMode = "grid" | "list";
export type ThumbnailSize = "sm" | "md" | "lg";

interface UIState {
  viewMode: ViewMode;
  thumbnailSize: ThumbnailSize;
  sidebarCollapsed: boolean;
  setViewMode: (m: ViewMode) => void;
  setThumbnailSize: (s: ThumbnailSize) => void;
  setSidebarCollapsed: (c: boolean) => void;
  toggleSidebar: () => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      viewMode: "grid",
      thumbnailSize: "md",
      sidebarCollapsed: false,

      setViewMode: (viewMode) => set({ viewMode }),
      setThumbnailSize: (thumbnailSize) => set({ thumbnailSize }),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
      toggleSidebar: () =>
        set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
    }),
    {
      name: "indexxxer-ui",
      partialState: (state: UIState) => ({
        viewMode: state.viewMode,
        thumbnailSize: state.thumbnailSize,
        sidebarCollapsed: state.sidebarCollapsed,
      }),
    }
  )
);
