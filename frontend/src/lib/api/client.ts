import axios from "axios";

const TOKEN_KEY = "indexxxer_token";

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

const client = axios.create({
  baseURL: "/api/v1",
  headers: { "Content-Type": "application/json" },
});

// Attach token on every request
client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers["X-API-Token"] = token;
  }
  return config;
});

export default client;
