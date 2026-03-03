import type { User, UserCreate, UserUpdate } from "@/types/api";
import client from "./client";

export async function listUsers(): Promise<User[]> {
  const { data } = await client.get<User[]>("/users");
  return data;
}

export async function createUser(payload: UserCreate): Promise<User> {
  const { data } = await client.post<User>("/users", payload);
  return data;
}

export async function updateUser(id: string, payload: UserUpdate): Promise<User> {
  const { data } = await client.put<User>(`/users/${id}`, payload);
  return data;
}

export async function deleteUser(id: string): Promise<void> {
  await client.delete(`/users/${id}`);
}
