/**
 * Serviço de API para Equipes
 */

import api from "@/lib/api";
import { PaginatedResponse, Usuario } from "./usuarios";

// Tipos
export interface Equipe {
  id: string;
  tenant_id: string;
  nome: string;
  descricao?: string;
  gestor_id?: string;
  ativa: boolean;
  cor?: string;
  created_at: string;
  updated_at: string;
}

export interface EquipeWithMembers extends Equipe {
  gestor?: {
    id: string;
    nome: string;
    email: string;
  };
  membros: {
    id: string;
    nome: string;
    email: string;
    matricula: string;
    papel: string;
    status: string;
  }[];
  total_membros: number;
}

export interface EquipeCreate {
  nome: string;
  descricao?: string;
  gestor_id?: string;
  cor?: string;
}

export interface EquipeUpdate {
  nome?: string;
  descricao?: string;
  gestor_id?: string;
  ativa?: boolean;
  cor?: string;
}

export interface ListEquipesParams {
  page?: number;
  per_page?: number;
  ativa?: boolean;
  q?: string;
}

// Funções de API
export const equipesService = {
  /**
   * Listar equipes com paginação e filtros
   */
  async list(params: ListEquipesParams = {}): Promise<PaginatedResponse<Equipe>> {
    const { data } = await api.get("/equipes", { params });
    return data;
  },

  /**
   * Buscar equipe por ID (com membros)
   */
  async get(id: string): Promise<EquipeWithMembers> {
    const { data } = await api.get(`/equipes/${id}`);
    return data;
  },

  /**
   * Criar nova equipe
   */
  async create(equipe: EquipeCreate): Promise<Equipe> {
    const { data } = await api.post("/equipes", equipe);
    return data;
  },

  /**
   * Atualizar equipe
   */
  async update(id: string, equipe: EquipeUpdate): Promise<Equipe> {
    const { data } = await api.patch(`/equipes/${id}`, equipe);
    return data;
  },

  /**
   * Excluir equipe
   */
  async delete(id: string): Promise<void> {
    await api.delete(`/equipes/${id}`);
  },

  /**
   * Adicionar membro à equipe
   */
  async addMember(equipeId: string, usuarioId: string): Promise<void> {
    await api.post(`/equipes/${equipeId}/membros`, { usuario_id: usuarioId });
  },

  /**
   * Remover membro da equipe
   */
  async removeMember(equipeId: string, usuarioId: string): Promise<void> {
    await api.delete(`/equipes/${equipeId}/membros/${usuarioId}`);
  },

  /**
   * Listar membros de uma equipe
   */
  async listMembers(equipeId: string): Promise<Usuario[]> {
    const { data } = await api.get(`/equipes/${equipeId}/membros`);
    return data;
  },
};

export default equipesService;
