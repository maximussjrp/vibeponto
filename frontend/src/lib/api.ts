/**
 * Cliente HTTP para comunicacao com a API.
 */

import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type AuthHandlers = {
  getAccessToken: () => string | null;
  refreshAccessToken: () => Promise<string | null>;
  clearAuth: () => void;
};

let authHandlers: AuthHandlers | null = null;

export function setAuthHandlers(handlers: AuthHandlers) {
  authHandlers = handlers;
}

export const api: AxiosInstance = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
    "X-Auth-Mode": "cookie",
  },
});

const refreshClient: AxiosInstance = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
    "X-Auth-Mode": "cookie",
  },
});

let refreshPromise: Promise<string | null> | null = null;

export async function requestNewAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = refreshClient
      .post("/auth/refresh")
      .then((response) => response.data?.access_token ?? null)
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

api.interceptors.request.use((config) => {
  config.headers.set?.("X-Auth-Mode", "cookie");

  const token = authHandlers?.getAccessToken();
  if (token) {
    config.headers.set?.("Authorization", `Bearer ${token}`);
  }

  return config;
});

function isRefreshRequest(config?: InternalAxiosRequestConfig) {
  return Boolean(config?.url?.includes("/auth/refresh"));
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isRefreshRequest(originalRequest) &&
      authHandlers
    ) {
      originalRequest._retry = true;

      const accessToken = await authHandlers.refreshAccessToken();
      if (accessToken) {
        originalRequest.headers.set?.("Authorization", `Bearer ${accessToken}`);
        return api(originalRequest);
      }

      authHandlers.clearAuth();
    }

    return Promise.reject(error);
  }
);

export interface APIError {
  detail: string;
  status_code?: number;
}

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const apiError = error.response?.data as APIError;
    return apiError?.detail || error.message || "Erro desconhecido";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Erro desconhecido";
}

export default api;
