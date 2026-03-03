import type { LoginRequest, TokenResponse, User } from "@/types/api";
import axios from "axios";
import client, { clearTokens, setTokens } from "./client";

export async function login(email: string, password: string): Promise<TokenResponse> {
  // Use plain axios (no auth header needed for login)
  const { data } = await axios.post<TokenResponse>("/api/v1/auth/login", { email, password } as LoginRequest);
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function logout(): Promise<void> {
  clearTokens();
}

export async function getMe(): Promise<User> {
  const { data } = await client.get<User>("/auth/me");
  return data;
}
