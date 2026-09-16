/**
 * Serviço de API para Benefícios
 */

import api from "@/lib/api";
import { PaginatedResponse } from "./usuarios";

// Tipos
export type TipoBeneficio = 
  | "vale_transporte"
  | "vale_alimentacao"
  | "vale_refeicao"
  | "plano_saude"
  | "plano_odontologico"
  | "seguro_vida"
  | "auxilio_creche"
  | "auxilio_educacao"
  | "gympass"
  | "outros";

export interface Beneficio {
  id: string;
  tenant_id: string;
  nome: string;
  tipo: TipoBeneficio;
  descricao?: string;
  valor?: number;
  valor_padrao?: number;
  valor_desconto?: number;
  percentual_empresa: number;
  total_atribuicoes?: number;
  ativo: boolean;
  created_at: string;
  updated_at: string;
}

export interface BeneficioCreate {
  nome: string;
  tipo: TipoBeneficio;
  descricao?: string;
  valor?: number;
  valor_padrao?: number;
  valor_desconto?: number;
  percentual_empresa?: number;
}

export interface BeneficioUpdate {
  nome?: string;
  descricao?: string;
  valor?: number;
  valor_padrao?: number;
  valor_desconto?: number;
  percentual_empresa?: number;
  ativo?: boolean;
}

export interface BeneficioUsuario {
  id: string;
  beneficio_id: string;
  usuario_id: string;
  data_inicio: string;
  data_fim?: string;
  valor_personalizado?: number;
  ativo: boolean;
  created_at: string;
  beneficio?: Beneficio;
  usuario?: {
    id: string;
    nome: string;
    matricula: string;
    foto_url?: string;
  };
}

export type Atribuicao = BeneficioUsuario & {
  valor?: number;
};

export interface AtribuirBeneficioParams {
  beneficio_id: string;
  usuario_id: string;
  data_inicio?: string;
  data_fim?: string;
  valor?: number;
  valor_personalizado?: number;
}

export interface ListBeneficiosParams {
  page?: number;
  per_page?: number;
  tipo?: TipoBeneficio;
  ativo?: boolean;
  q?: string;
}

// Funções de API
export const beneficiosService = {
  /**
   * Listar benefícios
   */
  async list(params: ListBeneficiosParams = {}): Promise<PaginatedResponse<Beneficio>> {
    const { data } = await api.get("/beneficios", { params });
    return data;
  },

  async listAtribuicoes(params: { page?: number; per_page?: number } = {}): Promise<PaginatedResponse<Atribuicao>> {
    const { data } = await api.get("/beneficios/atribuicoes", { params });
    return data;
  },

  /**
   * Buscar benefício por ID
   */
  async get(id: string): Promise<Beneficio> {
    const { data } = await api.get(`/beneficios/${id}`);
    return data;
  },

  /**
   * Criar novo benefício
   */
  async create(beneficio: BeneficioCreate): Promise<Beneficio> {
    const { data } = await api.post("/beneficios", beneficio);
    return data;
  },

  /**
   * Atualizar benefício
   */
  async update(id: string, beneficio: BeneficioUpdate): Promise<Beneficio> {
    const { data } = await api.patch(`/beneficios/${id}`, beneficio);
    return data;
  },

  /**
   * Excluir benefício
   */
  async delete(id: string): Promise<void> {
    await api.delete(`/beneficios/${id}`);
  },

  /**
   * Atribuir benefício a usuário
   */
  async atribuir(params: AtribuirBeneficioParams): Promise<BeneficioUsuario> {
    const { data } = await api.post("/beneficios/atribuir", params);
    return data;
  },

  /**
   * Remover benefício de usuário
   */
  async removerAtribuicao(id: string): Promise<void> {
    await api.delete(`/beneficios/atribuicao/${id}`);
  },

  /**
   * Listar benefícios de um usuário
   */
  async listByUsuario(usuarioId: string): Promise<BeneficioUsuario[]> {
    const { data } = await api.get(`/beneficios/usuario/${usuarioId}`);
    return data;
  },

  /**
   * Meus benefícios
   */
  async meusBeneficios(): Promise<BeneficioUsuario[]> {
    const { data } = await api.get("/beneficios/meus");
    return data;
  },

  /**
   * Listar usuários com um benefício
   */
  async listUsuariosByBeneficio(beneficioId: string): Promise<BeneficioUsuario[]> {
    const { data } = await api.get(`/beneficios/${beneficioId}/usuarios`);
    return data;
  },
};

export default beneficiosService;
