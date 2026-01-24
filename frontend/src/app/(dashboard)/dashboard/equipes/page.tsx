"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/lib/api";
import { equipesService, usuariosService } from "@/services";
import type { Equipe, EquipeCreate, EquipeUpdate, EquipeWithMembers } from "@/services/equipes";
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
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { getInitials } from "@/lib/utils";
import {
  Plus,
  Search,
  MoreHorizontal,
  Pencil,
  Trash2,
  Loader2,
  Users,
  RefreshCw,
  UserPlus,
  Settings,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Textarea } from "@/components/ui/textarea";

const equipeSchema = z.object({
  nome: z.string().min(2, "Nome deve ter pelo menos 2 caracteres"),
  descricao: z.string().optional(),
  gestor_id: z.string().optional(),
  cor: z.string().optional(),
});

type EquipeForm = z.infer<typeof equipeSchema>;

const CORES = [
  { value: "#3B82F6", label: "Azul" },
  { value: "#10B981", label: "Verde" },
  { value: "#F59E0B", label: "Amarelo" },
  { value: "#EF4444", label: "Vermelho" },
  { value: "#8B5CF6", label: "Roxo" },
  { value: "#EC4899", label: "Rosa" },
  { value: "#6B7280", label: "Cinza" },
];

export default function EquipesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [addMemberDialogOpen, setAddMemberDialogOpen] = useState(false);
  const [editingEquipe, setEditingEquipe] = useState<Equipe | null>(null);
  const [deletingEquipe, setDeletingEquipe] = useState<Equipe | null>(null);
  const [selectedEquipe, setSelectedEquipe] = useState<Equipe | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<string>("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["equipes", debouncedSearch],
    queryFn: () => equipesService.list({ q: debouncedSearch || undefined, per_page: 50 }),
  });

  const { data: gestoresData } = useQuery({
    queryKey: ["gestores"],
    queryFn: () => usuariosService.list({ papel: "gestor", per_page: 100 }),
  });

  const { data: usuariosData } = useQuery({
    queryKey: ["usuarios-all"],
    queryFn: () => usuariosService.list({ per_page: 100 }),
  });

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<EquipeForm>({
    resolver: zodResolver(equipeSchema),
    defaultValues: { cor: "#3B82F6" },
  });

  const createMutation = useMutation({
    mutationFn: (data: EquipeCreate) => equipesService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["equipes"] });
      toast.success("Equipe criada com sucesso!");
      setDialogOpen(false);
      reset();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: EquipeUpdate }) =>
      equipesService.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["equipes"] });
      toast.success("Equipe atualizada com sucesso!");
      setDialogOpen(false);
      setEditingEquipe(null);
      reset();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => equipesService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["equipes"] });
      toast.success("Equipe removida com sucesso!");
      setDeleteDialogOpen(false);
      setDeletingEquipe(null);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const addMemberMutation = useMutation({
    mutationFn: ({ equipeId, usuarioId }: { equipeId: string; usuarioId: string }) =>
      equipesService.addMember(equipeId, usuarioId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["equipes"] });
      toast.success("Membro adicionado com sucesso!");
      setAddMemberDialogOpen(false);
      setSelectedUserId("");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const onSubmit = (formData: EquipeForm) => {
    if (editingEquipe) {
      updateMutation.mutate({ id: editingEquipe.id, data: formData });
    } else {
      createMutation.mutate(formData);
    }
  };

  const handleEdit = (equipe: Equipe) => {
    setEditingEquipe(equipe);
    setValue("nome", equipe.nome);
    setValue("descricao", equipe.descricao || "");
    setValue("gestor_id", equipe.gestor_id || "");
    setValue("cor", equipe.cor || "#3B82F6");
    setDialogOpen(true);
  };

  const handleDelete = (equipe: Equipe) => {
    setDeletingEquipe(equipe);
    setDeleteDialogOpen(true);
  };

  const handleAddMember = (equipe: Equipe) => {
    setSelectedEquipe(equipe);
    setAddMemberDialogOpen(true);
  };

  const handleNewEquipe = () => {
    setEditingEquipe(null);
    reset({ cor: "#3B82F6" });
    setDialogOpen(true);
  };

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Equipes</h2>
          <p className="text-muted-foreground">
            Gerencie as equipes e seus membros
            {data && ` • ${data.total} equipes`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={handleNewEquipe}>
            <Plus className="mr-2 h-4 w-4" />
            Nova Equipe
          </Button>
        </div>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Buscar equipe..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {isError ? (
        <div className="text-center py-8">
          <p className="text-destructive mb-4">Erro ao carregar equipes</p>
          <Button variant="outline" onClick={() => refetch()}>Tentar novamente</Button>
        </div>
      ) : isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array(6).fill(0).map((_, i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-4 w-48" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-20 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : data?.items?.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Users className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground mb-4">Nenhuma equipe encontrada</p>
            <Button onClick={handleNewEquipe}>
              <Plus className="mr-2 h-4 w-4" />
              Criar primeira equipe
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data?.items.map((equipe) => (
            <Card key={equipe.id} className="relative overflow-hidden">
              <div
                className="absolute top-0 left-0 right-0 h-1"
                style={{ backgroundColor: equipe.cor || "#3B82F6" }}
              />
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      {equipe.nome}
                      {!equipe.ativa && (
                        <Badge variant="secondary">Inativa</Badge>
                      )}
                    </CardTitle>
                    <CardDescription>{equipe.descricao || "Sem descrição"}</CardDescription>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuLabel>Ações</DropdownMenuLabel>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => handleAddMember(equipe)}>
                        <UserPlus className="mr-2 h-4 w-4" />
                        Adicionar Membro
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleEdit(equipe)}>
                        <Pencil className="mr-2 h-4 w-4" />
                        Editar
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Settings className="mr-2 h-4 w-4" />
                        Configurar Jornada
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => handleDelete(equipe)} className="text-destructive">
                        <Trash2 className="mr-2 h-4 w-4" />
                        Remover
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm">
                    <Users className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">
                      {usuariosData?.items.filter(u => u.equipe_id === equipe.id).length || 0} membros
                    </span>
                  </div>
                  {equipe.gestor_id && gestoresData && (
                    <div className="flex items-center gap-2">
                      <Avatar className="h-6 w-6">
                        <AvatarFallback className="text-xs">
                          {getInitials(gestoresData.items.find(g => g.id === equipe.gestor_id)?.nome || "")}
                        </AvatarFallback>
                      </Avatar>
                      <span className="text-sm text-muted-foreground">
                        Gestor: {gestoresData.items.find(g => g.id === equipe.gestor_id)?.nome || "N/A"}
                      </span>
                    </div>
                  )}
                  <div className="flex -space-x-2 overflow-hidden">
                    {usuariosData?.items
                      .filter(u => u.equipe_id === equipe.id)
                      .slice(0, 5)
                      .map((membro) => (
                        <Avatar key={membro.id} className="h-8 w-8 border-2 border-background">
                          <AvatarImage src={membro.foto_base_url || undefined} />
                          <AvatarFallback className="text-xs">{getInitials(membro.nome)}</AvatarFallback>
                        </Avatar>
                      ))}
                    {(usuariosData?.items.filter(u => u.equipe_id === equipe.id).length || 0) > 5 && (
                      <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center text-xs border-2 border-background">
                        +{(usuariosData?.items.filter(u => u.equipe_id === equipe.id).length || 0) - 5}
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) { setEditingEquipe(null); reset(); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingEquipe ? "Editar Equipe" : "Nova Equipe"}</DialogTitle>
            <DialogDescription>Preencha os dados da equipe</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="nome">Nome *</Label>
              <Input id="nome" {...register("nome")} />
              {errors.nome && <p className="text-sm text-destructive">{errors.nome.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="descricao">Descrição</Label>
              <Textarea id="descricao" {...register("descricao")} placeholder="Descrição da equipe..." />
            </div>
            <div className="space-y-2">
              <Label htmlFor="gestor_id">Gestor</Label>
              <Select value={watch("gestor_id") || "none"} onValueChange={(v) => setValue("gestor_id", v === "none" ? "" : v)}>
                <SelectTrigger><SelectValue placeholder="Selecione um gestor..." /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Nenhum</SelectItem>
                  {gestoresData?.items.map((gestor) => (
                    <SelectItem key={gestor.id} value={gestor.id}>{gestor.nome}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Cor</Label>
              <div className="flex gap-2">
                {CORES.map((cor) => (
                  <button
                    key={cor.value}
                    type="button"
                    onClick={() => setValue("cor", cor.value)}
                    className={`w-8 h-8 rounded-full border-2 transition-all ${watch("cor") === cor.value ? "border-foreground scale-110" : "border-transparent"}`}
                    style={{ backgroundColor: cor.value }}
                    title={cor.label}
                  />
                ))}
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
              <Button type="submit" disabled={isPending}>
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingEquipe ? "Salvar" : "Criar"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Add Member Dialog */}
      <Dialog open={addMemberDialogOpen} onOpenChange={setAddMemberDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Adicionar Membro</DialogTitle>
            <DialogDescription>
              Selecione um colaborador para adicionar à equipe {selectedEquipe?.nome}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Select value={selectedUserId} onValueChange={setSelectedUserId}>
              <SelectTrigger><SelectValue placeholder="Selecione um colaborador..." /></SelectTrigger>
              <SelectContent>
                {usuariosData?.items
                  .filter(u => !u.equipe_id || u.equipe_id !== selectedEquipe?.id)
                  .map((usuario) => (
                    <SelectItem key={usuario.id} value={usuario.id}>{usuario.nome} ({usuario.email})</SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddMemberDialogOpen(false)}>Cancelar</Button>
            <Button
              onClick={() => selectedEquipe && selectedUserId && addMemberMutation.mutate({ equipeId: selectedEquipe.id, usuarioId: selectedUserId })}
              disabled={!selectedUserId || addMemberMutation.isPending}
            >
              {addMemberMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Adicionar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar exclusão</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja remover a equipe <strong>{deletingEquipe?.nome}</strong>?
              Os membros serão desvinculados mas não removidos.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deletingEquipe && deleteMutation.mutate(deletingEquipe.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
              Remover
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
