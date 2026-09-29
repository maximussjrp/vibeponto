"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/lib/api";
import { formatCoordinates } from "@/lib/utils";
import { locaisService } from "@/services";
import type { Perimetro, PerimetroCreate, PerimetroUpdate } from "@/services/locais";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Plus,
  MapPin,
  MoreHorizontal,
  Pencil,
  Trash2,
  Loader2,
  Circle,
  RefreshCw,
  Search,
  Navigation,
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const perimetroSchema = z.object({
  nome: z.string().min(3, "Nome deve ter pelo menos 3 caracteres"),
  endereco: z.string().optional(),
  cep: z.string().optional(),
  latitude: z.coerce.number().min(-90).max(90, "Latitude inválida"),
  longitude: z.coerce.number().min(-180).max(180, "Longitude inválida"),
  raio_metros: z.coerce.number().min(10, "Raio mínimo é 10 metros").max(10000, "Raio máximo é 10km"),
  tipo: z.enum(["circulo", "poligono"]),
  tolerancia_metros: z.coerce.number().min(0).max(100).optional(),
});

type PerimetroForm = z.infer<typeof perimetroSchema>;

export default function LocaisPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editingLocal, setEditingLocal] = useState<Perimetro | null>(null);
  const [deletingLocal, setDeletingLocal] = useState<Perimetro | null>(null);
  const [cepLoading, setCepLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("lista");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["perimetros", debouncedSearch],
    queryFn: () => locaisService.list({ q: debouncedSearch || undefined, per_page: 50 }),
  });

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<PerimetroForm>({
    resolver: zodResolver(perimetroSchema),
    defaultValues: { tipo: "circulo", raio_metros: 100, tolerancia_metros: 10 },
  });

  const createMutation = useMutation({
    mutationFn: (data: PerimetroCreate) => locaisService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["perimetros"] });
      toast.success("Perímetro criado com sucesso!");
      setDialogOpen(false);
      reset();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: PerimetroUpdate }) =>
      locaisService.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["perimetros"] });
      toast.success("Perímetro atualizado com sucesso!");
      setDialogOpen(false);
      setEditingLocal(null);
      reset();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => locaisService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["perimetros"] });
      toast.success("Perímetro removido com sucesso!");
      setDeleteDialogOpen(false);
      setDeletingLocal(null);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const activateMutation = useMutation({
    mutationFn: (id: string) => locaisService.activate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["perimetros"] });
      toast.success("Perímetro ativado!");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => locaisService.deactivate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["perimetros"] });
      toast.success("Perímetro desativado!");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const handleCepLookup = async () => {
    const cep = watch("cep");
    if (!cep || cep.length < 8) {
      toast.error("Digite um CEP válido");
      return;
    }
    setCepLoading(true);
    try {
      const result = await locaisService.lookupCep(cep.replace(/\D/g, ""));
      setValue("endereco", `${result.logradouro}, ${result.bairro} - ${result.cidade}/${result.uf}`);
      if (result.latitude && result.longitude) {
        setValue("latitude", result.latitude);
        setValue("longitude", result.longitude);
      }
      toast.success("Endereço encontrado!");
    } catch {
      toast.error("CEP não encontrado");
    } finally {
      setCepLoading(false);
    }
  };

  const handleGetLocation = () => {
    if (!navigator.geolocation) {
      toast.error("Geolocalização não suportada");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setValue("latitude", pos.coords.latitude);
        setValue("longitude", pos.coords.longitude);
        toast.success("Localização obtida!");
      },
      () => toast.error("Não foi possível obter localização")
    );
  };

  const onSubmit = (formData: PerimetroForm) => {
    const submitData = {
      ...formData,
      poligono_coords: formData.tipo === "circulo" ? undefined : [],
    };
    if (editingLocal) {
      updateMutation.mutate({ id: editingLocal.id, data: submitData });
    } else {
      createMutation.mutate(submitData);
    }
  };

  const handleEdit = (local: Perimetro) => {
    setEditingLocal(local);
    setValue("nome", local.nome);
    setValue("endereco", local.endereco || "");
    setValue("latitude", local.latitude);
    setValue("longitude", local.longitude);
    setValue("raio_metros", local.raio_metros);
    setValue("tipo", local.tipo as "circulo" | "poligono");
    setValue("tolerancia_metros", local.tolerancia_metros || 10);
    setDialogOpen(true);
  };

  const handleDelete = (local: Perimetro) => {
    setDeletingLocal(local);
    setDeleteDialogOpen(true);
  };

  const handleNewLocal = () => {
    setEditingLocal(null);
    reset({ tipo: "circulo", raio_metros: 100, tolerancia_metros: 10 });
    setDialogOpen(true);
  };

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Locais e Perímetros</h2>
          <p className="text-muted-foreground">
            Configure perímetros de geofencing para registro de ponto
            {data && ` • ${data.total} perímetros`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={handleNewLocal}>
            <Plus className="mr-2 h-4 w-4" />
            Novo Perímetro
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="lista">Lista</TabsTrigger>
          <TabsTrigger value="mapa">Mapa</TabsTrigger>
        </TabsList>

        <TabsContent value="lista" className="space-y-4">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Buscar local..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          {isError ? (
            <div className="text-center py-8">
              <p className="text-destructive mb-4">Erro ao carregar perímetros</p>
              <Button variant="outline" onClick={() => refetch()}>Tentar novamente</Button>
            </div>
          ) : isLoading ? (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nome</TableHead>
                    <TableHead>Endereço</TableHead>
                    <TableHead>Coordenadas</TableHead>
                    <TableHead>Raio</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-12" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Array(5).fill(0).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-48" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                      <TableCell><Skeleton className="h-6 w-16" /></TableCell>
                      <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          ) : data?.items?.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <MapPin className="h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground mb-4">Nenhum perímetro configurado</p>
                <Button onClick={handleNewLocal}>
                  <Plus className="mr-2 h-4 w-4" />
                  Criar primeiro perímetro
                </Button>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nome</TableHead>
                    <TableHead>Endereço</TableHead>
                    <TableHead>Coordenadas</TableHead>
                    <TableHead>Raio</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-12" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data?.items.map((local) => (
                    <TableRow key={local.id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <MapPin className="h-4 w-4 text-muted-foreground" />
                          {local.nome}
                        </div>
                      </TableCell>
                      <TableCell className="max-w-xs truncate">{local.endereco || "-"}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatCoordinates(local.latitude, local.longitude) || "-"}
                      </TableCell>
                      <TableCell>{local.raio_metros}m</TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          <Circle className="h-3 w-3 mr-1" />
                          {local.tipo === "circulo" ? "Círculo" : "Polígono"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={local.ativo ? "default" : "secondary"}>
                          {local.ativo ? "Ativo" : "Inativo"}
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
                            <DropdownMenuItem onClick={() => handleEdit(local)}>
                              <Pencil className="mr-2 h-4 w-4" />
                              Editar
                            </DropdownMenuItem>
                            {local.ativo ? (
                              <DropdownMenuItem onClick={() => deactivateMutation.mutate(local.id)}>
                                <XCircle className="mr-2 h-4 w-4" />
                                Desativar
                              </DropdownMenuItem>
                            ) : (
                              <DropdownMenuItem onClick={() => activateMutation.mutate(local.id)}>
                                <CheckCircle2 className="mr-2 h-4 w-4" />
                                Ativar
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => handleDelete(local)} className="text-destructive">
                              <Trash2 className="mr-2 h-4 w-4" />
                              Remover
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="mapa">
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <MapPin className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">
                Visualização de mapa disponível em breve
              </p>
              <p className="text-sm text-muted-foreground">
                Integração com Google Maps ou Leaflet
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) { setEditingLocal(null); reset(); } }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingLocal ? "Editar Perímetro" : "Novo Perímetro"}</DialogTitle>
            <DialogDescription>Configure um perímetro de geofencing</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="nome">Nome *</Label>
              <Input id="nome" {...register("nome")} placeholder="Ex: Sede Principal" />
              {errors.nome && <p className="text-sm text-destructive">{errors.nome.message}</p>}
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-2 space-y-2">
                <Label htmlFor="cep">CEP</Label>
                <Input id="cep" {...register("cep")} placeholder="00000-000" />
              </div>
              <div className="flex items-end">
                <Button type="button" variant="outline" onClick={handleCepLookup} disabled={cepLoading} className="w-full">
                  {cepLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Buscar"}
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="endereco">Endereço</Label>
              <Input id="endereco" {...register("endereco")} placeholder="Rua, Número - Bairro" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="latitude">Latitude *</Label>
                <Input id="latitude" type="number" step="any" {...register("latitude")} />
                {errors.latitude && <p className="text-sm text-destructive">{errors.latitude.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="longitude">Longitude *</Label>
                <Input id="longitude" type="number" step="any" {...register("longitude")} />
                {errors.longitude && <p className="text-sm text-destructive">{errors.longitude.message}</p>}
              </div>
            </div>

            <Button type="button" variant="outline" onClick={handleGetLocation} className="w-full">
              <Navigation className="mr-2 h-4 w-4" />
              Usar minha localização atual
            </Button>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="tipo">Tipo</Label>
                <Select value={watch("tipo")} onValueChange={(v) => setValue("tipo", v as "circulo" | "poligono")}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="circulo">Círculo</SelectItem>
                    <SelectItem value="poligono">Polígono</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="raio_metros">Raio (metros) *</Label>
                <Input id="raio_metros" type="number" {...register("raio_metros")} />
                {errors.raio_metros && <p className="text-sm text-destructive">{errors.raio_metros.message}</p>}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="tolerancia_metros">Tolerância (metros)</Label>
              <Input id="tolerancia_metros" type="number" {...register("tolerancia_metros")} />
              <p className="text-xs text-muted-foreground">Margem extra permitida além do raio</p>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
              <Button type="submit" disabled={isPending}>
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingLocal ? "Salvar" : "Criar"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar exclusão</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja remover o perímetro <strong>{deletingLocal?.nome}</strong>?
              Esta ação não pode ser desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deletingLocal && deleteMutation.mutate(deletingLocal.id)}
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
