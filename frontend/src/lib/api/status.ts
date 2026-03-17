import client from "./client";

export interface ServiceStatus {
  name: string;
  up: boolean;
}

export interface StatusResponse {
  services: ServiceStatus[];
}

export async function getStatus(): Promise<StatusResponse> {
  const { data } = await client.get<StatusResponse>("/status");
  return data;
}
