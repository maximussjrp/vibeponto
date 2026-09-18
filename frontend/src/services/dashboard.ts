/**
 * Serviço de API para Dashboard
 */

import api from "@/lib/api";

// Tipos
export interface DashboardStats {
  colaboradores: {
    total: number;
    ativos: number;
    inativos: number;
    novos_mes: number;
  };
  ponto: {
    marcacoes_hoje: number;
    pendentes_aprovacao: number;
    atrasos_hoje: number;
    faltas_hoje: number;
  };
  horas: {
    trabalhadas_mes: number;
    extras_mes: number;
    banco_horas_total: number;
  };
  auditoria: {
    alertas_pendentes: number;
    alertas_criticos: number;
    taxa_conformidade: number;
  };
}

export interface GraficoMarcacoes {
  data: string;
  entradas: number;
  saidas: number;
  atrasos: number;
}

export interface GraficoHorasExtras {
  semana: string;
  horas: number;
}

export interface GraficoDistribuicao {
  equipe: string;
  total: number;
}

export interface AtividadeRecente {
  id: string;
  tipo: "marcacao" | "aprovacao" | "alerta" | "documento" | "usuario";
  descricao: string;
  usuario: string;
  timestamp: string;
}


export interface DashboardCharts {
  weekly_presence: { name: string; presentes: number; ausentes: number }[];
  team_distribution: { name: string; value: number }[];
  hourly_distribution: { hora: string; marcacoes: number }[];
}

// Funções de API
export const dashboardService = {
  /**
   * Estatísticas gerais do dashboard
   */
  async getStats(): Promise<DashboardStats> {
    const { data } = await api.get("/dashboard/stats");
    return data;
  },

  /**
   * Gráfico de marcações dos últimos 7 dias
   */
  async getMarcacoesSemana(): Promise<GraficoMarcacoes[]> {
    const { data } = await api.get("/dashboard/graficos/marcacoes-semana");
    return data;
  },

  /**
   * Gráfico de horas extras do mês
   */
  async getHorasExtrasMes(): Promise<GraficoHorasExtras[]> {
    const { data } = await api.get("/dashboard/graficos/horas-extras-mes");
    return data;
  },

  /**
   * Distribuição de colaboradores por equipe
   */
  async getDistribuicaoEquipes(): Promise<GraficoDistribuicao[]> {
    const { data } = await api.get("/dashboard/graficos/distribuicao-equipes");
    return data;
  },


  async getCharts(): Promise<DashboardCharts> {
    const [marcacoes, equipes] = await Promise.all([
      this.getMarcacoesSemana(),
      this.getDistribuicaoEquipes(),
    ]);

    return {
      weekly_presence: marcacoes.map((item) => ({
        name: item.data,
        presentes: item.entradas,
        ausentes: Math.max(0, item.saidas - item.entradas),
      })),
      team_distribution: equipes.map((item) => ({
        name: item.equipe,
        value: item.total,
      })),
      hourly_distribution: [],
    };
  },

  /**
   * Atividades recentes
   */
  async getAtividadesRecentes(limite: number = 10): Promise<AtividadeRecente[]> {
    const { data } = await api.get("/dashboard/atividades-recentes", {
      params: { limite },
    });
    return data;
  },

  /**
   * Colaboradores presentes agora
   */
  async getColaboradoresPresentes(): Promise<{
    presentes: number;
    total: number;
    lista: { id: string; nome: string; entrada: string }[];
  }> {
    const { data } = await api.get("/dashboard/presentes");
    return data;
  },

  /**
   * Resumo do dia para gestor
   */
  async getResumoDia(): Promise<{
    data: string;
    marcacoes: number;
    pendentes: number;
    aprovados: number;
    rejeitados: number;
    alertas: number;
  }> {
    const { data } = await api.get("/dashboard/resumo-dia");
    return data;
  },
};

export default dashboardService;
