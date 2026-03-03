import type { FilterCreate, SavedFilter } from "@/types/api";
import client from "./client";

export async function listFilters() {
  const { data } = await client.get<SavedFilter[]>("/filters");
  return data;
}

export async function createFilter(payload: FilterCreate) {
  const { data } = await client.post<SavedFilter>("/filters", payload);
  return data;
}

export async function updateFilter(id: string, payload: Partial<FilterCreate>) {
  const { data } = await client.put<SavedFilter>(`/filters/${id}`, payload);
  return data;
}

export async function deleteFilter(id: string) {
  await client.delete(`/filters/${id}`);
}
