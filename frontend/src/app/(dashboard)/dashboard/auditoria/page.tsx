"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/lib/api";
import { auditoriaService } from "@/services";
import type { AlertaAuditoria, AlertaStatus, AlertaTipo } from "@/services/auditoria";
import { formatDate, formatTime, getInitials } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  AlertTriangle,
  Search,
  RefreshCw,
  Filter,
  Loader2,
  MapPin,
  Clock,
  Smartphone,
  Eye,
  CheckCircle2,
  XCircle,
  Shield,
  AlertCircle,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const STATUS_COLORS: Record<AlertaStatus, "default" | "secondary" | "destructive" | "outline"> = {
  novo: "destructive",
  em_analise: "secondary",
  resolvido: "default",
  ignorado: "outline",
};

const STATUS_LABELS: Record<AlertaStatus, string> = {
  novo: "Novo",
  em_analise: "Em Análise",
  resolvido: "Resolvido",
  ignorado: "Ignorado",
};

const TIPO_LABELS: Record<AlertaTipo, string> = {
  fora_perimetro: "Fora do Perímetro",
  horario_invalido: "Horário Inválido",
  dispositivo_nao_autorizado: "Dispositivo não Autorizado",
  multiplas_marcacoes: "Múltiplas Marcações",
  localizacao_suspeita: "Localização Suspeita",
  fraude_potencial: "Fraude Potencial",
};

const TIPO_ICONS: Record<AlertaTipo, any> = {
  fora_perimetro: MapPin,
  horario_invalido: Clock,
  dispositivo_nao_autorizado: Smartphone,
  multiplas_marcacoes: AlertCircle,
  localizacao_suspeita: MapPin,
  fraude_potencial: Shield,
};

export default function AuditoriaPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<AlertaStatus | "all">("all");
  const [tipoFilter, setTipoFilter] = useState<AlertaTipo | "all">("all");
  const [selectedAlerta, setSelectedAlerta] = useState<AlertaAuditoria | null>(null);
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  const [observacao, setObservacao] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["alertas", statusFilter, tipoFilter, page, debouncedSearch],
    queryFn: () => auditoriaService.listAlertas({
      status: statusFilter === "all" ? undefined : statusFilter,
      tipo: tipoFilter === "all" ? undefined : tipoFilter,
      q: debouncedSearch || undefined,
      page,
      per_page: 20,
    }),
  });

  const { data: statsData } = useQuery({
    queryKey: ["alertas-stats"],
    queryFn: () => auditoriaService.getStats(),
  });

  const resolverMutation = useMutation({
    mutationFn: ({ id, observacao }: { id: string; observacao: string }) =>
      auditoriaService.resolverAlerta(id, observacao),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alertas"] });
      queryClient.invalidateQueries({ queryKey: ["alertas-stats"] });
      toast.success("Alerta resolvido!");
      setReviewDialogOpen(false);
      setSelectedAlerta(null);
      setObservacao("");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const ignorarMutation = useMutation({
    mutationFn: ({ id, observacao }: { id: string; observacao: string }) =>
      auditoriaService.ignorarAlerta(id, observacao),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alertas"] });
      queryClient.invalidateQueries({ queryKey: ["alertas-stats"] });
      toast.success("Alerta ignorado");
      setReviewDialogOpen(false);
      setSelectedAlerta(null);
      setObservacao("");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const handleReview = (alerta: AlertaAuditoria) => {
    setSelectedAlerta(alerta);
    setReviewDialogOpen(true);
  };

  const renderIcon = (tipo: AlertaTipo) => {
    const Icon = TIPO_ICONS[tipo] || AlertTriangle;
    return <Icon className="h-4 w-4" />;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Auditoria</h2>
          <p className="text-muted-foreground">
            Monitore alertas e inconsistências nas marcações
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Novos Alertas</CardDescription>
            <CardTitle className="text-2xl text-red-600">{statsData?.novos || 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Em Análise</CardDescription>
            <CardTitle className="text-2xl text-yellow-600">{statsData?.em_analise || 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Resolvidos (Mês)</CardDescription>
            <CardTitle className="text-2xl text-green-600">{statsData?.resolvidos_mes || 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total</CardDescription>
            <CardTitle className="text-2xl">{statsData?.total || 0}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar por colaborador..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as AlertaStatus | "all")}>
          <SelectTrigger className="w-48">
            <Filter className="h-4 w-4 mr-2" />
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos Status</SelectItem>
            <SelectItem value="novo">Novo</SelectItem>
            <SelectItem value="em_analise">Em Análise</SelectItem>
            <SelectItem value="resolvido">Resolvido</SelectItem>
            <SelectItem value="ignorado">Ignorado</SelectItem>
          </SelectContent>
        </Select>
        <Select value={tipoFilter} onValueChange={(v) => setTipoFilter(v as AlertaTipo | "all")}>
          <SelectTrigger className="w-56">
            <SelectValue placeholder="Tipo" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos Tipos</SelectItem>
            <SelectItem value="fora_perimetro">Fora do Perímetro</SelectItem>
            <SelectItem value="horario_invalido">Horário Inválido</SelectItem>
            <SelectItem value="dispositivo_nao_autorizado">Dispositivo não Autorizado</SelectItem>
            <SelectItem value="multiplas_marcacoes">Múltiplas Marcações</SelectItem>
            <SelectItem value="localizacao_suspeita">Localização Suspeita</SelectItem>
            <SelectItem value="fraude_potencial">Fraude Potencial</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Alerts Table */}
      {isError ? (
        <div className="text-center py-8">
          <p className="text-destructive mb-4">Erro ao carregar alertas</p>
          <Button variant="outline" onClick={() => refetch()}>Tentar novamente</Button>
        </div>
      ) : isLoading ? (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tipo</TableHead>
                <TableHead>Colaborador</TableHead>
                <TableHead>Data/Hora</TableHead>
                <TableHead>Descrição</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array(5).fill(0).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-6 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-40" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-48" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-20" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      ) : !data?.items?.length ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Shield className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">Nenhum alerta encontrado</p>
            <p className="text-sm text-muted-foreground">Tudo parece estar em ordem!</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tipo</TableHead>
                <TableHead>Colaborador</TableHead>
                <TableHead>Data/Hora</TableHead>
                <TableHead>Descrição</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-24">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((alerta) => (
                <TableRow key={alerta.id}>
                  <TableCell>
                    <Badge variant="outline" className="gap-1">
                      {renderIcon(alerta.tipo)}
                      {TIPO_LABELS[alerta.tipo] || alerta.tipo}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <Avatar className="h-8 w-8">
                        <AvatarImage src={alerta.usuario?.foto_url} />
                        <AvatarFallback>{getInitials(alerta.usuario?.nome || "")}</AvatarFallback>
                      </Avatar>
                      <span className="font-medium">{alerta.usuario?.nome || "N/A"}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="text-sm">
                      <p>{formatDate(new Date(alerta.data_hora))}</p>
                      <p className="text-muted-foreground">{formatTime(new Date(alerta.data_hora))}</p>
                    </div>
                  </TableCell>
                  <TableCell className="max-w-xs truncate">{alerta.descricao}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_COLORS[alerta.status]}>
                      {STATUS_LABELS[alerta.status]}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {(alerta.status === "novo" || alerta.status === "em_analise") && (
                      <Button variant="outline" size="sm" onClick={() => handleReview(alerta)}>
                        <Eye className="h-4 w-4 mr-1" />
                        Revisar
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {/* Pagination */}
      {data && data.total_pages > 1 && (
        <div className="flex justify-center gap-2">
          <Button variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Anterior</Button>
          <span className="flex items-center px-4">Página {page} de {data.total_pages}</span>
          <Button variant="outline" disabled={page >= data.total_pages} onClick={() => setPage(p => p + 1)}>Próxima</Button>
        </div>
      )}

      {/* Review Dialog */}
      <Dialog open={reviewDialogOpen} onOpenChange={(open) => { setReviewDialogOpen(open); if (!open) { setSelectedAlerta(null); setObservacao(""); } }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Revisar Alerta</DialogTitle>
            <DialogDescription>Analise o alerta e tome uma ação</DialogDescription>
          </DialogHeader>
          {selectedAlerta && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Colaborador</p>
                  <p className="font-medium">{selectedAlerta.usuario?.nome}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Tipo</p>
                  <Badge variant="outline" className="gap-1 mt-1">
                    {renderIcon(selectedAlerta.tipo)}
                    {TIPO_LABELS[selectedAlerta.tipo]}
                  </Badge>
                </div>
                <div>
                  <p className="text-muted-foreground">Data/Hora</p>
                  <p className="font-medium">
                    {formatDate(new Date(selectedAlerta.data_hora))} às {formatTime(new Date(selectedAlerta.data_hora))}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Marcação Relacionada</p>
                  <p className="font-medium">{selectedAlerta.marcacao_id ? "Sim" : "Não"}</p>
                </div>
              </div>

              <div>
                <p className="text-muted-foreground text-sm">Descrição</p>
                <p className="mt-1 p-3 bg-muted rounded-md text-sm">{selectedAlerta.descricao}</p>
              </div>

              {selectedAlerta.detalhes && (
                <div>
                  <p className="text-muted-foreground text-sm">Detalhes Técnicos</p>
                  <pre className="mt-1 p-3 bg-muted rounded-md text-xs overflow-auto">
                    {JSON.stringify(selectedAlerta.detalhes, null, 2)}
                  </pre>
                </div>
              )}

              <div className="space-y-2">
                <Label>Observação</Label>
                <Textarea
                  value={observacao}
                  onChange={(e) => setObservacao(e.target.value)}
                  placeholder="Adicione uma observação sobre a resolução..."
                />
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setReviewDialogOpen(false)}>Cancelar</Button>
            <Button
              variant="secondary"
              onClick={() => selectedAlerta && ignorarMutation.mutate({ id: selectedAlerta.id, observacao })}
              disabled={ignorarMutation.isPending}
            >
              {ignorarMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <XCircle className="mr-2 h-4 w-4" />}
              Ignorar
            </Button>
            <Button
              onClick={() => selectedAlerta && resolverMutation.mutate({ id: selectedAlerta.id, observacao })}
              disabled={resolverMutation.isPending}
            >
              {resolverMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
              Resolver
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
