/**
 * Serviço de API para Marcações de Ponto
 */

import api from "@/lib/api";
import { toFiniteNumber } from "@/lib/utils";
import { PaginatedResponse } from "./usuarios";

// Tipos
export interface Marcacao {
  id: string;
  usuario_id: string;
  tenant_id: string;
  tipo: "entrada" | "saida" | "intervalo_inicio" | "intervalo_fim";
  timestamp: string;
  timestamp_local?: string;
  data_hora: string;
  latitude?: number;
  longitude?: number;
  endereco?: string;
  dentro_perimetro?: boolean;
  perimetro_id?: string;
  foto_url?: string;
  ip_address?: string;
  device_id?: string;
  device_info?: string;
  dispositivo?: string;
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
    foto_url?: string;
    foto_base_url?: string;
  };
}

export interface MarcacaoCreate {
  tipo: "entrada" | "saida" | "intervalo_inicio" | "intervalo_fim";
  latitude?: number;
  longitude?: number;
  foto_base64?: string;
  device_id?: string;
  device_info?: string;
  dispositivo?: string;
  observacao?: string;
  offline?: boolean;
  offline_timestamp?: string;
}

export type CorrecaoStatus = "pendente" | "aprovada" | "rejeitada";

export interface CorrecaoRequest {
  marcacao_id?: string;
  usuario_id?: string;
  tipo_marcacao?: string;
  novo_timestamp?: string;
  motivo?: string;
  data_hora_original?: string;
  data_hora_corrigida?: string;
  justificativa?: string;
}

export type CorrecaoCreate = CorrecaoRequest;

export interface Correcao {
  id: string;
  marcacao_id?: string;
  solicitante_id?: string;
  usuario_id?: string;
  aprovador_id?: string;
  tipo_marcacao: string;
  timestamp_original?: string;
  timestamp_novo?: string;
  data_hora_original?: string;
  data_hora_corrigida: string;
  motivo?: string;
  justificativa: string;
  status: CorrecaoStatus;
  observacao_aprovador?: string;
  created_at: string;
  updated_at: string;
  usuario?: {
    id: string;
    nome: string;
    matricula?: string;
    foto_url?: string;
    foto_base_url?: string;
  };
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
  q?: string;
}

export interface ListCorrecoesParams {
  page?: number;
  per_page?: number;
  status?: string;
}


function normalizeMarcacao(marcacao: Marcacao): Marcacao {
  return {
    ...marcacao,
    data_hora: marcacao.data_hora || marcacao.timestamp_local || marcacao.timestamp || marcacao.created_at,
    latitude: toFiniteNumber(marcacao.latitude),
    longitude: toFiniteNumber(marcacao.longitude),
    dispositivo: marcacao.dispositivo || marcacao.device_info || marcacao.device_id || "Web",
    usuario: marcacao.usuario
      ? {
          ...marcacao.usuario,
          foto_url: marcacao.usuario.foto_url || marcacao.usuario.foto_base_url,
        }
      : marcacao.usuario,
  };
}

function normalizeMarcacaoPage(response: PaginatedResponse<Marcacao>): PaginatedResponse<Marcacao> {
  return {
    ...response,
    items: response.items.map(normalizeMarcacao),
  };
}


function normalizeCorrecao(correcao: Correcao): Correcao {
  const statusMap: Record<string, CorrecaoStatus> = {
    pendente: "pendente",
    aprovado: "aprovada",
    aprovada: "aprovada",
    rejeitado: "rejeitada",
    rejeitada: "rejeitada",
  };
  return {
    ...correcao,
    tipo_marcacao: correcao.tipo_marcacao || "entrada",
    data_hora_original: correcao.data_hora_original || correcao.timestamp_original,
    data_hora_corrigida: correcao.data_hora_corrigida || correcao.timestamp_novo || correcao.created_at,
    justificativa: correcao.justificativa || correcao.motivo || "-",
    status: statusMap[correcao.status] || "pendente",
    usuario: correcao.usuario
      ? {
          ...correcao.usuario,
          foto_url: correcao.usuario.foto_url || correcao.usuario.foto_base_url,
        }
      : correcao.usuario,
  };
}

function normalizeCorrecaoPage(response: PaginatedResponse<Correcao>): PaginatedResponse<Correcao> {
  return {
    ...response,
    items: response.items.map(normalizeCorrecao),
  };
}

// Funções de API
export const pontoService = {
  /**
   * Registrar nova marcação
   */
  async registrar(marcacao: MarcacaoCreate): Promise<Marcacao> {
    const { data } = await api.post("/ponto/marcacoes", marcacao);
    return normalizeMarcacao(data);
  },

  /**
   * Listar marcações com paginação e filtros
   */
  async listMarcacoes(params: ListMarcacoesParams = {}): Promise<PaginatedResponse<Marcacao>> {
    const { data } = await api.get("/ponto/marcacoes", { params });
    return normalizeMarcacaoPage(data);
  },

  /**
   * Buscar marcação por ID
   */
  async getMarcacao(id: string): Promise<Marcacao> {
    const { data } = await api.get(`/ponto/marcacoes/${id}`);
    return normalizeMarcacao(data);
  },

  /**
   * Minhas marcações do dia
   */
  async minhasMarcacoesHoje(): Promise<Marcacao[]> {
    const { data } = await api.get("/ponto/minhas-marcacoes/hoje");
    return data.map(normalizeMarcacao);
  },

  /**
   * Solicitar correção de marcação
   */
  async solicitarCorrecao(correcao: CorrecaoRequest): Promise<Correcao> {
    const payload = {
      ...correcao,
      marcacao_id: correcao.marcacao_id || "",
      novo_timestamp: correcao.novo_timestamp || correcao.data_hora_corrigida,
      motivo: correcao.motivo || correcao.justificativa,
    };
    const { data } = await api.post("/ponto/correcoes", payload);
    return normalizeCorrecao(data);
  },

  async createCorrecao(correcao: CorrecaoCreate): Promise<Correcao> {
    return this.solicitarCorrecao(correcao);
  },

  /**
   * Listar correções pendentes
   */
  async listCorrecoes(params: ListCorrecoesParams = {}): Promise<PaginatedResponse<Correcao>> {
    const apiParams = {
      ...params,
      status: params.status === "aprovada" ? "aprovado" : params.status === "rejeitada" ? "rejeitado" : params.status,
    };
    const { data } = await api.get("/ponto/correcoes", { params: apiParams });
    return normalizeCorrecaoPage(data);
  },

  /**
   * Aprovar correção
   */
  async aprovarCorrecao(id: string, observacao?: string): Promise<Correcao> {
    const { data } = await api.post(`/ponto/correcoes/${id}/aprovar`, { observacao });
    return normalizeCorrecao(data);
  },

  /**
   * Rejeitar correção
   */
  async rejeitarCorrecao(id: string, observacao: string): Promise<Correcao> {
    const { data } = await api.post(`/ponto/correcoes/${id}/rejeitar`, { observacao });
    return normalizeCorrecao(data);
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
