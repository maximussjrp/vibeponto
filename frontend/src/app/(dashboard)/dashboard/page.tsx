"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { dashboardService, pontoService, auditoriaService } from "@/services";
import { formatDate, formatTime, getInitials } from "@/lib/utils";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  Users,
  Clock,
  CalendarCheck,
  AlertTriangle,
  TrendingUp,
  ArrowRight,
  UserCheck,
  Timer,
  RefreshCw,
  MapPin,
  Shield,
} from "lucide-react";
import Link from "next/link";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const COLORS = ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6"];

const TIPO_LABELS: Record<string, string> = {
  entrada: "Entrada",
  saida_almoco: "Saída Almoço",
  retorno_almoco: "Retorno Almoço",
  saida: "Saída",
};

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading, refetch: refetchStats } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => dashboardService.getStats(),
    refetchInterval: 60000, // Refresh every minute
  });

  const { data: marcacoesHoje, isLoading: marcacoesLoading } = useQuery({
    queryKey: ["marcacoes-hoje"],
    queryFn: () => {
      const today = new Date().toISOString().split("T")[0];
      return pontoService.listMarcacoes({ data_inicio: today, data_fim: today, per_page: 10 });
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const { data: alertasData, isLoading: alertasLoading } = useQuery({
    queryKey: ["alertas-novos"],
    queryFn: () => auditoriaService.listAlertas({ status: "novo", per_page: 5 }),
  });

  const { data: chartsData } = useQuery({
    queryKey: ["dashboard-charts"],
    queryFn: () => dashboardService.getCharts(),
  });

  const formatHoras = (minutos: number | undefined) => {
    if (!minutos) return "0h";
    const h = Math.floor(minutos / 60);
    const m = minutos % 60;
    return `${h}h${m > 0 ? ` ${m}m` : ""}`;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
          <p className="text-muted-foreground">
            Visão geral do sistema de ponto
          </p>
        </div>
        <Button variant="outline" size="icon" onClick={() => refetchStats()}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Colaboradores</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <>
                <div className="text-2xl font-bold">{stats?.colaboradores?.total || 0}</div>
                <p className="text-xs text-muted-foreground">
                  <span className="text-green-600">{stats?.colaboradores?.ativos || 0}</span> ativos
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Marcações Hoje</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <>
                <div className="text-2xl font-bold">{stats?.ponto?.marcacoes_hoje || 0}</div>
                <p className="text-xs text-muted-foreground">
                  <span className="text-yellow-600">{stats?.ponto?.pendentes_aprovacao || 0}</span> pendentes
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Horas Extras (Mês)</CardTitle>
            <Timer className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <>
                <div className="text-2xl font-bold text-green-600">{formatHoras(stats?.horas?.extras_mes)}</div>
                <p className="text-xs text-muted-foreground">
                  {stats?.ponto?.atrasos_hoje || 0} atrasos no mês
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Taxa de Assiduidade</CardTitle>
            <CalendarCheck className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <>
                <div className="text-2xl font-bold">{stats?.auditoria?.taxa_conformidade?.toFixed(1) || 0}%</div>
                <div className="flex items-center text-xs text-green-600">
                  <TrendingUp className="h-3 w-3 mr-1" />
                  <span>Meta: 95%</span>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Alertas and Charts */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Alertas de Auditoria */}
        <Card className="lg:col-span-1">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-lg">Alertas de Auditoria</CardTitle>
              <CardDescription>Requer atenção</CardDescription>
            </div>
            <Badge variant={alertasData?.items?.length ? "destructive" : "secondary"}>
              {alertasData?.total || 0}
            </Badge>
          </CardHeader>
          <CardContent>
            {alertasLoading ? (
              <div className="space-y-3">
                {Array(3).fill(0).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : !alertasData?.items?.length ? (
              <div className="text-center py-8">
                <Shield className="h-12 w-12 mx-auto text-muted-foreground mb-2" />
                <p className="text-muted-foreground text-sm">Nenhum alerta pendente</p>
              </div>
            ) : (
              <div className="space-y-3">
                {alertasData.items.slice(0, 5).map((alerta) => (
                  <div key={alerta.id} className="flex items-start gap-3 p-2 rounded-lg hover:bg-muted/50">
                    <AlertTriangle className="h-5 w-5 text-yellow-500 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{alerta.usuario?.nome}</p>
                      <p className="text-xs text-muted-foreground truncate">{alerta.descricao}</p>
                    </div>
                  </div>
                ))}
                <Link href="/dashboard/auditoria">
                  <Button variant="outline" className="w-full mt-2">
                    Ver todos
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Gráfico de Presença Semanal */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg">Presença Semanal</CardTitle>
            <CardDescription>Colaboradores presentes por dia</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              {chartsData?.weekly_presence ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartsData.weekly_presence}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis dataKey="name" className="text-xs" />
                    <YAxis className="text-xs" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "hsl(var(--card))",
                        border: "1px solid hsl(var(--border))",
                        borderRadius: "8px",
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="presentes"
                      stackId="1"
                      stroke="#22c55e"
                      fill="#22c55e"
                      fillOpacity={0.5}
                      name="Presentes"
                    />
                    <Area
                      type="monotone"
                      dataKey="ausentes"
                      stackId="1"
                      stroke="#ef4444"
                      fill="#ef4444"
                      fillOpacity={0.5}
                      name="Ausentes"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full">
                  <p className="text-muted-foreground">Carregando gráfico...</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Marcações Recentes and Distribuição */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Marcações Recentes */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-lg">Marcações Recentes</CardTitle>
              <CardDescription>Últimas marcações de hoje</CardDescription>
            </div>
            <Link href="/dashboard/ponto">
              <Button variant="ghost" size="sm">
                Ver todas
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {marcacoesLoading ? (
              <div className="space-y-3">
                {Array(5).fill(0).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : !marcacoesHoje?.items?.length ? (
              <div className="text-center py-8">
                <Clock className="h-12 w-12 mx-auto text-muted-foreground mb-2" />
                <p className="text-muted-foreground text-sm">Nenhuma marcação hoje</p>
              </div>
            ) : (
              <div className="space-y-3">
                {marcacoesHoje.items.slice(0, 8).map((marcacao) => (
                  <div key={marcacao.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted/50">
                    <Avatar className="h-9 w-9">
                      <AvatarImage src={marcacao.usuario?.foto_url} />
                      <AvatarFallback>{getInitials(marcacao.usuario?.nome || "")}</AvatarFallback>
                    </Avatar>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{marcacao.usuario?.nome}</p>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Badge variant="outline" className="text-xs">
                          {TIPO_LABELS[marcacao.tipo] || marcacao.tipo}
                        </Badge>
                        <span>{formatTime(new Date(marcacao.data_hora))}</span>
                      </div>
                    </div>
                    {marcacao.dentro_perimetro === true ? (
                      <MapPin className="h-4 w-4 text-green-500" />
                    ) : marcacao.dentro_perimetro === false ? (
                      <MapPin className="h-4 w-4 text-red-500" />
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Distribuição por Equipe */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Distribuição por Equipe</CardTitle>
            <CardDescription>Colaboradores por equipe</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[250px]">
              {chartsData?.team_distribution ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={chartsData.team_distribution}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {chartsData.team_distribution.map((entry: any, index: number) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "hsl(var(--card))",
                        border: "1px solid hsl(var(--border))",
                        borderRadius: "8px",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full">
                  <p className="text-muted-foreground">Carregando gráfico...</p>
                </div>
              )}
            </div>
            {chartsData?.team_distribution && (
              <div className="flex flex-wrap justify-center gap-4 mt-4">
                {chartsData.team_distribution.map((item: any, index: number) => (
                  <div key={item.name} className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: COLORS[index % COLORS.length] }}
                    />
                    <span className="text-sm text-muted-foreground">{item.name}: {item.value}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Horários de Pico */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Horários de Pico</CardTitle>
          <CardDescription>Distribuição de marcações por horário</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[200px]">
            {chartsData?.hourly_distribution ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartsData.hourly_distribution}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="hora" className="text-xs" />
                  <YAxis className="text-xs" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                    }}
                  />
                  <Bar dataKey="marcacoes" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Marcações" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full">
                <p className="text-muted-foreground">Carregando gráfico...</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
