/**
 * Store de autenticação usando Zustand
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import api from "@/lib/api";

export interface User {
  id: string;
  nome: string;
  email: string;
  cpf: string;
  telefone?: string;
  matricula?: string;
  cargo?: string;
  departamento?: string;
  papel: "colaborador" | "gestor" | "admin_dp" | "auditor" | "financeiro";
  status: "active" | "inactive" | "suspended";
  foto_url?: string;
  mfa_enabled: boolean;
  equipe_id?: string;
  tenant_id: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  
  // Actions
  login: (email: string, password: string, mfaCode?: string) => Promise<{ requiresMfa: boolean }>;
  logout: () => Promise<void>;
  setTokens: (accessToken: string, refreshToken: string) => void;
  loadUser: () => Promise<void>;
  updateUser: (user: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,

      login: async (email, password, mfaCode) => {
        set({ isLoading: true });
        
        try {
          const { data } = await api.post("/auth/login", {
            email,
            password,
            mfa_code: mfaCode,
          });
          
          // Se requer MFA
          if (data.requires_mfa) {
            set({ isLoading: false });
            return { requiresMfa: true };
          }
          
          // Login completo
          set({
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
            user: data.user,
            isAuthenticated: true,
            isLoading: false,
          });
          
          return { requiresMfa: false };
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      logout: async () => {
        try {
          await api.post("/auth/logout");
        } catch {
          // Ignorar erro de logout
        }
        
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        });
      },

      setTokens: (accessToken, refreshToken) => {
        set({ accessToken, refreshToken, isAuthenticated: true });
      },

      loadUser: async () => {
        const { accessToken } = get();
        if (!accessToken) return;
        
        try {
          const { data } = await api.get("/auth/me");
          set({ user: data, isAuthenticated: true });
        } catch {
          set({
            user: null,
            accessToken: null,
            refreshToken: null,
            isAuthenticated: false,
          });
        }
      },

      updateUser: (userData) => {
        const { user } = get();
        if (user) {
          set({ user: { ...user, ...userData } });
        }
      },
    }),
    {
      name: "vibeponto-auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
