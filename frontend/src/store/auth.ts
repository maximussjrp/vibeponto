/**
 * Store de autenticacao usando Zustand.
 *
 * O refresh token fica em cookie HttpOnly emitido pelo backend. O access token
 * permanece apenas em memoria para reduzir exposicao em XSS e storage local.
 */

import { create } from "zustand";
import api, { requestNewAccessToken, setAuthHandlers } from "@/lib/api";
import { clearBrowserAuthData } from "@/lib/auth-cleanup";

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
  isAuthenticated: boolean;
  isLoading: boolean;
  initialized: boolean;

  login: (
    email: string,
    password: string,
    mfaCode?: string,
    tenantId?: string
  ) => Promise<{ requiresMfa: boolean }>;
  logout: () => Promise<void>;
  setTokens: (accessToken: string | null) => void;
  loadUser: () => Promise<void>;
  clearSession: (options?: { cleanup?: boolean; broadcast?: boolean }) => void;
  updateUser: (user: Partial<User>) => void;
}

let loadUserPromise: Promise<void> | null = null;

function broadcastLogout() {
  if (typeof window === "undefined" || !("BroadcastChannel" in window)) {
    return;
  }

  const channel = new BroadcastChannel("vibeponto-auth");
  channel.postMessage({ type: "LOGOUT" });
  channel.close();
}

export const useAuthStore = create<AuthState>()((set, get) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isLoading: false,
  initialized: false,

  login: async (email, password, mfaCode, tenantId) => {
    set({ isLoading: true });

    try {
      const { data } = await api.post("/auth/login", {
        email,
        password,
        mfa_code: mfaCode,
        tenant_id: tenantId || undefined,
      });

      if (data.requires_mfa) {
        set({ isLoading: false, initialized: true });
        return { requiresMfa: true };
      }

      await clearBrowserAuthData();

      set({
        accessToken: data.access_token,
        user: data.user,
        isAuthenticated: true,
        isLoading: false,
        initialized: true,
      });

      return { requiresMfa: false };
    } catch (error) {
      set({ isLoading: false, initialized: true });
      throw error;
    }
  },

  logout: async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // Logout local continua mesmo se a sessao no servidor ja expirou.
    }

    get().clearSession({ cleanup: true, broadcast: true });
  },

  setTokens: (accessToken) => {
    set({ accessToken, isAuthenticated: Boolean(accessToken) });
  },

  loadUser: async () => {
    if (loadUserPromise) {
      return loadUserPromise;
    }

    loadUserPromise = (async () => {
      try {
        let token = get().accessToken;
        if (!token) {
          token = await requestNewAccessToken();
          if (token) {
            set({ accessToken: token, isAuthenticated: true });
          }
        }

        if (!token) {
          set({ initialized: true, isAuthenticated: false, user: null, accessToken: null });
          return;
        }

        const { data } = await api.get("/auth/me");
        set({ user: data, isAuthenticated: true, initialized: true });
      } catch {
        set({ user: null, accessToken: null, isAuthenticated: false, initialized: true });
      } finally {
        loadUserPromise = null;
      }
    })();

    return loadUserPromise;
  },

  clearSession: (options) => {
    set({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      initialized: true,
    });

    if (options?.broadcast) {
      broadcastLogout();
    }

    if (options?.cleanup) {
      void clearBrowserAuthData();
    }
  },

  updateUser: (userData) => {
    const { user } = get();
    if (user) {
      set({ user: { ...user, ...userData } });
    }
  },
}));

setAuthHandlers({
  getAccessToken: () => useAuthStore.getState().accessToken,
  refreshAccessToken: async () => {
    const token = await requestNewAccessToken().catch(() => null);
    useAuthStore.getState().setTokens(token);
    return token;
  },
  clearAuth: () => useAuthStore.getState().clearSession({ cleanup: true, broadcast: true }),
});

if (typeof window !== "undefined" && "BroadcastChannel" in window) {
  const channel = new BroadcastChannel("vibeponto-auth");
  channel.onmessage = (event) => {
    if (event.data?.type === "LOGOUT") {
      useAuthStore.getState().clearSession({ cleanup: true });
    }
  };
}
