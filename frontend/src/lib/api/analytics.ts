import type { AnalyticsOverview, IndexingStats, QueryStats } from "@/types/api";
import client from "./client";

export async function getOverview(): Promise<AnalyticsOverview> {
  const { data } = await client.get<AnalyticsOverview>("/analytics/overview");
  return data;
}

export async function getQueryStats(days = 30): Promise<QueryStats> {
  const { data } = await client.get<QueryStats>("/analytics/queries", { params: { days } });
  return data;
}

export async function getIndexingStats(days = 30): Promise<IndexingStats> {
  const { data } = await client.get<IndexingStats>("/analytics/indexing", { params: { days } });
  return data;
}
