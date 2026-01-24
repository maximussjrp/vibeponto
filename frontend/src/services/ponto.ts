/**
 * Serviço de API para Marcações de Ponto
 */

import api from "@/lib/api";
import { PaginatedResponse } from "./usuarios";

// Tipos
export interface Marcacao {
  id: string;
  usuario_id: string;
  tenant_id: string;
  tipo: "entrada" | "saida" | "intervalo_inicio" | "intervalo_fim";
  timestamp: string;
  latitude?: number;
  longitude?: number;
  endereco?: string;
  dentro_perimetro?: boolean;
  perimetro_id?: string;
  foto_url?: string;
  ip_address?: string;
  device_id?: string;
  device_info?: string;
  status: "pendente" | "aprovado" | "rejeitado" | "corrigido";
  observacao?: string;
  offline_sync: boolean;
  offline_timestamp?: string;
  created_at: string;
  updated_at: string;
  usuario?: {
    id: string;
    nome: string;
    matricula: string;
  };
}

export interface MarcacaoCreate {
  tipo: "entrada" | "saida" | "intervalo_inicio" | "intervalo_fim";
  latitude?: number;
  longitude?: number;
  foto_base64?: string;
  device_id?: string;
  device_info?: string;
  observacao?: string;
  offline?: boolean;
  offline_timestamp?: string;
}

export interface CorrecaoRequest {
  marcacao_id: string;
  novo_timestamp: string;
  motivo: string;
}

export interface Correcao {
  id: string;
  marcacao_id: string;
  solicitante_id: string;
  aprovador_id?: string;
  timestamp_original: string;
  timestamp_novo: string;
  motivo: string;
  status: "pendente" | "aprovado" | "rejeitado";
  observacao_aprovador?: string;
  created_at: string;
  updated_at: string;
}

export interface Comprovante {
  usuario: string;
  matricula: string;
  data: string;
  marcacoes: {
    tipo: string;
    horario: string;
    status: string;
  }[];
  total_horas: string;
}

export interface ListMarcacoesParams {
  page?: number;
  per_page?: number;
  usuario_id?: string;
  data_inicio?: string;
  data_fim?: string;
  status?: string;
  tipo?: string;
}

export interface ListCorrecoesParams {
  page?: number;
  per_page?: number;
  status?: string;
}

// Funções de API
export const pontoService = {
  /**
   * Registrar nova marcação
   */
  async registrar(marcacao: MarcacaoCreate): Promise<Marcacao> {
    const { data } = await api.post("/ponto/marcacoes", marcacao);
    return data;
  },

  /**
   * Listar marcações com paginação e filtros
   */
  async listMarcacoes(params: ListMarcacoesParams = {}): Promise<PaginatedResponse<Marcacao>> {
    const { data } = await api.get("/ponto/marcacoes", { params });
    return data;
  },

  /**
   * Buscar marcação por ID
   */
  async getMarcacao(id: string): Promise<Marcacao> {
    const { data } = await api.get(`/ponto/marcacoes/${id}`);
    return data;
  },

  /**
   * Minhas marcações do dia
   */
  async minhasMarcacoesHoje(): Promise<Marcacao[]> {
    const { data } = await api.get("/ponto/minhas-marcacoes/hoje");
    return data;
  },

  /**
   * Solicitar correção de marcação
   */
  async solicitarCorrecao(correcao: CorrecaoRequest): Promise<Correcao> {
    const { data } = await api.post("/ponto/correcoes", correcao);
    return data;
  },

  /**
   * Listar correções pendentes
   */
  async listCorrecoes(params: ListCorrecoesParams = {}): Promise<PaginatedResponse<Correcao>> {
    const { data } = await api.get("/ponto/correcoes", { params });
    return data;
  },

  /**
   * Aprovar correção
   */
  async aprovarCorrecao(id: string, observacao?: string): Promise<Correcao> {
    const { data } = await api.post(`/ponto/correcoes/${id}/aprovar`, { observacao });
    return data;
  },

  /**
   * Rejeitar correção
   */
  async rejeitarCorrecao(id: string, observacao: string): Promise<Correcao> {
    const { data } = await api.post(`/ponto/correcoes/${id}/rejeitar`, { observacao });
    return data;
  },

  /**
   * Gerar comprovante de ponto
   */
  async gerarComprovante(usuarioId: string, data: string): Promise<Comprovante> {
    const response = await api.get(`/ponto/comprovante/${usuarioId}`, {
      params: { data },
    });
    return response.data;
  },

  /**
   * Sincronizar marcações offline
   */
  async syncOffline(marcacoes: MarcacaoCreate[]): Promise<{ sincronizadas: number; erros: number }> {
    const { data } = await api.post("/ponto/sync-offline", { marcacoes });
    return data;
  },
};

export default pontoService;
