import api from "@/lib/api";

export interface RegisterTenantData {
  // Dados da empresa
  empresa_nome: string;
  empresa_cnpj: string;
  empresa_email: string;
  empresa_telefone?: string;
  
  // Dados do admin
  admin_nome: string;
  admin_email: string;
  admin_senha: string;
  
  // Plano
  plano: "starter" | "professional" | "enterprise";
}

export interface RegisterTenantResponse {
  tenant_id: string;
  tenant_slug: string;
  admin_id: string;
  message: string;
}

export const authService = {
  async registerTenant(data: RegisterTenantData): Promise<RegisterTenantResponse> {
    const response = await api.post("/auth/register-tenant", data);
    return response.data;
  },

  async checkSlugAvailability(slug: string): Promise<{ available: boolean }> {
    const response = await api.get(`/auth/check-slug/${slug}`);
    return response.data;
  },

  async checkCnpjAvailability(cnpj: string): Promise<{ available: boolean; empresa_nome?: string }> {
    const response = await api.get(`/auth/check-cnpj/${cnpj}`);
    return response.data;
  },

  async requestPasswordReset(email: string): Promise<{ message: string }> {
    const response = await api.post("/auth/forgot-password", { email });
    return response.data;
  },

  async resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
    const response = await api.post("/auth/reset-password", { token, new_password: newPassword });
    return response.data;
  },
};
