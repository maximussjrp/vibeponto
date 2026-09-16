/**
 * Serviço de API para Auditoria
 */

import api from "@/lib/api";
import { PaginatedResponse } from "./usuarios";

// Tipos
export type TipoAlerta = 
  | "marcacao_fora_local"
  | "horario_incomum"
  | "jornada_excedida"
  | "marcacao_duplicada"
  | "intervalo_curto"
  | "ausencia_marcacao"
  | "dispositivo_diferente"
  | "ip_suspeito"
  | "velocidade_impossivel"
  | "padrao_anormal";

export type SeveridadeAlerta = "baixa" | "media" | "alta" | "critica";

export type StatusAlerta = "pendente" | "revisado" | "ignorado" | "resolvido";

export type AlertaTipo =
  | "fora_perimetro"
  | "horario_invalido"
  | "dispositivo_nao_autorizado"
  | "multiplas_marcacoes"
  | "localizacao_suspeita"
  | "fraude_potencial";

export type AlertaStatus = "novo" | "em_analise" | "resolvido" | "ignorado";

export interface Auditoria {
  id: string;
  tenant_id: string;
  usuario_id: string;
  marcacao_id?: string;
  tipo: TipoAlerta;
  severidade: SeveridadeAlerta;
  status: StatusAlerta;
  descricao: string;
  detalhes?: Record<string, unknown>;
  revisor_id?: string;
  revisado_em?: string;
  decisao?: "ignorado" | "advertencia" | "corrigido" | "escalado";
  observacao_revisor?: string;
  created_at: string;
  updated_at: string;
  usuario?: {
    id: string;
    nome: string;
    matricula: string;
  };
  marcacao?: {
    id: string;
    tipo: string;
    timestamp: string;
  };
}

export interface AlertaAuditoria extends Omit<Auditoria, "tipo" | "status" | "usuario"> {
  tipo: AlertaTipo;
  status: AlertaStatus;
  data_hora: string;
  usuario?: {
    id: string;
    nome: string;
    matricula: string;
    foto_url?: string;
  };
}

export interface ListAlertasParams {
  page?: number;
  per_page?: number;
  tipo?: AlertaTipo;
  status?: AlertaStatus;
  q?: string;
}

export interface AlertaStats {
  novos: number;
  em_analise: number;
  resolvidos_mes: number;
  total: number;
}

export type AlertasResponse = PaginatedResponse<AlertaAuditoria> & {
  total_pages: number;
};

export interface AuditoriaRevisao {
  decisao: "ignorado" | "advertencia" | "corrigido" | "escalado";
  observacao?: string;
}

export interface ListAuditoriaParams {
  page?: number;
  per_page?: number;
  tipo?: TipoAlerta;
  severidade?: SeveridadeAlerta;
  status?: StatusAlerta;
  usuario_id?: string;
  data_inicio?: string;
  data_fim?: string;
}

export interface EstatisticasAuditoria {
  total: number;
  por_tipo: Record<TipoAlerta, number>;
  por_severidade: Record<SeveridadeAlerta, number>;
  por_status: Record<StatusAlerta, number>;
  tendencia_semanal: {
    semana: string;
    total: number;
  }[];
}

// Funções de API
export const auditoriaService = {
  /**
   * Listar alertas de auditoria
   */
  async list(params: ListAuditoriaParams = {}): Promise<PaginatedResponse<Auditoria>> {
    const { data } = await api.get("/ponto/auditoria", { params });
    return data;
  },

  async listAlertas(params: ListAlertasParams = {}): Promise<AlertasResponse> {
    const { data } = await api.get("/ponto/auditoria", { params });
    return {
      ...data,
      total_pages: data.total_pages ?? data.pages ?? Math.ceil((data.total || 0) / (data.per_page || 1)),
    };
  },

  /**
   * Buscar alerta por ID
   */
  async get(id: string): Promise<Auditoria> {
    const { data } = await api.get(`/ponto/auditoria/${id}`);
    return data;
  },

  /**
   * Revisar alerta
   */
  async revisar(id: string, revisao: AuditoriaRevisao): Promise<Auditoria> {
    const { data } = await api.post(`/ponto/auditoria/${id}/revisar`, revisao);
    return data;
  },

  async resolverAlerta(id: string, observacao?: string): Promise<Auditoria> {
    return this.revisar(id, { decisao: "corrigido", observacao });
  },

  async ignorarAlerta(id: string, observacao?: string): Promise<Auditoria> {
    return this.revisar(id, { decisao: "ignorado", observacao });
  },

  /**
   * Marcar como ignorado (atalho)
   */
  async ignorar(id: string, observacao?: string): Promise<Auditoria> {
    return this.revisar(id, { decisao: "ignorado", observacao });
  },

  /**
   * Marcar como resolvido (atalho)
   */
  async resolver(id: string, observacao?: string): Promise<Auditoria> {
    return this.revisar(id, { decisao: "corrigido", observacao });
  },

  /**
   * Obter estatísticas de auditoria
   */
  async estatisticas(dataInicio?: string, dataFim?: string): Promise<EstatisticasAuditoria> {
    const { data } = await api.get("/ponto/auditoria/estatisticas", {
      params: { data_inicio: dataInicio, data_fim: dataFim },
    });
    return data;
  },

  async getStats(): Promise<AlertaStats> {
    const { data } = await api.get("/ponto/auditoria/estatisticas");
    return data;
  },

  /**
   * Exportar relatório de auditoria
   */
  async exportar(params: ListAuditoriaParams, formato: "pdf" | "excel"): Promise<Blob> {
    const response = await api.get(`/ponto/auditoria/exportar/${formato}`, {
      params,
      responseType: "blob",
    });
    return response.data;
  },
};

export default auditoriaService;
