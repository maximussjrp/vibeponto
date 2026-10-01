"use client";

import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/lib/api";
import { formatCPF, getInitials } from "@/lib/utils";
import { useAuthStore } from "@/store/auth";
import { usuariosService, equipesService } from "@/services";
import type { Usuario, UsuarioCreate, UsuarioUpdate, ListUsuariosParams } from "@/services/usuarios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
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
import {
  Plus,
  Search,
  MoreHorizontal,
  Pencil,
  Trash2,
  Loader2,
  Eye,
  EyeOff,
  Download,
  RefreshCw,
  UserX,
  UserCheck,
  KeyRound,
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
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";

const usuarioSchema = z.object({
  nome: z.string().min(3, "Nome deve ter pelo menos 3 caracteres"),
  email: z.string().email("Email inválido"),
  cpf: z.string().min(11, "CPF inválido").max(14),
  matricula: z.string().min(1, "Matrícula é obrigatória"),
  telefone: z.string().optional(),
  password: z.string().min(6, "Senha deve ter pelo menos 6 caracteres").optional(),
  papel: z.enum(["admin_dp", "gestor", "colaborador", "auditor", "financeiro"]),
  equipe_id: z.string().optional(),
});

type UsuarioForm = z.infer<typeof usuarioSchema>;

const PAPEIS = {
  admin_dp: { label: "Admin DP", variant: "default" as const },
  gestor: { label: "Gestor", variant: "secondary" as const },
  colaborador: { label: "Colaborador", variant: "outline" as const },
  auditor: { label: "Auditor", variant: "secondary" as const },
  financeiro: { label: "Financeiro", variant: "secondary" as const },
};

const STATUS = {
  active: { label: "Ativo", variant: "success" as const },
  inactive: { label: "Inativo", variant: "secondary" as const },
  suspended: { label: "Suspenso", variant: "destructive" as const },
};

export default function UsuariosPage() {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [papelFilter, setPapelFilter] = useState<string>("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<Usuario | null>(null);
  const [deletingUser, setDeletingUser] = useState<Usuario | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const queryParams: ListUsuariosParams = {
    page,
    per_page: 10,
    q: debouncedSearch || undefined,
    status: statusFilter !== "all" ? statusFilter : undefined,
    papel: papelFilter !== "all" ? papelFilter : undefined,
  };

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["usuarios", queryParams],
    queryFn: () => usuariosService.list(queryParams),
  });

  const { data: equipesData } = useQuery({
    queryKey: ["equipes-select"],
    queryFn: () => equipesService.list({ per_page: 100 }),
  });

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<UsuarioForm>({
    resolver: zodResolver(usuarioSchema),
    defaultValues: { papel: "colaborador" },
  });

  const createMutation = useMutation({
    mutationFn: (data: UsuarioCreate) => usuariosService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["usuarios"] });
      toast.success("Colaborador criado com sucesso!");
      setDialogOpen(false);
      reset();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: UsuarioUpdate }) =>
      usuariosService.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["usuarios"] });
      toast.success("Colaborador atualizado com sucesso!");
      setDialogOpen(false);
      setEditingUser(null);
      reset();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => usuariosService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["usuarios"] });
      toast.success("Colaborador removido com sucesso!");
      setDeleteDialogOpen(false);
      setDeletingUser(null);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const suspendMutation = useMutation({
    mutationFn: (id: string) => usuariosService.suspend(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["usuarios"] });
      toast.success("Colaborador suspenso!");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const activateMutation = useMutation({
    mutationFn: (id: string) => usuariosService.activate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["usuarios"] });
      toast.success("Colaborador reativado!");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const resetPasswordMutation = useMutation({
    mutationFn: (id: string) => usuariosService.resetPassword(id),
    onSuccess: (data) => {
      toast.success(data.message || "Solicitação de reset de senha enviada com sucesso!", { duration: 5000 });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const onSubmit = (formData: UsuarioForm) => {
    const isGestor = user?.papel === "gestor";
    if (editingUser) {
      const updateData: UsuarioUpdate = {
        nome: formData.nome,
        telefone: formData.telefone,
        equipe_id: formData.equipe_id || undefined,
      };
      if (!isGestor && formData.papel) {
        updateData.papel = formData.papel;
      }
      updateMutation.mutate({ id: editingUser.id, data: updateData });
    } else {
      const createData: UsuarioCreate = {
        nome: formData.nome,
        email: formData.email,
        cpf: formData.cpf.replace(/\D/g, ""),
        matricula: formData.matricula,
        telefone: formData.telefone,
        password: formData.password!,
        papel: formData.papel,
        equipe_id: formData.equipe_id || undefined,
      };
      createMutation.mutate(createData);
    }
  };

  const handleEdit = (userToEdit: Usuario) => {
    setEditingUser(userToEdit);
    setValue("nome", userToEdit.nome);
    setValue("email", userToEdit.email);
    setValue("cpf", userToEdit.cpf || "");
    setValue("matricula", userToEdit.matricula || "");
    setValue("telefone", userToEdit.telefone || "");
    setValue("papel", userToEdit.papel);
    setValue("equipe_id", userToEdit.equipe_id || "");
    setDialogOpen(true);
  };

  const handleDelete = (user: Usuario) => {
    setDeletingUser(user);
    setDeleteDialogOpen(true);
  };

  const handleNewUser = () => {
    setEditingUser(null);
    reset({ 
      nome: "",
      email: "",
      cpf: "",
      matricula: "",
      telefone: "",
      password: "",
      papel: "colaborador",
      equipe_id: "",
    });
    setDialogOpen(true);
  };

  const handleCloseDialog = (open: boolean) => {
    setDialogOpen(open);
    if (!open) {
      setEditingUser(null);
      reset();
    }
  };

  const getRoleBadge = (papel: string) => {
    const config = PAPEIS[papel as keyof typeof PAPEIS] || PAPEIS.colaborador;
    return <Badge variant={config.variant}>{config.label}</Badge>;
  };

  const getStatusBadge = (status: string) => {
    const config = STATUS[status as keyof typeof STATUS] || STATUS.inactive;
    return <Badge variant={config.variant}>{config.label}</Badge>;
  };

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Colaboradores</h2>
          <p className="text-muted-foreground">
            Gerencie os colaboradores da empresa
            {data && ` • ${data.total} cadastrados`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button variant="outline">
            <Download className="mr-2 h-4 w-4" />
            Exportar
          </Button>
          <Button onClick={handleNewUser}>
            <Plus className="mr-2 h-4 w-4" />
            Novo Colaborador
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar por nome, email ou matrícula..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="active">Ativos</SelectItem>
                <SelectItem value="inactive">Inativos</SelectItem>
                <SelectItem value="suspended">Suspensos</SelectItem>
              </SelectContent>
            </Select>
            <Select value={papelFilter} onValueChange={(v) => { setPapelFilter(v); setPage(1); }}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Permissão" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas</SelectItem>
                <SelectItem value="admin_dp">Admin DP</SelectItem>
                <SelectItem value="gestor">Gestor</SelectItem>
                <SelectItem value="colaborador">Colaborador</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          {isError ? (
            <div className="text-center py-8">
              <p className="text-destructive mb-4">Erro ao carregar colaboradores</p>
              <Button variant="outline" onClick={() => refetch()}>Tentar novamente</Button>
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Colaborador</TableHead>
                    <TableHead>Matrícula</TableHead>
                    <TableHead>CPF</TableHead>
                    <TableHead>Equipe</TableHead>
                    <TableHead>Permissão</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading ? (
                    Array(5).fill(0).map((_, i) => (
                      <TableRow key={i}>
                        <TableCell><div className="flex items-center gap-3"><Skeleton className="w-10 h-10 rounded-full" /><div><Skeleton className="h-4 w-32 mb-1" /><Skeleton className="h-3 w-24" /></div></div></TableCell>
                        <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                        <TableCell><Skeleton className="h-4 w-28" /></TableCell>
                        <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                        <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                        <TableCell><Skeleton className="h-6 w-16" /></TableCell>
                        <TableCell><Skeleton className="h-8 w-8 ml-auto" /></TableCell>
                      </TableRow>
                    ))
                  ) : data?.items?.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                        Nenhum colaborador encontrado
                      </TableCell>
                    </TableRow>
                  ) : (
                    data?.items.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <Avatar>
                              <AvatarImage src={user.foto_base_url || undefined} />
                              <AvatarFallback>{getInitials(user.nome)}</AvatarFallback>
                            </Avatar>
                            <div>
                              <p className="font-medium">{user.nome}</p>
                              <p className="text-sm text-muted-foreground">{user.email}</p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="font-mono">{user.matricula}</TableCell>
                        <TableCell className="font-mono">{formatCPF(user.cpf)}</TableCell>
                        <TableCell>
                          {user.equipe_id ? equipesData?.items.find(e => e.id === user.equipe_id)?.nome || "-" : <span className="text-muted-foreground">-</span>}
                        </TableCell>
                        <TableCell>{getRoleBadge(user.papel)}</TableCell>
                        <TableCell>{getStatusBadge(user.status)}</TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon"><MoreHorizontal className="h-4 w-4" /></Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuLabel>Ações</DropdownMenuLabel>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem onClick={() => handleEdit(user)}>
                                <Pencil className="mr-2 h-4 w-4" />Editar
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => resetPasswordMutation.mutate(user.id)}>
                                <KeyRound className="mr-2 h-4 w-4" />Resetar Senha
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              {user.status === "active" ? (
                                <DropdownMenuItem onClick={() => suspendMutation.mutate(user.id)}>
                                  <UserX className="mr-2 h-4 w-4" />Suspender
                                </DropdownMenuItem>
                              ) : (
                                <DropdownMenuItem onClick={() => activateMutation.mutate(user.id)}>
                                  <UserCheck className="mr-2 h-4 w-4" />Reativar
                                </DropdownMenuItem>
                              )}
                              <DropdownMenuSeparator />
                              <DropdownMenuItem onClick={() => handleDelete(user)} className="text-destructive">
                                <Trash2 className="mr-2 h-4 w-4" />Remover
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>

              {data && data.pages > 1 && (
                <div className="mt-4 flex justify-center">
                  <Pagination>
                    <PaginationContent>
                      <PaginationItem>
                        <PaginationPrevious href="#" onClick={(e) => { e.preventDefault(); setPage(Math.max(1, page - 1)); }} className={page <= 1 ? "pointer-events-none opacity-50" : ""} />
                      </PaginationItem>
                      {Array.from({ length: Math.min(5, data.pages) }, (_, i) => {
                        const pageNum = Math.max(1, Math.min(data.pages - 4, page - 2)) + i;
                        if (pageNum > data.pages) return null;
                        return (
                          <PaginationItem key={pageNum}>
                            <PaginationLink href="#" isActive={pageNum === page} onClick={(e) => { e.preventDefault(); setPage(pageNum); }}>{pageNum}</PaginationLink>
                          </PaginationItem>
                        );
                      })}
                      <PaginationItem>
                        <PaginationNext href="#" onClick={(e) => { e.preventDefault(); setPage(Math.min(data.pages, page + 1)); }} className={page >= data.pages ? "pointer-events-none opacity-50" : ""} />
                      </PaginationItem>
                    </PaginationContent>
                  </Pagination>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={handleCloseDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingUser ? "Editar Colaborador" : "Novo Colaborador"}</DialogTitle>
            <DialogDescription>Preencha os dados do colaborador abaixo</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2 space-y-2">
                <Label htmlFor="nome">Nome Completo *</Label>
                <Input id="nome" {...register("nome")} />
                {errors.nome && <p className="text-sm text-destructive">{errors.nome.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email *</Label>
                <Input id="email" type="email" {...register("email")} disabled={!!editingUser} />
                {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="cpf">CPF *</Label>
                <Input id="cpf" placeholder="000.000.000-00" {...register("cpf")} disabled={!!editingUser} />
                {errors.cpf && <p className="text-sm text-destructive">{errors.cpf.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="matricula">Matrícula *</Label>
                <Input id="matricula" {...register("matricula")} disabled={!!editingUser} />
                {errors.matricula && <p className="text-sm text-destructive">{errors.matricula.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="telefone">Telefone</Label>
                <Input id="telefone" placeholder="(00) 00000-0000" {...register("telefone")} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="papel">Permissão *</Label>
                <Select value={watch("papel")} onValueChange={(value) => setValue("papel", value as UsuarioForm["papel"])}>
                  <SelectTrigger><SelectValue placeholder="Selecione..." /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="colaborador">Colaborador</SelectItem>
                    <SelectItem value="gestor">Gestor</SelectItem>
                    <SelectItem value="admin_dp">Admin DP</SelectItem>
                    <SelectItem value="auditor">Auditor</SelectItem>
                    <SelectItem value="financeiro">Financeiro</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="equipe_id">Equipe</Label>
                <Select value={watch("equipe_id") || "none"} onValueChange={(value) => setValue("equipe_id", value === "none" ? "" : value)}>
                  <SelectTrigger><SelectValue placeholder="Selecione..." /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Nenhuma</SelectItem>
                    {equipesData?.items.map((equipe) => (<SelectItem key={equipe.id} value={equipe.id}>{equipe.nome}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              {!editingUser && (
                <div className="col-span-2 space-y-2">
                  <Label htmlFor="password">Senha *</Label>
                  <div className="relative">
                    <Input id="password" type={showPassword ? "text" : "password"} {...register("password")} />
                    <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
                </div>
              )}
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => handleCloseDialog(false)}>Cancelar</Button>
              <Button type="submit" disabled={isPending}>
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingUser ? "Salvar" : "Criar"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar exclusão</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja remover <strong>{deletingUser?.nome}</strong>? Esta ação não pode ser desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={() => deletingUser && deleteMutation.mutate(deletingUser.id)} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {deleteMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
              Remover
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
