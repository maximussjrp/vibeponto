"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/lib/api";
import { empresaService } from "@/services";
import type { Tenant, TenantUpdate, Configuracoes, ConfiguracoesUpdate } from "@/services/empresa";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Building2,
  Settings,
  Clock,
  Bell,
  Shield,
  Save,
  Loader2,
  RefreshCw,
  MapPin,
} from "lucide-react";

const empresaSchema = z.object({
  nome: z.string().min(2, "Nome deve ter pelo menos 2 caracteres"),
  cnpj: z.string().optional(),
  razao_social: z.string().optional(),
  endereco: z.string().optional(),
  telefone: z.string().optional(),
  email: z.string().email("Email inválido").optional().or(z.literal("")),
  logo_url: z.string().optional(),
});

const configSchema = z.object({
  tolerancia_atraso_minutos: z.coerce.number().min(0).max(60),
  tolerancia_saida_antecipada_minutos: z.coerce.number().min(0).max(60),
  horas_jornada_padrao: z.coerce.number().min(1).max(24),
  intervalo_almoco_minutos: z.coerce.number().min(0).max(180),
  permite_ponto_fora_perimetro: z.boolean(),
  exige_foto_ponto: z.boolean(),
  exige_geolocalizacao: z.boolean(),
  notificar_atrasos: z.boolean(),
  notificar_horas_extras: z.boolean(),
  dias_retroativos_correcao: z.coerce.number().min(0).max(30),
  aprovacao_automatica: z.boolean(),
  fuso_horario: z.string(),
});

type EmpresaForm = z.infer<typeof empresaSchema>;
type ConfigForm = z.infer<typeof configSchema>;

const FUSOS_HORARIOS = [
  { value: "America/Sao_Paulo", label: "São Paulo (GMT-3)" },
  { value: "America/Manaus", label: "Manaus (GMT-4)" },
  { value: "America/Cuiaba", label: "Cuiabá (GMT-4)" },
  { value: "America/Fortaleza", label: "Fortaleza (GMT-3)" },
  { value: "America/Rio_Branco", label: "Rio Branco (GMT-5)" },
];

export default function EmpresaPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("geral");

  const { data: tenantData, isLoading: tenantLoading, refetch: refetchTenant } = useQuery({
    queryKey: ["tenant"],
    queryFn: () => empresaService.getTenant(),
  });

  const { data: configData, isLoading: configLoading, refetch: refetchConfig } = useQuery({
    queryKey: ["configuracoes"],
    queryFn: () => empresaService.getConfiguracoes(),
  });

  const empresaForm = useForm<EmpresaForm>({
    resolver: zodResolver(empresaSchema),
    values: tenantData ? {
      nome: tenantData.nome || "",
      cnpj: tenantData.cnpj || "",
      razao_social: tenantData.razao_social || "",
      endereco: tenantData.endereco || "",
      telefone: tenantData.telefone || "",
      email: tenantData.email || "",
      logo_url: tenantData.logo_url || "",
    } : undefined,
  });

  const configForm = useForm<ConfigForm>({
    resolver: zodResolver(configSchema),
    values: configData ? {
      tolerancia_atraso_minutos: configData.tolerancia_atraso_minutos || 10,
      tolerancia_saida_antecipada_minutos: configData.tolerancia_saida_antecipada_minutos || 10,
      horas_jornada_padrao: configData.horas_jornada_padrao || 8,
      intervalo_almoco_minutos: configData.intervalo_almoco_minutos || 60,
      permite_ponto_fora_perimetro: configData.permite_ponto_fora_perimetro ?? false,
      exige_foto_ponto: configData.exige_foto_ponto ?? false,
      exige_geolocalizacao: configData.exige_geolocalizacao ?? true,
      notificar_atrasos: configData.notificar_atrasos ?? true,
      notificar_horas_extras: configData.notificar_horas_extras ?? true,
      dias_retroativos_correcao: configData.dias_retroativos_correcao || 7,
      aprovacao_automatica: configData.aprovacao_automatica ?? false,
      fuso_horario: configData.fuso_horario || "America/Sao_Paulo",
    } : undefined,
  });

  const updateTenantMutation = useMutation({
    mutationFn: (data: TenantUpdate) => empresaService.updateTenant(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tenant"] });
      toast.success("Dados da empresa atualizados!");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const updateConfigMutation = useMutation({
    mutationFn: (data: ConfiguracoesUpdate) => empresaService.updateConfiguracoes(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["configuracoes"] });
      toast.success("Configurações atualizadas!");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const onSubmitEmpresa = (data: EmpresaForm) => {
    updateTenantMutation.mutate(data);
  };

  const onSubmitConfig = (data: ConfigForm) => {
    updateConfigMutation.mutate(data);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Empresa</h2>
          <p className="text-muted-foreground">
            Configurações gerais da empresa
          </p>
        </div>
        <Button variant="outline" size="icon" onClick={() => { refetchTenant(); refetchConfig(); }}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4 lg:w-auto lg:inline-grid">
          <TabsTrigger value="geral" className="gap-2">
            <Building2 className="h-4 w-4" />
            <span className="hidden sm:inline">Geral</span>
          </TabsTrigger>
          <TabsTrigger value="jornada" className="gap-2">
            <Clock className="h-4 w-4" />
            <span className="hidden sm:inline">Jornada</span>
          </TabsTrigger>
          <TabsTrigger value="ponto" className="gap-2">
            <MapPin className="h-4 w-4" />
            <span className="hidden sm:inline">Ponto</span>
          </TabsTrigger>
          <TabsTrigger value="notificacoes" className="gap-2">
            <Bell className="h-4 w-4" />
            <span className="hidden sm:inline">Notificações</span>
          </TabsTrigger>
        </TabsList>

        {/* Dados Gerais */}
        <TabsContent value="geral">
          <Card>
            <CardHeader>
              <CardTitle>Dados da Empresa</CardTitle>
              <CardDescription>Informações cadastrais da sua empresa</CardDescription>
            </CardHeader>
            <CardContent>
              {tenantLoading ? (
                <div className="space-y-4">
                  {Array(6).fill(0).map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              ) : (
                <form onSubmit={empresaForm.handleSubmit(onSubmitEmpresa)} className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Nome Fantasia *</Label>
                      <Input {...empresaForm.register("nome")} />
                      {empresaForm.formState.errors.nome && (
                        <p className="text-sm text-destructive">{empresaForm.formState.errors.nome.message}</p>
                      )}
                    </div>
                    <div className="space-y-2">
                      <Label>Razão Social</Label>
                      <Input {...empresaForm.register("razao_social")} />
                    </div>
                    <div className="space-y-2">
                      <Label>CNPJ</Label>
                      <Input {...empresaForm.register("cnpj")} placeholder="00.000.000/0000-00" />
                    </div>
                    <div className="space-y-2">
                      <Label>Telefone</Label>
                      <Input {...empresaForm.register("telefone")} placeholder="(00) 0000-0000" />
                    </div>
                    <div className="space-y-2 md:col-span-2">
                      <Label>Email</Label>
                      <Input {...empresaForm.register("email")} type="email" />
                    </div>
                    <div className="space-y-2 md:col-span-2">
                      <Label>Endereço</Label>
                      <Textarea {...empresaForm.register("endereco")} placeholder="Endereço completo" />
                    </div>
                    <div className="space-y-2 md:col-span-2">
                      <Label>URL do Logo</Label>
                      <Input {...empresaForm.register("logo_url")} placeholder="https://..." />
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <Button type="submit" disabled={updateTenantMutation.isPending}>
                      {updateTenantMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                      Salvar
                    </Button>
                  </div>
                </form>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Jornada de Trabalho */}
        <TabsContent value="jornada">
          <Card>
            <CardHeader>
              <CardTitle>Jornada de Trabalho</CardTitle>
              <CardDescription>Configure os padrões de jornada</CardDescription>
            </CardHeader>
            <CardContent>
              {configLoading ? (
                <div className="space-y-4">
                  {Array(5).fill(0).map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              ) : (
                <form onSubmit={configForm.handleSubmit(onSubmitConfig)} className="space-y-6">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label>Horas de Jornada Padrão</Label>
                      <Input type="number" {...configForm.register("horas_jornada_padrao")} />
                    </div>
                    <div className="space-y-2">
                      <Label>Intervalo de Almoço (minutos)</Label>
                      <Input type="number" {...configForm.register("intervalo_almoco_minutos")} />
                    </div>
                    <div className="space-y-2">
                      <Label>Tolerância para Atraso (minutos)</Label>
                      <Input type="number" {...configForm.register("tolerancia_atraso_minutos")} />
                    </div>
                    <div className="space-y-2">
                      <Label>Tolerância Saída Antecipada (minutos)</Label>
                      <Input type="number" {...configForm.register("tolerancia_saida_antecipada_minutos")} />
                    </div>
                    <div className="space-y-2">
                      <Label>Fuso Horário</Label>
                      <Select
                        value={configForm.watch("fuso_horario")}
                        onValueChange={(v) => configForm.setValue("fuso_horario", v)}
                      >
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {FUSOS_HORARIOS.map((fuso) => (
                            <SelectItem key={fuso.value} value={fuso.value}>{fuso.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Dias Retroativos para Correção</Label>
                      <Input type="number" {...configForm.register("dias_retroativos_correcao")} />
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-4 border rounded-lg">
                    <div>
                      <Label>Aprovação Automática</Label>
                      <p className="text-sm text-muted-foreground">Aprovar marcações automaticamente quando dentro do perímetro</p>
                    </div>
                    <Switch
                      checked={configForm.watch("aprovacao_automatica")}
                      onCheckedChange={(v) => configForm.setValue("aprovacao_automatica", v)}
                    />
                  </div>

                  <div className="flex justify-end">
                    <Button type="submit" disabled={updateConfigMutation.isPending}>
                      {updateConfigMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                      Salvar
                    </Button>
                  </div>
                </form>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Configurações de Ponto */}
        <TabsContent value="ponto">
          <Card>
            <CardHeader>
              <CardTitle>Regras de Ponto</CardTitle>
              <CardDescription>Configure as regras para registro de ponto</CardDescription>
            </CardHeader>
            <CardContent>
              {configLoading ? (
                <div className="space-y-4">
                  {Array(4).fill(0).map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : (
                <form onSubmit={configForm.handleSubmit(onSubmitConfig)} className="space-y-4">
                  <div className="flex items-center justify-between p-4 border rounded-lg">
                    <div>
                      <Label>Exigir Geolocalização</Label>
                      <p className="text-sm text-muted-foreground">Obrigar envio de localização nas marcações</p>
                    </div>
                    <Switch
                      checked={configForm.watch("exige_geolocalizacao")}
                      onCheckedChange={(v) => configForm.setValue("exige_geolocalizacao", v)}
                    />
                  </div>

                  <div className="flex items-center justify-between p-4 border rounded-lg">
                    <div>
                      <Label>Permitir Ponto Fora do Perímetro</Label>
                      <p className="text-sm text-muted-foreground">Aceitar marcações fora dos perímetros configurados</p>
                    </div>
                    <Switch
                      checked={configForm.watch("permite_ponto_fora_perimetro")}
                      onCheckedChange={(v) => configForm.setValue("permite_ponto_fora_perimetro", v)}
                    />
                  </div>

                  <div className="flex items-center justify-between p-4 border rounded-lg">
                    <div>
                      <Label>Exigir Foto no Ponto</Label>
                      <p className="text-sm text-muted-foreground">Obrigar selfie para confirmar identidade</p>
                    </div>
                    <Switch
                      checked={configForm.watch("exige_foto_ponto")}
                      onCheckedChange={(v) => configForm.setValue("exige_foto_ponto", v)}
                    />
                  </div>

                  <div className="flex justify-end">
                    <Button type="submit" disabled={updateConfigMutation.isPending}>
                      {updateConfigMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                      Salvar
                    </Button>
                  </div>
                </form>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Notificações */}
        <TabsContent value="notificacoes">
          <Card>
            <CardHeader>
              <CardTitle>Notificações</CardTitle>
              <CardDescription>Configure alertas e notificações</CardDescription>
            </CardHeader>
            <CardContent>
              {configLoading ? (
                <div className="space-y-4">
                  {Array(3).fill(0).map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : (
                <form onSubmit={configForm.handleSubmit(onSubmitConfig)} className="space-y-4">
                  <div className="flex items-center justify-between p-4 border rounded-lg">
                    <div>
                      <Label>Notificar Atrasos</Label>
                      <p className="text-sm text-muted-foreground">Enviar notificação quando colaborador atrasar</p>
                    </div>
                    <Switch
                      checked={configForm.watch("notificar_atrasos")}
                      onCheckedChange={(v) => configForm.setValue("notificar_atrasos", v)}
                    />
                  </div>

                  <div className="flex items-center justify-between p-4 border rounded-lg">
                    <div>
                      <Label>Notificar Horas Extras</Label>
                      <p className="text-sm text-muted-foreground">Alertar sobre acúmulo de horas extras</p>
                    </div>
                    <Switch
                      checked={configForm.watch("notificar_horas_extras")}
                      onCheckedChange={(v) => configForm.setValue("notificar_horas_extras", v)}
                    />
                  </div>

                  <div className="flex justify-end">
                    <Button type="submit" disabled={updateConfigMutation.isPending}>
                      {updateConfigMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                      Salvar
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
