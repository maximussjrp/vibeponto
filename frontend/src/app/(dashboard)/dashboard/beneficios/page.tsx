"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/lib/api";
import { beneficiosService, usuariosService } from "@/services";
import type { Beneficio, BeneficioCreate, BeneficioUpdate, Atribuicao } from "@/services/beneficios";
import { formatDate, getInitials, formatCurrency } from "@/lib/utils";
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
import { Switch } from "@/components/ui/switch";
import {
  Plus,
  Search,
  RefreshCw,
  Loader2,
  Gift,
  Pencil,
  Trash2,
  MoreHorizontal,
  Users,
  UserPlus,
  Wallet,
  CreditCard,
  HeartPulse,
  UtensilsCrossed,
  Car,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const beneficioSchema = z.object({
  nome: z.string().min(2, "Nome deve ter pelo menos 2 caracteres"),
  tipo: z.enum(["vale_refeicao", "vale_alimentacao", "vale_transporte", "plano_saude", "outros"]),
  descricao: z.string().optional(),
  valor_padrao: z.coerce.number().min(0).optional(),
  ativo: z.boolean().default(true),
});

type BeneficioForm = z.infer<typeof beneficioSchema>;

const TIPO_ICONS: Record<string, any> = {
  vale_refeicao: UtensilsCrossed,
  vale_alimentacao: Wallet,
  vale_transporte: Car,
  plano_saude: HeartPulse,
  outros: Gift,
};

const TIPO_LABELS: Record<string, string> = {
  vale_refeicao: "Vale Refeição",
  vale_alimentacao: "Vale Alimentação",
  vale_transporte: "Vale Transporte",
  plano_saude: "Plano de Saúde",
  outros: "Outros",
};

export default function BeneficiosPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("beneficios");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [atribuirDialogOpen, setAtribuirDialogOpen] = useState(false);
  const [editingBeneficio, setEditingBeneficio] = useState<Beneficio | null>(null);
  const [deletingBeneficio, setDeletingBeneficio] = useState<Beneficio | null>(null);
  const [selectedBeneficio, setSelectedBeneficio] = useState<Beneficio | null>(null);
  const [selectedUsuarios, setSelectedUsuarios] = useState<string[]>([]);
  const [valorAtribuicao, setValorAtribuicao] = useState<string>("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const { data: beneficiosData, isLoading: loadingBeneficios, refetch: refetchBeneficios } = useQuery({
    queryKey: ["beneficios", debouncedSearch],
    queryFn: () => beneficiosService.list({ q: debouncedSearch || undefined, per_page: 50 }),
  });

  const { data: atribuicoesData, isLoading: loadingAtribuicoes, refetch: refetchAtribuicoes } = useQuery({
    queryKey: ["atribuicoes"],
    queryFn: () => beneficiosService.listAtribuicoes({ per_page: 100 }),
    enabled: activeTab === "atribuicoes",
  });

  const { data: usuariosData } = useQuery({
    queryKey: ["usuarios-beneficios"],
    queryFn: () => usuariosService.list({ per_page: 100 }),
  });

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<BeneficioForm>({
    resolver: zodResolver(beneficioSchema),
    defaultValues: { ativo: true, tipo: "vale_refeicao" },
  });

  const createMutation = useMutation({
    mutationFn: (data: BeneficioCreate) => beneficiosService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["beneficios"] });
      toast.success("Benefício criado com sucesso!");
      setDialogOpen(false);
      reset();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: BeneficioUpdate }) =>
      beneficiosService.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["beneficios"] });
      toast.success("Benefício atualizado!");
      setDialogOpen(false);
      setEditingBeneficio(null);
      reset();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => beneficiosService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["beneficios"] });
      toast.success("Benefício removido!");
      setDeleteDialogOpen(false);
      setDeletingBeneficio(null);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const atribuirMutation = useMutation({
    mutationFn: ({ beneficioId, usuarioIds, valor }: { beneficioId: string; usuarioIds: string[]; valor?: number }) =>
      Promise.all(usuarioIds.map(usuarioId =>
        beneficiosService.atribuir({ beneficio_id: beneficioId, usuario_id: usuarioId, valor })
      )),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["atribuicoes"] });
      toast.success("Benefício atribuído com sucesso!");
      setAtribuirDialogOpen(false);
      setSelectedBeneficio(null);
      setSelectedUsuarios([]);
      setValorAtribuicao("");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const removerAtribuicaoMutation = useMutation({
    mutationFn: (id: string) => beneficiosService.removerAtribuicao(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["atribuicoes"] });
      toast.success("Atribuição removida!");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const onSubmit = (formData: BeneficioForm) => {
    if (editingBeneficio) {
      updateMutation.mutate({ id: editingBeneficio.id, data: formData });
    } else {
      createMutation.mutate(formData);
    }
  };

  const handleEdit = (beneficio: Beneficio) => {
    setEditingBeneficio(beneficio);
    setValue("nome", beneficio.nome);
    setValue("tipo", beneficio.tipo as any);
    setValue("descricao", beneficio.descricao || "");
    setValue("valor_padrao", beneficio.valor_padrao || 0);
    setValue("ativo", beneficio.ativo);
    setDialogOpen(true);
  };

  const handleDelete = (beneficio: Beneficio) => {
    setDeletingBeneficio(beneficio);
    setDeleteDialogOpen(true);
  };

  const handleAtribuir = (beneficio: Beneficio) => {
    setSelectedBeneficio(beneficio);
    setValorAtribuicao(beneficio.valor_padrao?.toString() || "");
    setAtribuirDialogOpen(true);
  };

  const handleNewBeneficio = () => {
    setEditingBeneficio(null);
    reset({ ativo: true, tipo: "vale_refeicao" });
    setDialogOpen(true);
  };

  const renderIcon = (tipo: string) => {
    const Icon = TIPO_ICONS[tipo] || Gift;
    return <Icon className="h-5 w-5" />;
  };

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Benefícios</h2>
          <p className="text-muted-foreground">
            Gerencie os benefícios dos colaboradores
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => activeTab === "beneficios" ? refetchBeneficios() : refetchAtribuicoes()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={handleNewBeneficio}>
            <Plus className="mr-2 h-4 w-4" />
            Novo Benefício
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="beneficios">Benefícios</TabsTrigger>
          <TabsTrigger value="atribuicoes">Atribuições</TabsTrigger>
        </TabsList>

        <TabsContent value="beneficios" className="space-y-4">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Buscar benefício..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          {loadingBeneficios ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {Array(6).fill(0).map((_, i) => (
                <Card key={i}>
                  <CardHeader>
                    <Skeleton className="h-6 w-32" />
                    <Skeleton className="h-4 w-48" />
                  </CardHeader>
                  <CardContent>
                    <Skeleton className="h-12 w-full" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : !beneficiosData?.items?.length ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Gift className="h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground mb-4">Nenhum benefício cadastrado</p>
                <Button onClick={handleNewBeneficio}>
                  <Plus className="mr-2 h-4 w-4" />
                  Criar primeiro benefício
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {beneficiosData.items.map((beneficio) => (
                <Card key={beneficio.id}>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-primary/10 text-primary">
                          {renderIcon(beneficio.tipo)}
                        </div>
                        <div>
                          <CardTitle className="text-lg flex items-center gap-2">
                            {beneficio.nome}
                            {!beneficio.ativo && <Badge variant="secondary">Inativo</Badge>}
                          </CardTitle>
                          <CardDescription>{TIPO_LABELS[beneficio.tipo]}</CardDescription>
                        </div>
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
                          <DropdownMenuItem onClick={() => handleAtribuir(beneficio)}>
                            <UserPlus className="mr-2 h-4 w-4" />
                            Atribuir
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleEdit(beneficio)}>
                            <Pencil className="mr-2 h-4 w-4" />
                            Editar
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onClick={() => handleDelete(beneficio)} className="text-destructive">
                            <Trash2 className="mr-2 h-4 w-4" />
                            Remover
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {beneficio.descricao && (
                        <p className="text-sm text-muted-foreground">{beneficio.descricao}</p>
                      )}
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Valor padrão:</span>
                        <span className="font-semibold">{formatCurrency(beneficio.valor_padrao || 0)}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Users className="h-4 w-4" />
                        <span>{beneficio.total_atribuicoes || 0} colaboradores</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="atribuicoes" className="space-y-4">
          {loadingAtribuicoes ? (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Colaborador</TableHead>
                    <TableHead>Benefício</TableHead>
                    <TableHead>Valor</TableHead>
                    <TableHead>Desde</TableHead>
                    <TableHead>Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Array(5).fill(0).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell><Skeleton className="h-8 w-40" /></TableCell>
                      <TableCell><Skeleton className="h-6 w-32" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                      <TableCell><Skeleton className="h-8 w-20" /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          ) : !atribuicoesData?.items?.length ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Users className="h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground">Nenhuma atribuição encontrada</p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Colaborador</TableHead>
                    <TableHead>Benefício</TableHead>
                    <TableHead>Valor</TableHead>
                    <TableHead>Desde</TableHead>
                    <TableHead className="w-24">Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {atribuicoesData.items.map((atribuicao) => (
                    <TableRow key={atribuicao.id}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar className="h-8 w-8">
                            <AvatarImage src={atribuicao.usuario?.foto_url} />
                            <AvatarFallback>{getInitials(atribuicao.usuario?.nome || "")}</AvatarFallback>
                          </Avatar>
                          <span className="font-medium">{atribuicao.usuario?.nome || "N/A"}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {renderIcon(atribuicao.beneficio?.tipo || "")}
                          <span>{atribuicao.beneficio?.nome || "N/A"}</span>
                        </div>
                      </TableCell>
                      <TableCell className="font-medium">{formatCurrency(atribuicao.valor || 0)}</TableCell>
                      <TableCell>{formatDate(new Date(atribuicao.created_at))}</TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removerAtribuicaoMutation.mutate(atribuicao.id)}
                          disabled={removerAtribuicaoMutation.isPending}
                          className="text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) { setEditingBeneficio(null); reset(); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingBeneficio ? "Editar Benefício" : "Novo Benefício"}</DialogTitle>
            <DialogDescription>Preencha os dados do benefício</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label>Nome *</Label>
              <Input {...register("nome")} placeholder="Ex: VR Mensal" />
              {errors.nome && <p className="text-sm text-destructive">{errors.nome.message}</p>}
            </div>

            <div className="space-y-2">
              <Label>Tipo *</Label>
              <Select value={watch("tipo")} onValueChange={(v) => setValue("tipo", v as any)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="vale_refeicao">Vale Refeição</SelectItem>
                  <SelectItem value="vale_alimentacao">Vale Alimentação</SelectItem>
                  <SelectItem value="vale_transporte">Vale Transporte</SelectItem>
                  <SelectItem value="plano_saude">Plano de Saúde</SelectItem>
                  <SelectItem value="outros">Outros</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Descrição</Label>
              <Textarea {...register("descricao")} placeholder="Descrição do benefício..." />
            </div>

            <div className="space-y-2">
              <Label>Valor Padrão (R$)</Label>
              <Input type="number" step="0.01" {...register("valor_padrao")} placeholder="0.00" />
            </div>

            <div className="flex items-center justify-between">
              <Label htmlFor="ativo">Ativo</Label>
              <Switch
                id="ativo"
                checked={watch("ativo")}
                onCheckedChange={(v) => setValue("ativo", v)}
              />
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
              <Button type="submit" disabled={isPending}>
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingBeneficio ? "Salvar" : "Criar"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Atribuir Dialog */}
      <Dialog open={atribuirDialogOpen} onOpenChange={(open) => { setAtribuirDialogOpen(open); if (!open) { setSelectedBeneficio(null); setSelectedUsuarios([]); setValorAtribuicao(""); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Atribuir Benefício</DialogTitle>
            <DialogDescription>
              Atribuir {selectedBeneficio?.nome} aos colaboradores selecionados
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Colaboradores *</Label>
              <div className="max-h-48 overflow-y-auto border rounded-md p-2 space-y-1">
                {usuariosData?.items.map((u) => (
                  <label key={u.id} className="flex items-center gap-2 p-2 hover:bg-muted rounded cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedUsuarios.includes(u.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedUsuarios([...selectedUsuarios, u.id]);
                        } else {
                          setSelectedUsuarios(selectedUsuarios.filter(id => id !== u.id));
                        }
                      }}
                      className="rounded"
                    />
                    <Avatar className="h-6 w-6">
                      <AvatarFallback className="text-xs">{getInitials(u.nome)}</AvatarFallback>
                    </Avatar>
                    <span className="text-sm">{u.nome}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">{selectedUsuarios.length} selecionado(s)</p>
            </div>

            <div className="space-y-2">
              <Label>Valor (R$)</Label>
              <Input
                type="number"
                step="0.01"
                value={valorAtribuicao}
                onChange={(e) => setValorAtribuicao(e.target.value)}
                placeholder={selectedBeneficio?.valor_padrao?.toString() || "0.00"}
              />
              <p className="text-xs text-muted-foreground">Deixe em branco para usar o valor padrão</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAtribuirDialogOpen(false)}>Cancelar</Button>
            <Button
              onClick={() => selectedBeneficio && atribuirMutation.mutate({
                beneficioId: selectedBeneficio.id,
                usuarioIds: selectedUsuarios,
                valor: valorAtribuicao ? parseFloat(valorAtribuicao) : undefined,
              })}
              disabled={atribuirMutation.isPending || selectedUsuarios.length === 0}
            >
              {atribuirMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Atribuir
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
              Tem certeza que deseja remover o benefício <strong>{deletingBeneficio?.nome}</strong>?
              Todas as atribuições serão removidas.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deletingBeneficio && deleteMutation.mutate(deletingBeneficio.id)}
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
