"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";

import { getErrorMessage } from "@/lib/api";
import { empresaService, configuracoesService } from "@/services/empresa";
import type {
  Tenant,
  TenantUpdate,
  ConfiguracoesPonto,
  ConfiguracoesNotificacoes,
  ConfiguracoesSeguranca,
  ConfiguracoesIntegracoes,
  Endereco,
} from "@/services/empresa";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Building2,
  Settings,
  Clock,
  Bell,
  Shield,
  Save,
  Loader2,
  RefreshCw,
  Send,
} from "lucide-react";

// Schemas de Validação
const empresaSchema = z.object({
  nome: z.string().min(2, "Nome deve ter pelo menos 2 caracteres"),
  razao_social: z.string().optional(),
  cnpj: z.string().optional(),
  email: z.string().email("Email inválido").optional().or(z.literal("")),
  telefone: z.string().optional(),
  cep: z.string().optional(),
  logradouro: z.string().optional(),
  numero: z.string().optional(),
  complemento: z.string().optional(),
  bairro: z.string().optional(),
  cidade: z.string().optional(),
  estado: z.string().optional(),
});

const pontoSchema = z.object({
  tolerancia_minutos: z.coerce.number().min(0).max(60),
  intervalo_minimo: z.coerce.number().min(0).max(180),
  jornada_diaria: z.coerce.number().min(1).max(24),
  jornada_semanal: z.coerce.number().min(1).max(168),
  hora_extra_automatica: z.boolean(),
  banco_horas_ativo: z.boolean(),
  banco_horas_limite: z.coerce.number().min(0).max(500),
  exigir_foto: z.boolean(),
  exigir_geolocalizacao: z.boolean(),
  permitir_offline: z.boolean(),
  notificar_atraso: z.boolean(),
  notificar_hora_extra: z.boolean(),
});

const notificacoesSchema = z.object({
  email_ativo: z.boolean(),
  push_ativo: z.boolean(),
  notificar_marcacao: z.boolean(),
  notificar_aprovacao: z.boolean(),
  notificar_documento: z.boolean(),
  notificar_alerta: z.boolean(),
  horario_lembrete_entrada: z.string().optional().nullable(),
  horario_lembrete_saida: z.string().optional().nullable(),
});

const segurancaSchema = z.object({
  mfa_obrigatorio: z.boolean(),
  sessao_unica: z.boolean(),
  tempo_sessao: z.coerce.number().min(15).max(1440),
  tentativas_login: z.coerce.number().min(1).max(10),
  bloquear_dispositivo: z.boolean(),
  ips_permitidos: z.string().optional(),
});

const integracoesSchema = z.object({
  webhook_url: z.string().url("URL de webhook inválida").optional().or(z.literal("")),
  webhook_secret: z.string().optional(),
  api_folha_ativa: z.boolean(),
  api_folha_url: z.string().url("URL de API inválida").optional().or(z.literal("")),
  api_folha_token: z.string().optional(),
});

type EmpresaForm = z.infer<typeof empresaSchema>;
type PontoForm = z.infer<typeof pontoSchema>;
type NotificacoesForm = z.infer<typeof notificacoesSchema>;
type SegurancaForm = z.infer<typeof segurancaSchema>;
type IntegracoesForm = z.infer<typeof integracoesSchema>;

export default function EmpresaPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("empresa");

  // Queries Canônicas por Seção
  const { data: tenantData, isLoading: tenantLoading, refetch: refetchTenant } = useQuery({
    queryKey: ["tenant"],
    queryFn: () => empresaService.getTenant(),
  });

  const { data: pontoData, isLoading: pontoLoading, refetch: refetchPonto } = useQuery({
    queryKey: ["config-ponto"],
    queryFn: () => configuracoesService.getPonto(),
  });

  const { data: notificacoesData, isLoading: notificacoesLoading, refetch: refetchNotificacoes } = useQuery({
    queryKey: ["config-notificacoes"],
    queryFn: () => configuracoesService.getNotificacoes(),
  });

  const { data: segurancaData, isLoading: segurancaLoading, refetch: refetchSeguranca } = useQuery({
    queryKey: ["config-seguranca"],
    queryFn: () => configuracoesService.getSeguranca(),
  });

  const { data: integracoesData, isLoading: integracoesLoading, refetch: refetchIntegracoes } = useQuery({
    queryKey: ["config-integracoes"],
    queryFn: () => configuracoesService.getIntegracoes(),
  });

  // Forms Hook Form
  const empresaForm = useForm<EmpresaForm>({ resolver: zodResolver(empresaSchema) });
  const pontoForm = useForm<PontoForm>({ resolver: zodResolver(pontoSchema) });
  const notificacoesForm = useForm<NotificacoesForm>({ resolver: zodResolver(notificacoesSchema) });
  const segurancaForm = useForm<SegurancaForm>({ resolver: zodResolver(segurancaSchema) });
  const integracoesForm = useForm<IntegracoesForm>({ resolver: zodResolver(integracoesSchema) });

  // Preencher Forms ao carregar dados
  useEffect(() => {
    if (tenantData) {
      const end = (typeof tenantData.endereco === "object" ? tenantData.endereco : {}) as Endereco;
      empresaForm.reset({
        nome: tenantData.nome || "",
        razao_social: tenantData.razao_social || tenantData.nome || "",
        cnpj: tenantData.cnpj || "",
        email: tenantData.email || "",
        telefone: tenantData.telefone || "",
        cep: end?.cep || "",
        logradouro: end?.logradouro || "",
        numero: end?.numero || "",
        complemento: end?.complemento || "",
        bairro: end?.bairro || "",
        cidade: end?.municipio || end?.cidade || "",
        estado: end?.uf || end?.estado || "",
      });
    }
  }, [tenantData, empresaForm]);

  useEffect(() => {
    if (pontoData) pontoForm.reset(pontoData);
  }, [pontoData, pontoForm]);

  useEffect(() => {
    if (notificacoesData) notificacoesForm.reset(notificacoesData);
  }, [notificacoesData, notificacoesForm]);

  useEffect(() => {
    if (segurancaData) {
      segurancaForm.reset({
        ...segurancaData,
        ips_permitidos: segurancaData.ips_permitidos?.join(", ") || "",
      });
    }
  }, [segurancaData, segurancaForm]);

  useEffect(() => {
    if (integracoesData) {
      integracoesForm.reset({
        webhook_url: integracoesData.webhook_url || "",
        webhook_secret: "",
        api_folha_ativa: integracoesData.api_folha_ativa || false,
        api_folha_url: integracoesData.api_folha_url || "",
        api_folha_token: "",
      });
    }
  }, [integracoesData, integracoesForm]);

  // Mutations
  const updateTenantMutation = useMutation({
    mutationFn: (data: TenantUpdate) => empresaService.updateTenant(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant"] });
      toast.success("Dados da empresa atualizados!");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const updatePontoMutation = useMutation({
    mutationFn: (data: Partial<ConfiguracoesPonto>) => configuracoesService.updatePonto(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["config-ponto"] });
      toast.success("Configurações de ponto salvas!");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const updateNotificacoesMutation = useMutation({
    mutationFn: (data: Partial<ConfiguracoesNotificacoes>) => configuracoesService.updateNotificacoes(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["config-notificacoes"] });
      toast.success("Configurações de notificações salvas!");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const updateSegurancaMutation = useMutation({
    mutationFn: (data: Partial<ConfiguracoesSeguranca>) => configuracoesService.updateSeguranca(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["config-seguranca"] });
      toast.success("Configurações de segurança salvas!");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const updateIntegracoesMutation = useMutation({
    mutationFn: (data: Partial<ConfiguracoesIntegracoes>) => configuracoesService.updateIntegracoes(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["config-integracoes"] });
      toast.success("Configurações de integrações salvas!");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const testarWebhookMutation = useMutation({
    mutationFn: () => configuracoesService.testarWebhook(),
    onSuccess: (res) => {
      if (res.sucesso) {
        toast.success(res.mensagem);
      } else {
        toast.error(res.mensagem);
      }
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  // Submit Handlers
  const onSubmitEmpresa = (data: EmpresaForm) => {
    const endereco: Endereco = {
      cep: data.cep,
      logradouro: data.logradouro,
      numero: data.numero,
      complemento: data.complemento,
      bairro: data.bairro,
      municipio: data.cidade,
      uf: data.estado,
      pais: "Brasil",
    };

    updateTenantMutation.mutate({
      nome: data.nome,
      razao_social: data.razao_social,
      email: data.email || undefined,
      telefone: data.telefone || undefined,
      endereco,
    });
  };

  const onSubmitPonto = (data: PontoForm) => updatePontoMutation.mutate(data);
  const onSubmitNotificacoes = (data: NotificacoesForm) => {
    updateNotificacoesMutation.mutate({
      ...data,
      horario_lembrete_entrada: data.horario_lembrete_entrada || null,
      horario_lembrete_saida: data.horario_lembrete_saida || null,
    });
  };

  const onSubmitSeguranca = (data: SegurancaForm) => {
    const ipsList = data.ips_permitidos
      ? data.ips_permitidos.split(",").map((s) => s.trim()).filter(Boolean)
      : undefined;
    updateSegurancaMutation.mutate({ ...data, ips_permitidos: ipsList });
  };

  const onSubmitIntegracoes = (data: IntegracoesForm) => {
    const payload: Partial<ConfiguracoesIntegracoes> = {
      webhook_url: data.webhook_url || undefined,
      api_folha_ativa: data.api_folha_ativa,
      api_folha_url: data.api_folha_url || undefined,
    };
    if (data.webhook_secret) payload.webhook_secret = data.webhook_secret;
    if (data.api_folha_token) payload.api_folha_token = data.api_folha_token;

    updateIntegracoesMutation.mutate(payload);
  };

  const handleRefresh = () => {
    refetchTenant();
    refetchPonto();
    refetchNotificacoes();
    refetchSeguranca();
    refetchIntegracoes();
    toast.success("Dados atualizados!");
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Empresa e Configurações</h1>
          <p className="text-muted-foreground">
            Gerencie os dados cadastrais e parâmetros operacionais do sistema
          </p>
        </div>
        <Button variant="outline" size="icon" onClick={handleRefresh}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-5 lg:w-auto">
          <TabsTrigger value="empresa" className="flex items-center gap-2">
            <Building2 className="h-4 w-4" />
            Empresa
          </TabsTrigger>
          <TabsTrigger value="ponto" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Jornada & Ponto
          </TabsTrigger>
          <TabsTrigger value="notificacoes" className="flex items-center gap-2">
            <Bell className="h-4 w-4" />
            Notificações
          </TabsTrigger>
          <TabsTrigger value="seguranca" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Segurança
          </TabsTrigger>
          <TabsTrigger value="integracoes" className="flex items-center gap-2">
            <Settings className="h-4 w-4" />
            Integrações
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Dados Gerais da Empresa */}
        <TabsContent value="empresa">
          <Card>
            <CardHeader>
              <CardTitle>Dados da Empresa</CardTitle>
              <CardDescription>Informações cadastrais corporativas</CardDescription>
            </CardHeader>
            <CardContent>
              {tenantLoading ? (
                <div className="space-y-4">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : (
                <form onSubmit={empresaForm.handleSubmit(onSubmitEmpresa)} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="nome">Nome Fantasia *</Label>
                      <Input id="nome" {...empresaForm.register("nome")} />
                      {empresaForm.formState.errors.nome && (
                        <p className="text-sm text-destructive">{empresaForm.formState.errors.nome.message}</p>
                      )}
                    </div>
                    <div>
                      <Label htmlFor="razao_social">Razão Social</Label>
                      <Input id="razao_social" {...empresaForm.register("razao_social")} />
                    </div>
                    <div>
                      <Label htmlFor="cnpj">CNPJ (Somente Leitura)</Label>
                      <Input id="cnpj" {...empresaForm.register("cnpj")} disabled className="bg-muted" />
                    </div>
                    <div>
                      <Label htmlFor="telefone">Telefone</Label>
                      <Input id="telefone" {...empresaForm.register("telefone")} />
                    </div>
                    <div>
                      <Label htmlFor="email">Email Corporativo</Label>
                      <Input id="email" type="email" {...empresaForm.register("email")} />
                    </div>
                  </div>

                  <div className="border-t pt-4 mt-4">
                    <h3 className="font-medium text-sm mb-3">Endereço Estruturado</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <Label htmlFor="cep">CEP</Label>
                        <Input id="cep" {...empresaForm.register("cep")} />
                      </div>
                      <div className="md:col-span-2">
                        <Label htmlFor="logradouro">Logradouro</Label>
                        <Input id="logradouro" {...empresaForm.register("logradouro")} />
                      </div>
                      <div>
                        <Label htmlFor="numero">Número</Label>
                        <Input id="numero" {...empresaForm.register("numero")} />
                      </div>
                      <div>
                        <Label htmlFor="complemento">Complemento</Label>
                        <Input id="complemento" {...empresaForm.register("complemento")} />
                      </div>
                      <div>
                        <Label htmlFor="bairro">Bairro</Label>
                        <Input id="bairro" {...empresaForm.register("bairro")} />
                      </div>
                      <div>
                        <Label htmlFor="cidade">Município / Cidade</Label>
                        <Input id="cidade" {...empresaForm.register("cidade")} />
                      </div>
                      <div>
                        <Label htmlFor="estado">UF / Estado</Label>
                        <Input id="estado" {...empresaForm.register("estado")} />
                      </div>
                    </div>
                  </div>

                  <Button type="submit" disabled={updateTenantMutation.isPending}>
                    {updateTenantMutation.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="mr-2 h-4 w-4" />
                    )}
                    Salvar Dados
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 2: Jornada e Ponto */}
        <TabsContent value="ponto">
          <Card>
            <CardHeader>
              <CardTitle>Configurações de Ponto</CardTitle>
              <CardDescription>Parâmetros operacionais da marcação de ponto</CardDescription>
            </CardHeader>
            <CardContent>
              {pontoLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : (
                <form onSubmit={pontoForm.handleSubmit(onSubmitPonto)} className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="jornada_diaria">Jornada Diária Padrão (Horas)</Label>
                      <Input id="jornada_diaria" type="number" {...pontoForm.register("jornada_diaria")} />
                    </div>
                    <div>
                      <Label htmlFor="jornada_semanal">Jornada Semanal Padrão (Horas)</Label>
                      <Input id="jornada_semanal" type="number" {...pontoForm.register("jornada_semanal")} />
                    </div>
                    <div>
                      <Label htmlFor="tolerancia_minutos">Tolerância Geral (Minutos)</Label>
                      <Input id="tolerancia_minutos" type="number" {...pontoForm.register("tolerancia_minutos")} />
                    </div>
                    <div>
                      <Label htmlFor="intervalo_minimo">Intervalo Mínimo de Almoço (Minutos)</Label>
                      <Input id="intervalo_minimo" type="number" {...pontoForm.register("intervalo_minimo")} />
                    </div>
                  </div>

                  <div className="space-y-4 border-t pt-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>Exigir Foto no Registro</Label>
                        <p className="text-xs text-muted-foreground">Exige captura de selfie a cada marcação</p>
                      </div>
                      <Switch
                        checked={pontoForm.watch("exigir_foto")}
                        onCheckedChange={(checked) => pontoForm.setValue("exigir_foto", checked)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>Exigir Geolocalização</Label>
                        <p className="text-xs text-muted-foreground">Valida coordenadas GPS durante o registro</p>
                      </div>
                      <Switch
                        checked={pontoForm.watch("exigir_geolocalizacao")}
                        onCheckedChange={(checked) => pontoForm.setValue("exigir_geolocalizacao", checked)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>Permitir Marcação Offline</Label>
                        <p className="text-xs text-muted-foreground">Armazena marcações no dispositivo para sincronização posterior</p>
                      </div>
                      <Switch
                        checked={pontoForm.watch("permitir_offline")}
                        onCheckedChange={(checked) => pontoForm.setValue("permitir_offline", checked)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>Hora Extra Automática</Label>
                        <p className="text-xs text-muted-foreground">Calcula horas excedentes automaticamente</p>
                      </div>
                      <Switch
                        checked={pontoForm.watch("hora_extra_automatica")}
                        onCheckedChange={(checked) => pontoForm.setValue("hora_extra_automatica", checked)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>Banco de Horas Ativo</Label>
                        <p className="text-xs text-muted-foreground">Direciona horas extras para o banco de horas</p>
                      </div>
                      <Switch
                        checked={pontoForm.watch("banco_horas_ativo")}
                        onCheckedChange={(checked) => pontoForm.setValue("banco_horas_ativo", checked)}
                      />
                    </div>
                  </div>

                  <Button type="submit" disabled={updatePontoMutation.isPending}>
                    {updatePontoMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                    Salvar Configurações de Ponto
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 3: Notificações */}
        <TabsContent value="notificacoes">
          <Card>
            <CardHeader>
              <CardTitle>Configurações de Notificações</CardTitle>
              <CardDescription>Canais e alertas automáticos do sistema</CardDescription>
            </CardHeader>
            <CardContent>
              {notificacoesLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : (
                <form onSubmit={notificacoesForm.handleSubmit(onSubmitNotificacoes)} className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Disparo de E-mails Ativo</Label>
                      <p className="text-xs text-muted-foreground">Permite o envio de alertas por e-mail</p>
                    </div>
                    <Switch
                      checked={notificacoesForm.watch("email_ativo")}
                      onCheckedChange={(checked) => notificacoesForm.setValue("email_ativo", checked)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Notificações Push Ativas</Label>
                      <p className="text-xs text-muted-foreground">Envia avisos para aplicativo mobile</p>
                    </div>
                    <Switch
                      checked={notificacoesForm.watch("push_ativo")}
                      onCheckedChange={(checked) => notificacoesForm.setValue("push_ativo", checked)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Notificar Marcação de Ponto</Label>
                    </div>
                    <Switch
                      checked={notificacoesForm.watch("notificar_marcacao")}
                      onCheckedChange={(checked) => notificacoesForm.setValue("notificar_marcacao", checked)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Notificar Aprovação de Ajustes</Label>
                    </div>
                    <Switch
                      checked={notificacoesForm.watch("notificar_aprovacao")}
                      onCheckedChange={(checked) => notificacoesForm.setValue("notificar_aprovacao", checked)}
                    />
                  </div>

                  <Button type="submit" disabled={updateNotificacoesMutation.isPending} className="mt-4">
                    {updateNotificacoesMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                    Salvar Notificações
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 4: Segurança */}
        <TabsContent value="seguranca">
          <Card>
            <CardHeader>
              <CardTitle>Configurações de Segurança</CardTitle>
              <CardDescription>Políticas corporativas de acesso e autenticação</CardDescription>
            </CardHeader>
            <CardContent>
              {segurancaLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : (
                <form onSubmit={segurancaForm.handleSubmit(onSubmitSeguranca)} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="tempo_sessao">Tempo de Sessão (Minutos)</Label>
                      <Input id="tempo_sessao" type="number" {...segurancaForm.register("tempo_sessao")} />
                    </div>
                    <div>
                      <Label htmlFor="tentativas_login">Tentativas de Login Toleradas</Label>
                      <Input id="tentativas_login" type="number" {...segurancaForm.register("tentativas_login")} />
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="ips_permitidos">IPs Permitidos (Separados por vírgula)</Label>
                    <Input id="ips_permitidos" placeholder="ex: 200.100.50.1, 189.10.20.0/24" {...segurancaForm.register("ips_permitidos")} />
                  </div>
                  <div className="space-y-3 pt-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>MFA / 2FA Obrigatório</Label>
                        <p className="text-xs text-muted-foreground">Exige autenticação em duas etapas para todos os usuários</p>
                      </div>
                      <Switch
                        checked={segurancaForm.watch("mfa_obrigatorio")}
                        onCheckedChange={(checked) => segurancaForm.setValue("mfa_obrigatorio", checked)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>Sessão Única por Usuário</Label>
                        <p className="text-xs text-muted-foreground">Derruba logins anteriores ao autenticar em novo dispositivo</p>
                      </div>
                      <Switch
                        checked={segurancaForm.watch("sessao_unica")}
                        onCheckedChange={(checked) => segurancaForm.setValue("sessao_unica", checked)}
                      />
                    </div>
                  </div>

                  <Button type="submit" disabled={updateSegurancaMutation.isPending} className="mt-4">
                    {updateSegurancaMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                    Salvar Segurança
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 5: Integrações */}
        <TabsContent value="integracoes">
          <Card>
            <CardHeader>
              <CardTitle>Integrações e Webhooks</CardTitle>
              <CardDescription>Parâmetros para envio de eventos externos e folha de pagamento</CardDescription>
            </CardHeader>
            <CardContent>
              {integracoesLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : (
                <form onSubmit={integracoesForm.handleSubmit(onSubmitIntegracoes)} className="space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <Label htmlFor="webhook_url">URL do Webhook</Label>
                      {integracoesData?.webhook_secret_configurado && (
                        <span className="text-xs text-emerald-600 font-medium">✓ Webhook Secret Configurado</span>
                      )}
                    </div>
                    <Input id="webhook_url" placeholder="https://api.empresa.com/webhook" {...integracoesForm.register("webhook_url")} />
                  </div>
                  <div>
                    <Label htmlFor="webhook_secret">Novo Webhook Secret (Escreva para alterar)</Label>
                    <Input id="webhook_secret" type="password" placeholder="Deixe em branco para manter o atual" {...integracoesForm.register("webhook_secret")} />
                  </div>

                  <div className="border-t pt-4">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <Label>Integração com API de Folha</Label>
                      </div>
                      <Switch
                        checked={integracoesForm.watch("api_folha_ativa")}
                        onCheckedChange={(checked) => integracoesForm.setValue("api_folha_ativa", checked)}
                      />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="api_folha_url">URL da API de Folha</Label>
                        <Input id="api_folha_url" placeholder="https://folha.empresa.com/api" {...integracoesForm.register("api_folha_url")} />
                      </div>
                      <div>
                        <Label htmlFor="api_folha_token">Token da API de Folha</Label>
                        <Input id="api_folha_token" type="password" placeholder="Deixe em branco para manter o atual" {...integracoesForm.register("api_folha_token")} />
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-4">
                    <Button type="submit" disabled={updateIntegracoesMutation.isPending}>
                      {updateIntegracoesMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                      Salvar Integrações
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => testarWebhookMutation.mutate()}
                      disabled={testarWebhookMutation.isPending || !integracoesData?.webhook_url}
                    >
                      {testarWebhookMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                      Testar Webhook
                    </Button>
                  </div>
                </form>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
