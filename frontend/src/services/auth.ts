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

  async getMe(): Promise<any> {
    const response = await api.get("/auth/me");
    return response.data;
  },

  async updateMe(data: { nome?: string; telefone?: string }): Promise<any> {
    const response = await api.patch("/auth/me", data);
    return response.data;
  },

  async changePassword(data: { current_password: string; new_password: string; confirm_password: string }): Promise<{ message: string }> {
    const response = await api.post("/auth/password/change", data);
    return response.data;
  },

  async requestPasswordReset(email: string, tenant_id?: string): Promise<{ message: string }> {
    const response = await api.post("/auth/password/reset", { email, tenant_id });
    return response.data;
  },

  async resetPassword(token: string, newPassword: string, confirmPassword: string): Promise<{ message: string }> {
    const response = await api.post("/auth/password/reset/confirm", {
      token,
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
    return response.data;
  },
};
