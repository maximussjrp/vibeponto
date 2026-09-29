"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/lib/api";
import { pontoService, usuariosService } from "@/services";
import type { Marcacao, MarcacaoCreate, Correcao, CorrecaoCreate, CorrecaoStatus } from "@/services/ponto";
import { formatCoordinates, formatDate, formatTime, getInitials } from "@/lib/utils";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  CalendarClock,
  Clock,
  Plus,
  Search,
  MapPin,
  Smartphone,
  Check,
  X,
  AlertTriangle,
  Loader2,
  Filter,
  RefreshCw,
  FileEdit,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const correcaoSchema = z.object({
  usuario_id: z.string().min(1, "Selecione um colaborador"),
  marcacao_id: z.string().optional(),
  tipo_marcacao: z.enum(["entrada", "saida_almoco", "retorno_almoco", "saida"]),
  data_hora_original: z.string().optional(),
  data_hora_corrigida: z.string().min(1, "Data/hora corrigida é obrigatória"),
  justificativa: z.string().min(10, "Justificativa deve ter pelo menos 10 caracteres"),
});

type CorrecaoForm = z.infer<typeof correcaoSchema>;

const STATUS_COLORS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  pendente: "secondary",
  aprovada: "default",
  rejeitada: "destructive",
};

const STATUS_LABELS: Record<string, string> = {
  pendente: "Pendente",
  aprovada: "Aprovada",
  rejeitada: "Rejeitada",
};

const TIPO_LABELS: Record<string, string> = {
  entrada: "Entrada",
  saida_almoco: "Saída Almoço",
  retorno_almoco: "Retorno Almoço",
  saida: "Saída",
};

export default function PontoPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("marcacoes");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [dateFilter, setDateFilter] = useState(() => {
    const today = new Date();
    return today.toISOString().split("T")[0];
  });
  const [statusFilter, setStatusFilter] = useState<CorrecaoStatus | "all">("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedCorrecao, setSelectedCorrecao] = useState<Correcao | null>(null);
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Marcações Query
  const { data: marcacoesData, isLoading: loadingMarcacoes, refetch: refetchMarcacoes } = useQuery({
    queryKey: ["marcacoes", dateFilter, debouncedSearch],
    queryFn: () => pontoService.listMarcacoes({
      data_inicio: dateFilter,
      data_fim: dateFilter,
      q: debouncedSearch || undefined,
      per_page: 100,
    }),
    enabled: activeTab === "marcacoes",
  });

  // Correções Query
  const { data: correcoesData, isLoading: loadingCorrecoes, refetch: refetchCorrecoes } = useQuery({
    queryKey: ["correcoes", statusFilter],
    queryFn: () => pontoService.listCorrecoes({
      status: statusFilter === "all" ? undefined : statusFilter,
      per_page: 100,
    }),
    enabled: activeTab === "correcoes",
  });

  // Usuários para o form
  const { data: usuariosData } = useQuery({
    queryKey: ["usuarios-ponto"],
    queryFn: () => usuariosService.list({ per_page: 100 }),
  });

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<CorrecaoForm>({
    resolver: zodResolver(correcaoSchema),
  });

  const createCorrecaoMutation = useMutation({
    mutationFn: (data: CorrecaoCreate) => pontoService.createCorrecao(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["correcoes"] });
      toast.success("Solicitação de correção enviada!");
      setDialogOpen(false);
      reset();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const aprovarMutation = useMutation({
    mutationFn: (id: string) => pontoService.aprovarCorrecao(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["correcoes"] });
      queryClient.invalidateQueries({ queryKey: ["marcacoes"] });
      toast.success("Correção aprovada!");
      setReviewDialogOpen(false);
      setSelectedCorrecao(null);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const rejeitarMutation = useMutation({
    mutationFn: ({ id, motivo }: { id: string; motivo: string }) =>
      pontoService.rejeitarCorrecao(id, motivo),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["correcoes"] });
      toast.success("Correção rejeitada");
      setReviewDialogOpen(false);
      setSelectedCorrecao(null);
      setRejectReason("");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const onSubmit = (formData: CorrecaoForm) => {
    createCorrecaoMutation.mutate({
      ...formData,
      data_hora_original: formData.data_hora_original || undefined,
    });
  };

  const handleReviewCorrecao = (correcao: Correcao) => {
    setSelectedCorrecao(correcao);
    setReviewDialogOpen(true);
  };

  const renderMarcacoes = () => {
    if (loadingMarcacoes) {
      return (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Colaborador</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Data/Hora</TableHead>
                <TableHead>Local</TableHead>
                <TableHead>Dispositivo</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array(5).fill(0).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-8 w-48" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-40" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      );
    }

    if (!marcacoesData?.items?.length) {
      return (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Clock className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">Nenhuma marcação encontrada para esta data</p>
          </CardContent>
        </Card>
      );
    }

    return (
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Colaborador</TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead>Data/Hora</TableHead>
              <TableHead>Local</TableHead>
              <TableHead>Dispositivo</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {marcacoesData.items.map((marcacao) => {
              const coordinates = formatCoordinates(marcacao.latitude, marcacao.longitude);

              return (
                <TableRow key={marcacao.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Avatar className="h-8 w-8">
                      <AvatarImage src={marcacao.usuario?.foto_url} />
                      <AvatarFallback>{getInitials(marcacao.usuario?.nome || "")}</AvatarFallback>
                    </Avatar>
                    <span className="font-medium">{marcacao.usuario?.nome || "N/A"}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">
                    {TIPO_LABELS[marcacao.tipo] || marcacao.tipo}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <CalendarClock className="h-4 w-4 text-muted-foreground" />
                    {formatDate(new Date(marcacao.data_hora))} {formatTime(new Date(marcacao.data_hora))}
                  </div>
                </TableCell>
                <TableCell>
                  {coordinates ? (
                    <div className="flex items-center gap-1 text-sm text-muted-foreground">
                      <MapPin className="h-3 w-3" />
                      {marcacao.endereco || coordinates}
                    </div>
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1 text-sm text-muted-foreground">
                    <Smartphone className="h-3 w-3" />
                    {marcacao.dispositivo || "Web"}
                  </div>
                </TableCell>
                <TableCell>
                  {marcacao.dentro_perimetro === true ? (
                    <Badge variant="default" className="bg-green-600">
                      <Check className="h-3 w-3 mr-1" />
                      Válido
                    </Badge>
                  ) : marcacao.dentro_perimetro === false ? (
                    <Badge variant="destructive">
                      <AlertTriangle className="h-3 w-3 mr-1" />
                      Fora do perímetro
                    </Badge>
                  ) : (
                    <Badge variant="secondary">Pendente</Badge>
                  )}
                </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>
    );
  };

  const renderCorrecoes = () => {
    if (loadingCorrecoes) {
      return (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Colaborador</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Original</TableHead>
                <TableHead>Corrigido</TableHead>
                <TableHead>Justificativa</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array(5).fill(0).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-8 w-48" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-48" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-20" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      );
    }

    if (!correcoesData?.items?.length) {
      return (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FileEdit className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">Nenhuma solicitação de correção encontrada</p>
          </CardContent>
        </Card>
      );
    }

    return (
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Colaborador</TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead>Original</TableHead>
              <TableHead>Corrigido</TableHead>
              <TableHead>Justificativa</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-24">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {correcoesData.items.map((correcao) => (
              <TableRow key={correcao.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Avatar className="h-8 w-8">
                      <AvatarImage src={correcao.usuario?.foto_url} />
                      <AvatarFallback>{getInitials(correcao.usuario?.nome || "")}</AvatarFallback>
                    </Avatar>
                    <span className="font-medium">{correcao.usuario?.nome || "N/A"}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">
                    {TIPO_LABELS[correcao.tipo_marcacao] || correcao.tipo_marcacao}
                  </Badge>
                </TableCell>
                <TableCell>
                  {correcao.data_hora_original ? (
                    <span className="text-sm">{formatDate(new Date(correcao.data_hora_original))} {formatTime(new Date(correcao.data_hora_original))}</span>
                  ) : (
                    <span className="text-muted-foreground">Nova marcação</span>
                  )}
                </TableCell>
                <TableCell>
                  <span className="text-sm font-medium">
                    {formatDate(new Date(correcao.data_hora_corrigida))} {formatTime(new Date(correcao.data_hora_corrigida))}
                  </span>
                </TableCell>
                <TableCell className="max-w-xs truncate">{correcao.justificativa}</TableCell>
                <TableCell>
                  <Badge variant={STATUS_COLORS[correcao.status]}>
                    {STATUS_LABELS[correcao.status]}
                  </Badge>
                </TableCell>
                <TableCell>
                  {correcao.status === "pendente" && (
                    <Button variant="outline" size="sm" onClick={() => handleReviewCorrecao(correcao)}>
                      Revisar
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Ponto</h2>
          <p className="text-muted-foreground">
            Gerencie marcações e solicitações de correção
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => activeTab === "marcacoes" ? refetchMarcacoes() : refetchCorrecoes()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Nova Correção
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="marcacoes">Marcações</TabsTrigger>
          <TabsTrigger value="correcoes">Correções</TabsTrigger>
        </TabsList>

        <TabsContent value="marcacoes" className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar colaborador..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Input
              type="date"
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              className="w-auto"
            />
          </div>
          {renderMarcacoes()}
        </TabsContent>

        <TabsContent value="correcoes" className="space-y-4">
          <div className="flex items-center gap-4">
            <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as CorrecaoStatus | "all")}>
              <SelectTrigger className="w-48">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Filtrar por status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="pendente">Pendente</SelectItem>
                <SelectItem value="aprovada">Aprovada</SelectItem>
                <SelectItem value="rejeitada">Rejeitada</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {renderCorrecoes()}
        </TabsContent>
      </Tabs>

      {/* Nova Correção Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) reset(); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Solicitar Correção de Ponto</DialogTitle>
            <DialogDescription>Preencha os dados para solicitar uma correção</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="usuario_id">Colaborador *</Label>
              <Select value={watch("usuario_id") || ""} onValueChange={(v) => setValue("usuario_id", v)}>
                <SelectTrigger><SelectValue placeholder="Selecione um colaborador" /></SelectTrigger>
                <SelectContent>
                  {usuariosData?.items.map((u) => (
                    <SelectItem key={u.id} value={u.id}>{u.nome}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.usuario_id && <p className="text-sm text-destructive">{errors.usuario_id.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="tipo_marcacao">Tipo de Marcação *</Label>
              <Select value={watch("tipo_marcacao") || ""} onValueChange={(v) => setValue("tipo_marcacao", v as any)}>
                <SelectTrigger><SelectValue placeholder="Selecione o tipo" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="entrada">Entrada</SelectItem>
                  <SelectItem value="saida_almoco">Saída Almoço</SelectItem>
                  <SelectItem value="retorno_almoco">Retorno Almoço</SelectItem>
                  <SelectItem value="saida">Saída</SelectItem>
                </SelectContent>
              </Select>
              {errors.tipo_marcacao && <p className="text-sm text-destructive">{errors.tipo_marcacao.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="data_hora_original">Data/Hora Original</Label>
              <Input type="datetime-local" {...register("data_hora_original")} />
              <p className="text-xs text-muted-foreground">Deixe em branco para nova marcação</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="data_hora_corrigida">Data/Hora Corrigida *</Label>
              <Input type="datetime-local" {...register("data_hora_corrigida")} />
              {errors.data_hora_corrigida && <p className="text-sm text-destructive">{errors.data_hora_corrigida.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="justificativa">Justificativa *</Label>
              <Textarea {...register("justificativa")} placeholder="Descreva o motivo da correção..." />
              {errors.justificativa && <p className="text-sm text-destructive">{errors.justificativa.message}</p>}
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
              <Button type="submit" disabled={createCorrecaoMutation.isPending}>
                {createCorrecaoMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Enviar Solicitação
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Review Correção Dialog */}
      <Dialog open={reviewDialogOpen} onOpenChange={(open) => { setReviewDialogOpen(open); if (!open) { setSelectedCorrecao(null); setRejectReason(""); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Revisar Correção</DialogTitle>
            <DialogDescription>Aprove ou rejeite a solicitação de correção</DialogDescription>
          </DialogHeader>
          {selectedCorrecao && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Colaborador</p>
                  <p className="font-medium">{selectedCorrecao.usuario?.nome}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Tipo</p>
                  <p className="font-medium">{TIPO_LABELS[selectedCorrecao.tipo_marcacao]}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Original</p>
                  <p className="font-medium">
                    {selectedCorrecao.data_hora_original 
                      ? `${formatDate(new Date(selectedCorrecao.data_hora_original))} ${formatTime(new Date(selectedCorrecao.data_hora_original))}`
                      : "Nova marcação"}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Corrigido</p>
                  <p className="font-medium">
                    {formatDate(new Date(selectedCorrecao.data_hora_corrigida))} {formatTime(new Date(selectedCorrecao.data_hora_corrigida))}
                  </p>
                </div>
              </div>
              <div>
                <p className="text-muted-foreground text-sm">Justificativa</p>
                <p className="mt-1 p-3 bg-muted rounded-md text-sm">{selectedCorrecao.justificativa}</p>
              </div>

              <div className="space-y-2">
                <Label>Motivo da Rejeição (opcional)</Label>
                <Textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Informe o motivo caso rejeite..."
                />
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setReviewDialogOpen(false)}>Cancelar</Button>
            <Button
              variant="destructive"
              onClick={() => selectedCorrecao && rejeitarMutation.mutate({ id: selectedCorrecao.id, motivo: rejectReason })}
              disabled={rejeitarMutation.isPending}
            >
              {rejeitarMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <XCircle className="mr-2 h-4 w-4" />}
              Rejeitar
            </Button>
            <Button
              onClick={() => selectedCorrecao && aprovarMutation.mutate(selectedCorrecao.id)}
              disabled={aprovarMutation.isPending}
            >
              {aprovarMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
              Aprovar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
