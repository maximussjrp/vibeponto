"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { getErrorMessage, api } from "@/lib/api";
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Plus,
  Search,
  MoreHorizontal,
  Pencil,
  Trash2,
  Loader2,
  Calendar,
  RefreshCw,
  Clock,
  Users,
  User,
  Copy,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// Tipos
interface JanelaHorario {
  entrada: string;
  saida: string;
  pausa_minutos: number;
}

interface Escala {
  id: string;
  nome: string;
  regime: "fixo" | "flexivel" | "turno" | "12x36" | "5x1" | "6x1" | "escala_alternada";
  usuario_id?: string;
  equipe_id?: string;
  janelas: Record<string, JanelaHorario>;
  tolerancia_entrada_min: number;
  tolerancia_saida_min: number;
  vigencia_inicio?: string;
  vigencia_fim?: string;
  ativa: boolean;
  created_at: string;
  updated_at: string;
}

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

// Schema de validação
const janelaSchema = z.object({
  entrada: z.string().regex(/^\d{2}:\d{2}$/, "Formato HH:MM"),
  saida: z.string().regex(/^\d{2}:\d{2}$/, "Formato HH:MM"),
  pausa_minutos: z.number().min(0).max(240),
});

const escalaSchema = z.object({
  nome: z.string().min(2, "Nome deve ter pelo menos 2 caracteres"),
  regime: z.enum(["fixo", "flexivel", "turno", "12x36", "5x1", "6x1", "escala_alternada"]),
  tolerancia_entrada_min: z.number().min(0).max(60),
  tolerancia_saida_min: z.number().min(0).max(60),
});

type EscalaForm = z.infer<typeof escalaSchema>;

// Dias da semana
const DIAS_SEMANA = [
  { key: "seg", label: "Segunda" },
  { key: "ter", label: "Terça" },
  { key: "qua", label: "Quarta" },
  { key: "qui", label: "Quinta" },
  { key: "sex", label: "Sexta" },
  { key: "sab", label: "Sábado" },
  { key: "dom", label: "Domingo" },
];

const REGIMES = [
  { value: "fixo", label: "Fixo" },
  { value: "flexivel", label: "Flexível" },
  { value: "turno", label: "Turno" },
  { value: "12x36", label: "12x36" },
  { value: "5x1", label: "5x1" },
  { value: "6x1", label: "6x1" },
  { value: "escala_alternada", label: "Escala Alternada" },
];

// Service
const escalasService = {
  listar: async (params: { page?: number; search?: string; ativa?: boolean }) => {
    const searchParams = new URLSearchParams();
    if (params.page) searchParams.set("page", String(params.page));
    if (params.ativa !== undefined) searchParams.set("ativa", String(params.ativa));
    const response = await api.get<PaginatedResponse<Escala>>(`/escalas?${searchParams}`);
    return response.data;
  },
  criar: async (data: Partial<Escala>) => {
    const response = await api.post<Escala>("/escalas", data);
    return response.data;
  },
  atualizar: async (id: string, data: Partial<Escala>) => {
    const response = await api.patch<Escala>(`/escalas/${id}`, data);
    return response.data;
  },
  excluir: async (id: string) => {
    await api.delete(`/escalas/${id}`);
  },
  duplicar: async (id: string) => {
    const response = await api.post<Escala>(`/escalas/${id}/duplicar`);
    return response.data;
  },
};

export default function EscalasPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editingEscala, setEditingEscala] = useState<Escala | null>(null);
  const [deletingEscala, setDeletingEscala] = useState<Escala | null>(null);
  const [page, setPage] = useState(1);
  const [showInativas, setShowInativas] = useState(false);
  
  // Janelas de horário
  const [janelas, setJanelas] = useState<Record<string, JanelaHorario>>({
    seg: { entrada: "08:00", saida: "17:00", pausa_minutos: 60 },
    ter: { entrada: "08:00", saida: "17:00", pausa_minutos: 60 },
    qua: { entrada: "08:00", saida: "17:00", pausa_minutos: 60 },
    qui: { entrada: "08:00", saida: "17:00", pausa_minutos: 60 },
    sex: { entrada: "08:00", saida: "17:00", pausa_minutos: 60 },
  });

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Queries
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["escalas", page, debouncedSearch, showInativas],
    queryFn: () => escalasService.listar({ 
      page, 
      search: debouncedSearch || undefined,
      ativa: showInativas ? undefined : true,
    }),
  });

  // Form
  const form = useForm<EscalaForm>({
    resolver: zodResolver(escalaSchema),
    defaultValues: {
      nome: "",
      regime: "fixo",
      tolerancia_entrada_min: 10,
      tolerancia_saida_min: 10,
    },
  });

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: Partial<Escala>) => escalasService.criar(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["escalas"] });
      toast.success("Escala criada com sucesso!");
      handleCloseDialog();
    },
    onError: (error) => {
      toast.error(getErrorMessage(error));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Escala> }) => 
      escalasService.atualizar(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["escalas"] });
      toast.success("Escala atualizada com sucesso!");
      handleCloseDialog();
    },
    onError: (error) => {
      toast.error(getErrorMessage(error));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => escalasService.excluir(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["escalas"] });
      toast.success("Escala excluída com sucesso!");
      setDeleteDialogOpen(false);
      setDeletingEscala(null);
    },
    onError: (error) => {
      toast.error(getErrorMessage(error));
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: (id: string) => escalasService.duplicar(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["escalas"] });
      toast.success("Escala duplicada com sucesso!");
    },
    onError: (error) => {
      toast.error(getErrorMessage(error));
    },
  });

  // Handlers
  const handleOpenCreate = () => {
    setEditingEscala(null);
    form.reset({
      nome: "",
      regime: "fixo",
      tolerancia_entrada_min: 10,
      tolerancia_saida_min: 10,
    });
    setJanelas({
      seg: { entrada: "08:00", saida: "17:00", pausa_minutos: 60 },
      ter: { entrada: "08:00", saida: "17:00", pausa_minutos: 60 },
      qua: { entrada: "08:00", saida: "17:00", pausa_minutos: 60 },
      qui: { entrada: "08:00", saida: "17:00", pausa_minutos: 60 },
      sex: { entrada: "08:00", saida: "17:00", pausa_minutos: 60 },
    });
    setDialogOpen(true);
  };

  const handleOpenEdit = (escala: Escala) => {
    setEditingEscala(escala);
    form.reset({
      nome: escala.nome,
      regime: escala.regime,
      tolerancia_entrada_min: escala.tolerancia_entrada_min,
      tolerancia_saida_min: escala.tolerancia_saida_min,
    });
    setJanelas(escala.janelas || {});
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingEscala(null);
    form.reset();
  };

  const handleSubmit = (values: EscalaForm) => {
    const data = {
      ...values,
      janelas,
    };

    if (editingEscala) {
      updateMutation.mutate({ id: editingEscala.id, data });
    } else {
      createMutation.mutate(data);
    }
  };

  const handleDelete = () => {
    if (deletingEscala) {
      deleteMutation.mutate(deletingEscala.id);
    }
  };

  const handleToggleAtiva = async (escala: Escala) => {
    try {
      await escalasService.atualizar(escala.id, { ativa: !escala.ativa });
      queryClient.invalidateQueries({ queryKey: ["escalas"] });
      toast.success(escala.ativa ? "Escala desativada" : "Escala ativada");
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  const updateJanela = (dia: string, field: keyof JanelaHorario, value: string | number) => {
    setJanelas(prev => ({
      ...prev,
      [dia]: {
        ...prev[dia],
        [field]: value,
      },
    }));
  };

  const toggleDia = (dia: string) => {
    setJanelas(prev => {
      if (prev[dia]) {
        const { [dia]: _, ...rest } = prev;
        return rest;
      }
      return {
        ...prev,
        [dia]: { entrada: "08:00", saida: "17:00", pausa_minutos: 60 },
      };
    });
  };

  const getRegimeLabel = (regime: string) => {
    return REGIMES.find(r => r.value === regime)?.label || regime;
  };

  const formatHorasTrabalhadas = (janelas: Record<string, JanelaHorario>) => {
    let totalMinutos = 0;
    Object.values(janelas).forEach(j => {
      if (j.entrada && j.saida) {
        const [hE, mE] = j.entrada.split(":").map(Number);
        const [hS, mS] = j.saida.split(":").map(Number);
        const minutos = (hS * 60 + mS) - (hE * 60 + mE) - (j.pausa_minutos || 0);
        totalMinutos += minutos;
      }
    });
    const horas = Math.floor(totalMinutos / 60);
    const minutos = totalMinutos % 60;
    return `${horas}h${minutos > 0 ? ` ${minutos}min` : ""}/semana`;
  };

  const isLoaded = !isLoading && data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Escalas de Trabalho</h1>
          <p className="text-muted-foreground">
            Gerencie as escalas e jornadas de trabalho
          </p>
        </div>
        <Button onClick={handleOpenCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Nova Escala
        </Button>
      </div>

      {/* Filtros */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Buscar escalas..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={showInativas}
                onCheckedChange={setShowInativas}
              />
              <Label>Mostrar inativas</Label>
            </div>
            <Button variant="outline" size="icon" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Tabela */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-4">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : !data?.items?.length ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Calendar className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">Nenhuma escala encontrada</h3>
              <p className="text-muted-foreground mb-4">
                Crie sua primeira escala de trabalho
              </p>
              <Button onClick={handleOpenCreate}>
                <Plus className="mr-2 h-4 w-4" />
                Nova Escala
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nome</TableHead>
                  <TableHead>Regime</TableHead>
                  <TableHead>Dias</TableHead>
                  <TableHead>Carga Horária</TableHead>
                  <TableHead>Tolerâncias</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[70px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((escala) => (
                  <TableRow key={escala.id}>
                    <TableCell className="font-medium">{escala.nome}</TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {getRegimeLabel(escala.regime)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {DIAS_SEMANA.map(d => (
                          <span
                            key={d.key}
                            className={`text-xs px-1 rounded ${
                              escala.janelas?.[d.key]
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted text-muted-foreground"
                            }`}
                          >
                            {d.key.charAt(0).toUpperCase()}
                          </span>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-muted-foreground">
                        {formatHorasTrabalhadas(escala.janelas || {})}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="text-xs text-muted-foreground">
                        ±{escala.tolerancia_entrada_min}min / ±{escala.tolerancia_saida_min}min
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge variant={escala.ativa ? "success" : "secondary"}>
                        {escala.ativa ? "Ativa" : "Inativa"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuLabel>Ações</DropdownMenuLabel>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onClick={() => handleOpenEdit(escala)}>
                            <Pencil className="mr-2 h-4 w-4" />
                            Editar
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => duplicateMutation.mutate(escala.id)}>
                            <Copy className="mr-2 h-4 w-4" />
                            Duplicar
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleToggleAtiva(escala)}>
                            {escala.ativa ? "Desativar" : "Ativar"}
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={() => {
                              setDeletingEscala(escala);
                              setDeleteDialogOpen(true);
                            }}
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Excluir
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Paginação */}
      {data && data.pages > 1 && (
        <div className="flex justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1}
            onClick={() => setPage(p => p - 1)}
          >
            Anterior
          </Button>
          <span className="flex items-center px-4 text-sm text-muted-foreground">
            Página {page} de {data.pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page === data.pages}
            onClick={() => setPage(p => p + 1)}
          >
            Próxima
          </Button>
        </div>
      )}

      {/* Dialog de Criar/Editar */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingEscala ? "Editar Escala" : "Nova Escala"}
            </DialogTitle>
            <DialogDescription>
              {editingEscala
                ? "Atualize os dados da escala de trabalho"
                : "Configure uma nova escala de trabalho"}
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
            {/* Dados básicos */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="nome">Nome da Escala</Label>
                <Input
                  id="nome"
                  placeholder="Ex: Comercial, Turno Manhã..."
                  {...form.register("nome")}
                />
                {form.formState.errors.nome && (
                  <p className="text-sm text-destructive">
                    {form.formState.errors.nome.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label>Regime</Label>
                <Select
                  value={form.watch("regime")}
                  onValueChange={(v) => form.setValue("regime", v as any)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione o regime" />
                  </SelectTrigger>
                  <SelectContent>
                    {REGIMES.map(r => (
                      <SelectItem key={r.value} value={r.value}>
                        {r.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Tolerâncias */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Tolerância Entrada (min)</Label>
                <Input
                  type="number"
                  min={0}
                  max={60}
                  {...form.register("tolerancia_entrada_min", { valueAsNumber: true })}
                />
              </div>
              <div className="space-y-2">
                <Label>Tolerância Saída (min)</Label>
                <Input
                  type="number"
                  min={0}
                  max={60}
                  {...form.register("tolerancia_saida_min", { valueAsNumber: true })}
                />
              </div>
            </div>

            {/* Janelas de Horário */}
            <div className="space-y-4">
              <Label className="text-base font-medium">Janelas de Horário</Label>
              <div className="space-y-3">
                {DIAS_SEMANA.map(dia => (
                  <div key={dia.key} className="flex items-center gap-4 p-3 border rounded-lg">
                    <div className="flex items-center gap-2 w-24">
                      <Switch
                        checked={!!janelas[dia.key]}
                        onCheckedChange={() => toggleDia(dia.key)}
                      />
                      <span className="text-sm font-medium">{dia.label}</span>
                    </div>
                    
                    {janelas[dia.key] && (
                      <>
                        <div className="flex items-center gap-2">
                          <Label className="text-xs text-muted-foreground">Entrada:</Label>
                          <Input
                            type="time"
                            value={janelas[dia.key].entrada}
                            onChange={(e) => updateJanela(dia.key, "entrada", e.target.value)}
                            className="w-28"
                          />
                        </div>
                        <div className="flex items-center gap-2">
                          <Label className="text-xs text-muted-foreground">Saída:</Label>
                          <Input
                            type="time"
                            value={janelas[dia.key].saida}
                            onChange={(e) => updateJanela(dia.key, "saida", e.target.value)}
                            className="w-28"
                          />
                        </div>
                        <div className="flex items-center gap-2">
                          <Label className="text-xs text-muted-foreground">Pausa:</Label>
                          <Input
                            type="number"
                            min={0}
                            max={240}
                            value={janelas[dia.key].pausa_minutos}
                            onChange={(e) => updateJanela(dia.key, "pausa_minutos", parseInt(e.target.value) || 0)}
                            className="w-20"
                          />
                          <span className="text-xs text-muted-foreground">min</span>
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
              <p className="text-sm text-muted-foreground">
                Carga horária semanal: <strong>{formatHorasTrabalhadas(janelas)}</strong>
              </p>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleCloseDialog}>
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={createMutation.isPending || updateMutation.isPending}
              >
                {(createMutation.isPending || updateMutation.isPending) && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {editingEscala ? "Salvar" : "Criar"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Dialog de Exclusão */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir escala?</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja excluir a escala &quot;{deletingEscala?.nome}&quot;?
              Esta ação não pode ser desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
