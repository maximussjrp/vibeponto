/**
 * Serviço de API para Configurações e Empresa (Vibe Ponto)
 */

import api from "@/lib/api";

// Tipos de Endereço Estruturado
export interface Endereco {
  cep?: string;
  logradouro?: string;
  numero?: string;
  complemento?: string;
  bairro?: string;
  municipio?: string;
  cidade?: string;
  uf?: string;
  estado?: string;
  pais?: string;
}

// Tipos Corporativos do Tenant
export interface Tenant {
  id: string;
  nome: string;
  cnpj: string;
  razao_social?: string;
  endereco?: Endereco | string;
  telefone?: string;
  email?: string;
  slug?: string;
  plano?: "starter" | "professional" | "enterprise";
  ativo: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface TenantUpdate {
  nome?: string;
  razao_social?: string;
  email?: string;
  telefone?: string;
  endereco?: Endereco | string;
}

// Seções de Configurações Canônicas
export interface ConfiguracoesPonto {
  tolerancia_minutos: number;
  intervalo_minimo: number;  // minutos
  jornada_diaria: number;     // horas
  jornada_semanal: number;    // horas
  hora_extra_automatica: boolean;
  banco_horas_ativo: boolean;
  banco_horas_limite: number; // horas
  exigir_foto: boolean;
  exigir_geolocalizacao: boolean;
  permitir_offline: boolean;
  notificar_atraso: boolean;
  notificar_hora_extra: boolean;
}

export interface ConfiguracoesNotificacoes {
  email_ativo: boolean;
  push_ativo: boolean;
  notificar_marcacao: boolean;
  notificar_aprovacao: boolean;
  notificar_documento: boolean;
  notificar_alerta: boolean;
  horario_lembrete_entrada?: string;
  horario_lembrete_saida?: string;
}

export interface ConfiguracoesSeguranca {
  mfa_obrigatorio: boolean;
  sessao_unica: boolean;
  tempo_sessao: number;  // minutos
  tentativas_login: number;
  bloquear_dispositivo: boolean;
  ips_permitidos?: string[];
}

export interface ConfiguracoesIntegracoes {
  webhook_url?: string;
  webhook_secret_configurado?: boolean;
  webhook_secret?: string; // apenas envio (write-only)
  api_folha_ativa: boolean;
  api_folha_url?: string;
  api_folha_token_configurado?: boolean;
  api_folha_token?: string; // apenas envio (write-only)
}

// Funções de API Corporativa
export const empresaService = {
  /**
   * Buscar dados corporativos da empresa (tenant)
   */
  async get(): Promise<Tenant> {
    const { data } = await api.get("/tenant");
    return data;
  },

  async getTenant(): Promise<Tenant> {
    return this.get();
  },

  /**
   * Atualizar dados corporativos da empresa
   */
  async update(tenant: TenantUpdate): Promise<Tenant> {
    const { data } = await api.patch("/tenant", tenant);
    return data;
  },

  async updateTenant(tenant: TenantUpdate): Promise<Tenant> {
    return this.update(tenant);
  },

  /**
   * Estatísticas da empresa
   */
  async estatisticas(): Promise<{
    total_usuarios: number;
    usuarios_ativos: number;
    total_equipes: number;
    marcacoes_hoje: number;
    alertas_pendentes: number;
  }> {
    const { data } = await api.get("/tenant/estatisticas");
    return data;
  },
};

// Funções de API de Configurações Canônicas
export const configuracoesService = {
  /**
   * Buscar configurações de ponto
   */
  async getPonto(): Promise<ConfiguracoesPonto> {
    const { data } = await api.get("/configuracoes/ponto");
    return data;
  },

  /**
   * Atualizar configurações de ponto
   */
  async updatePonto(config: Partial<ConfiguracoesPonto>): Promise<ConfiguracoesPonto> {
    const { data } = await api.patch("/configuracoes/ponto", config);
    return data;
  },

  /**
   * Buscar configurações de notificações
   */
  async getNotificacoes(): Promise<ConfiguracoesNotificacoes> {
    const { data } = await api.get("/configuracoes/notificacoes");
    return data;
  },

  /**
   * Atualizar configurações de notificações
   */
  async updateNotificacoes(config: Partial<ConfiguracoesNotificacoes>): Promise<ConfiguracoesNotificacoes> {
    const { data } = await api.patch("/configuracoes/notificacoes", config);
    return data;
  },

  /**
   * Buscar configurações de segurança
   */
  async getSeguranca(): Promise<ConfiguracoesSeguranca> {
    const { data } = await api.get("/configuracoes/seguranca");
    return data;
  },

  /**
   * Atualizar configurações de segurança
   */
  async updateSeguranca(config: Partial<ConfiguracoesSeguranca>): Promise<ConfiguracoesSeguranca> {
    const { data } = await api.patch("/configuracoes/seguranca", config);
    return data;
  },

  /**
   * Buscar configurações de integrações (sem segredos)
   */
  async getIntegracoes(): Promise<ConfiguracoesIntegracoes> {
    const { data } = await api.get("/configuracoes/integracoes");
    return data;
  },

  /**
   * Atualizar configurações de integrações
   */
  async updateIntegracoes(config: Partial<ConfiguracoesIntegracoes>): Promise<ConfiguracoesIntegracoes> {
    const { data } = await api.patch("/configuracoes/integracoes", config);
    return data;
  },

  /**
   * Testar webhook (com validação SSRF no backend)
   */
  async testarWebhook(): Promise<{ sucesso: boolean; mensagem: string }> {
    const { data } = await api.post("/configuracoes/integracoes/testar-webhook");
    return data;
  },
};

const empresaApi = { empresaService, configuracoesService };

export default empresaApi;
