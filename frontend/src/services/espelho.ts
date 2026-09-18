/**
 * Serviço de API para Espelho de Ponto
 */

import api from "@/lib/api";

// Tipos
export interface DiaEspelho {
  data: string;
  dia_semana: string;
  marcacoes: {
    tipo?: string;
    evento?: string;
    horario?: string;
    timestamp_local: string;
    status?: string;
  }[];
  horas_trabalhadas: string;
  horas_extras: string;
  horas_faltantes: string;
  observacao?: string;
  observacoes?: string[];
  feriado?: string;
  afastamento?: string;
}

export interface EspelhoPonto {
  usuario: {
    id: string;
    nome: string;
    matricula: string;
    cargo?: string;
    departamento?: string;
  };
  periodo: {
    mes: number;
    ano: number;
    data_inicio: string;
    data_fim: string;
  };
  resumo: {
    dias_trabalhados: number;
    horas_trabalhadas: string;
    horas_extras: string;
    horas_faltantes: string;
    banco_horas: string;
    faltas: number;
    atrasos: number;
    horas_noturnas: string;
  };
  dias: DiaEspelho[];
  usuario_nome?: string;
  usuario_matricula?: string;
  total_horas_trabalhadas?: string;
  total_horas_extras?: string;
  total_horas_falta?: string;
  total_dias_trabalhados?: number;
  assinatura_funcionario?: {
    data: string;
    ip?: string;
  };
  assinatura_gestor?: {
    data: string;
    nome: string;
  };
}

export interface EspelhoParams {
  usuario_id: string;
  mes: number;
  ano: number;
}

export interface EspelhoFilters {
  mes: number;
  ano: number;
  usuario_id?: string;
  equipe_id?: string;
}

export interface EspelhoListResponse {
  items: EspelhoPonto[];
  total: number;
}

// Funções auxiliares
function getMonthPeriod(mes: number, ano: number) {
  const inicio = new Date(ano, mes - 1, 1);
  const fim = new Date(ano, mes, 0, 23, 59, 59);
  return {
    periodo_inicio: inicio.toISOString(),
    periodo_fim: fim.toISOString(),
  };
}


function normalizeEspelho(espelho: EspelhoPonto): EspelhoPonto {
  return {
    ...espelho,
    usuario_nome: espelho.usuario_nome || espelho.usuario?.nome,
    usuario_matricula: espelho.usuario_matricula || espelho.usuario?.matricula,
    total_horas_trabalhadas: espelho.total_horas_trabalhadas || espelho.resumo?.horas_trabalhadas,
    total_horas_extras: espelho.total_horas_extras || espelho.resumo?.horas_extras,
    total_horas_falta: espelho.total_horas_falta || espelho.resumo?.horas_faltantes,
    total_dias_trabalhados: espelho.total_dias_trabalhados ?? espelho.resumo?.dias_trabalhados,
    dias: espelho.dias.map((dia) => ({
      ...dia,
      observacoes: dia.observacoes || (dia.observacao ? [dia.observacao] : []),
    })),
  };
}

// Funções de API
export const espelhoService = {
  /**
   * Buscar espelho de ponto de um usuário
   */
  async get(params: EspelhoParams): Promise<EspelhoPonto> {
    const { mes, ano, usuario_id } = params;
    const periodo = getMonthPeriod(mes, ano);
    const { data } = await api.get("/ponto/espelho", { 
      params: { usuario_id, ...periodo } 
    });
    return normalizeEspelho(data);
  },

  /**
   * Buscar lista de espelhos com filtros
   */
  async getEspelho(filters: EspelhoFilters): Promise<EspelhoListResponse> {
    const { mes, ano, usuario_id, equipe_id } = filters;
    const periodo = getMonthPeriod(mes, ano);
    const { data } = await api.get("/ponto/espelho", { 
      params: { usuario_id, equipe_id, ...periodo } 
    });
    // O backend retorna um único espelho, então encapsulamos
    return {
      items: data ? [normalizeEspelho(data)] : [],
      total: data ? 1 : 0,
    };
  },

  /**
   * Exportar espelho para PDF com filtros
   */
  async exportPdf(filters: EspelhoFilters): Promise<Blob> {
    const { mes, ano, usuario_id } = filters;
    const periodo = getMonthPeriod(mes, ano);
    const response = await api.get("/ponto/espelho/pdf", {
      params: { usuario_id, ...periodo },
      responseType: "blob",
    });
    return response.data;
  },

  /**
   * Exportar espelho para Excel com filtros
   */
  async exportExcel(filters: EspelhoFilters): Promise<Blob> {
    const { mes, ano, usuario_id, equipe_id } = filters;
    const periodo = getMonthPeriod(mes, ano);
    const response = await api.get("/ponto/espelho/excel", {
      params: { usuario_id, equipe_id, ...periodo },
      responseType: "blob",
    });
    return response.data;
  },

  /**
   * Meu espelho do mês atual
   */
  async meuEspelho(mes?: number, ano?: number): Promise<EspelhoPonto> {
    const { data } = await api.get("/espelho/meu", { params: { mes, ano } });
    return normalizeEspelho(data);
  },

  /**
   * Assinar espelho (funcionário)
   */
  async assinar(usuarioId: string, mes: number, ano: number): Promise<void> {
    await api.post("/espelho/assinar", { usuario_id: usuarioId, mes, ano });
  },

  /**
   * Aprovar espelho (gestor)
   */
  async aprovar(usuarioId: string, mes: number, ano: number): Promise<void> {
    await api.post("/espelho/aprovar", { usuario_id: usuarioId, mes, ano });
  },

  /**
   * Exportar espelho para PDF
   */
  async exportarPDF(usuarioId: string, mes: number, ano: number): Promise<Blob> {
    const response = await api.get("/espelho/exportar/pdf", {
      params: { usuario_id: usuarioId, mes, ano },
      responseType: "blob",
    });
    return response.data;
  },

  /**
   * Exportar espelho para Excel
   */
  async exportarExcel(usuarioId: string, mes: number, ano: number): Promise<Blob> {
    const response = await api.get("/espelho/exportar/excel", {
      params: { usuario_id: usuarioId, mes, ano },
      responseType: "blob",
    });
    return response.data;
  },

  /**
   * Enviar espelho por email
   */
  async enviarEmail(usuarioId: string, mes: number, ano: number): Promise<void> {
    await api.post("/espelho/enviar-email", { usuario_id: usuarioId, mes, ano });
  },

  /**
   * Exportar AEJ (Arquivo Eletrônico de Jornada)
   */
  async exportarAEJ(mes: number, ano: number): Promise<Blob> {
    const response = await api.get("/espelho/exportar/aej", {
      params: { mes, ano },
      responseType: "blob",
    });
    return response.data;
  },
};

export default espelhoService;
