/**
 * Serviço de API para Usuários/Colaboradores
 */

import api from "@/lib/api";

// Tipos
export interface Usuario {
  id: string;
  tenant_id: string;
  nome: string;
  email: string;
  cpf?: string;
  telefone?: string;
  matricula: string;
  papel: "admin_dp" | "gestor" | "colaborador" | "auditor" | "financeiro";
  status: "active" | "inactive" | "suspended" | "pending";
  mfa_enabled: boolean;
  foto_base_url?: string;
  equipe_id?: string;
  ultimo_login?: string;
  created_at: string;
  updated_at: string;
}

export interface UsuarioCreate {
  nome: string;
  email: string;
  cpf: string;
  telefone?: string;
  matricula: string;
  password: string;
  papel?: "admin_dp" | "gestor" | "colaborador" | "auditor" | "financeiro";
  equipe_id?: string;
}

export interface UsuarioUpdate {
  nome?: string;
  telefone?: string;
  equipe_id?: string;
  papel?: "admin_dp" | "gestor" | "colaborador" | "auditor" | "financeiro";
  status?: "active" | "inactive" | "suspended";
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface ListUsuariosParams {
  page?: number;
  per_page?: number;
  status?: string;
  papel?: string;
  equipe_id?: string;
  q?: string;
}

// Funções de API
export const usuariosService = {
  /**
   * Listar usuários com paginação e filtros
   */
  async list(params: ListUsuariosParams = {}): Promise<PaginatedResponse<Usuario>> {
    const { data } = await api.get("/usuarios", { params });
    return data;
  },

  /**
   * Buscar usuário por ID
   */
  async get(id: string): Promise<Usuario> {
    const { data } = await api.get(`/usuarios/${id}`);
    return data;
  },

  /**
   * Criar novo usuário
   */
  async create(usuario: UsuarioCreate): Promise<Usuario> {
    const { data } = await api.post("/usuarios", usuario);
    return data;
  },

  /**
   * Atualizar usuário
   */
  async update(id: string, usuario: UsuarioUpdate): Promise<Usuario> {
    const { data } = await api.patch(`/usuarios/${id}`, usuario);
    return data;
  },

  /**
   * Excluir usuário
   */
  async delete(id: string): Promise<void> {
    await api.delete(`/usuarios/${id}`);
  },

  /**
   * Suspender usuário
   */
  async suspend(id: string): Promise<Usuario> {
    const { data } = await api.post(`/usuarios/${id}/suspend`);
    return data;
  },

  /**
   * Reativar usuário
   */
  async activate(id: string): Promise<Usuario> {
    const { data } = await api.post(`/usuarios/${id}/reactivate`);
    return data;
  },

  /**
   * Resetar senha (dispara token de recuperação por e-mail)
   */
  async resetPassword(id: string): Promise<{ message: string }> {
    const { data } = await api.post(`/usuarios/${id}/reset-password`);
    return data;
  },
};

export default usuariosService;
