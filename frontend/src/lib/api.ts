/**
 * Cliente HTTP para comunicação com a API
 */

import axios, { AxiosError, AxiosInstance } from "axios";
import { useAuthStore } from "@/store/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const api: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Interceptor para adicionar token de autenticação
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Interceptor para tratar erros de autenticação
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;
    
    // Se 401 e não é refresh, tentar renovar token
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest.url?.includes("/auth/refresh")
    ) {
      const refreshToken = useAuthStore.getState().refreshToken;
      
      if (refreshToken) {
        try {
          const { data } = await api.post("/auth/refresh", {
            refresh_token: refreshToken,
          });
          
          useAuthStore.getState().setTokens(data.access_token, data.refresh_token);
          
          // Retry da requisição original
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
          }
          return api(originalRequest);
        } catch {
          // Refresh falhou, fazer logout
          useAuthStore.getState().logout();
          window.location.href = "/login";
        }
      }
    }
    
    return Promise.reject(error);
  }
);

// Tipos de erro da API
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
