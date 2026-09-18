"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/lib/api";
import { documentosService, usuariosService } from "@/services";
import type { Documento, DocumentoTipo, DocumentoStatus } from "@/services/documentos";
import { formatDate, getInitials } from "@/lib/utils";
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
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  Plus,
  Search,
  RefreshCw,
  Filter,
  Loader2,
  FileText,
  Download,
  Trash2,
  Eye,
  CheckCircle2,
  XCircle,
  Upload,
  File,
  FileImage,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const STATUS_COLORS: Record<DocumentoStatus, "default" | "secondary" | "destructive" | "outline"> = {
  pendente: "secondary",
  aprovado: "default",
  rejeitado: "destructive",
};

const STATUS_LABELS: Record<DocumentoStatus, string> = {
  pendente: "Pendente",
  aprovado: "Aprovado",
  rejeitado: "Rejeitado",
};

const TIPO_LABELS: Record<DocumentoTipo, string> = {
  atestado: "Atestado Médico",
  declaracao: "Declaração",
  comprovante: "Comprovante",
  contrato: "Contrato",
  termo: "Termo",
  outro: "Outro",
  outros: "Outros",
};

const uploadSchema = z.object({
  usuario_id: z.string().min(1, "Selecione um colaborador"),
  tipo: z.enum(["atestado", "declaracao", "comprovante", "contrato", "outro"]),
  descricao: z.string().optional(),
  data_referencia: z.string().optional(),
});

type UploadForm = z.infer<typeof uploadSchema>;

export default function DocumentosPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<DocumentoStatus | "all">("all");
  const [tipoFilter, setTipoFilter] = useState<DocumentoTipo | "all">("all");
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<Documento | null>(null);
  const [deletingDoc, setDeletingDoc] = useState<Documento | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["documentos", statusFilter, tipoFilter, page, debouncedSearch],
    queryFn: () => documentosService.list({
      status: statusFilter === "all" ? undefined : statusFilter,
      tipo: tipoFilter === "all" ? undefined : tipoFilter,
      q: debouncedSearch || undefined,
      page,
      per_page: 20,
    }),
  });

  const { data: usuariosData } = useQuery({
    queryKey: ["usuarios-docs"],
    queryFn: () => usuariosService.list({ per_page: 100 }),
  });

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<UploadForm>({
    resolver: zodResolver(uploadSchema),
    defaultValues: { tipo: "atestado" },
  });

  const uploadMutation = useMutation({
    mutationFn: async (formData: UploadForm) => {
      if (!selectedFile) throw new Error("Selecione um arquivo");
      return documentosService.upload(selectedFile, {
        ...formData,
        data_referencia: formData.data_referencia || undefined,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documentos"] });
      toast.success("Documento enviado com sucesso!");
      setUploadDialogOpen(false);
      setSelectedFile(null);
      reset();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => documentosService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documentos"] });
      toast.success("Documento removido!");
      setDeleteDialogOpen(false);
      setDeletingDoc(null);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const aprovarMutation = useMutation({
    mutationFn: (id: string) => documentosService.aprovar(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documentos"] });
      toast.success("Documento aprovado!");
      setReviewDialogOpen(false);
      setSelectedDoc(null);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const rejeitarMutation = useMutation({
    mutationFn: ({ id, motivo }: { id: string; motivo: string }) =>
      documentosService.rejeitar(id, motivo),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documentos"] });
      toast.success("Documento rejeitado");
      setReviewDialogOpen(false);
      setSelectedDoc(null);
      setRejectReason("");
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const handleDownload = async (doc: Documento) => {
    try {
      const blob = await documentosService.download(doc.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = doc.nome_arquivo;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 10 * 1024 * 1024) {
        toast.error("Arquivo muito grande. Máximo 10MB");
        return;
      }
      setSelectedFile(file);
    }
  };

  const handleReview = (doc: Documento) => {
    setSelectedDoc(doc);
    setReviewDialogOpen(true);
  };

  const handleDelete = (doc: Documento) => {
    setDeletingDoc(doc);
    setDeleteDialogOpen(true);
  };

  const getFileIcon = (mimeType: string) => {
    if (mimeType.includes("pdf")) return <FileText className="h-5 w-5 text-red-500" />;
    if (mimeType.includes("image")) return <FileImage className="h-5 w-5 text-blue-500" />;
    return <File className="h-5 w-5 text-gray-500" />;
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Documentos</h2>
          <p className="text-muted-foreground">
            Gerencie atestados, declarações e outros documentos
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={() => setUploadDialogOpen(true)}>
            <Upload className="mr-2 h-4 w-4" />
            Enviar Documento
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as DocumentoStatus | "all")}>
          <SelectTrigger className="w-40">
            <Filter className="h-4 w-4 mr-2" />
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos Status</SelectItem>
            <SelectItem value="pendente">Pendente</SelectItem>
            <SelectItem value="aprovado">Aprovado</SelectItem>
            <SelectItem value="rejeitado">Rejeitado</SelectItem>
          </SelectContent>
        </Select>
        <Select value={tipoFilter} onValueChange={(v) => setTipoFilter(v as DocumentoTipo | "all")}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Tipo" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos Tipos</SelectItem>
            <SelectItem value="atestado">Atestado Médico</SelectItem>
            <SelectItem value="declaracao">Declaração</SelectItem>
            <SelectItem value="comprovante">Comprovante</SelectItem>
            <SelectItem value="contrato">Contrato</SelectItem>
            <SelectItem value="outro">Outro</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Documents Table */}
      {isError ? (
        <div className="text-center py-8">
          <p className="text-destructive mb-4">Erro ao carregar documentos</p>
          <Button variant="outline" onClick={() => refetch()}>Tentar novamente</Button>
        </div>
      ) : isLoading ? (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Arquivo</TableHead>
                <TableHead>Colaborador</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Data</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array(5).fill(0).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-8 w-48" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-40" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-24" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      ) : !data?.items?.length ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FileText className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground mb-4">Nenhum documento encontrado</p>
            <Button onClick={() => setUploadDialogOpen(true)}>
              <Upload className="mr-2 h-4 w-4" />
              Enviar primeiro documento
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Arquivo</TableHead>
                <TableHead>Colaborador</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Data Ref.</TableHead>
                <TableHead>Enviado em</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-32">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((doc: Documento) => (
                <TableRow key={doc.id}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      {getFileIcon(doc.mime_type)}
                      <div>
                        <p className="font-medium truncate max-w-[200px]">{doc.nome_arquivo}</p>
                        <p className="text-xs text-muted-foreground">{formatFileSize(doc.tamanho)}</p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Avatar className="h-7 w-7">
                        <AvatarImage src={doc.usuario?.foto_url} />
                        <AvatarFallback className="text-xs">{getInitials(doc.usuario?.nome || "")}</AvatarFallback>
                      </Avatar>
                      <span className="text-sm">{doc.usuario?.nome || "N/A"}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{TIPO_LABELS[doc.tipo]}</Badge>
                  </TableCell>
                  <TableCell>{doc.data_referencia ? formatDate(new Date(doc.data_referencia)) : "-"}</TableCell>
                  <TableCell>{formatDate(new Date(doc.created_at))}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_COLORS[doc.status]}>
                      {STATUS_LABELS[doc.status]}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" onClick={() => handleDownload(doc)} title="Baixar">
                        <Download className="h-4 w-4" />
                      </Button>
                      {doc.status === "pendente" && (
                        <Button variant="ghost" size="icon" onClick={() => handleReview(doc)} title="Revisar">
                          <Eye className="h-4 w-4" />
                        </Button>
                      )}
                      <Button variant="ghost" size="icon" onClick={() => handleDelete(doc)} title="Remover" className="text-destructive">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
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

      {/* Upload Dialog */}
      <Dialog open={uploadDialogOpen} onOpenChange={(open) => { setUploadDialogOpen(open); if (!open) { setSelectedFile(null); reset(); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Enviar Documento</DialogTitle>
            <DialogDescription>Faça upload de um documento</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit((data) => uploadMutation.mutate(data))} className="space-y-4">
            <div className="space-y-2">
              <Label>Arquivo *</Label>
              <div
                className="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer hover:border-primary transition-colors"
                onClick={() => fileInputRef.current?.click()}
              >
                {selectedFile ? (
                  <div className="flex items-center justify-center gap-2">
                    <File className="h-8 w-8 text-muted-foreground" />
                    <div className="text-left">
                      <p className="font-medium">{selectedFile.name}</p>
                      <p className="text-sm text-muted-foreground">{formatFileSize(selectedFile.size)}</p>
                    </div>
                  </div>
                ) : (
                  <>
                    <Upload className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                    <p className="text-sm text-muted-foreground">Clique para selecionar ou arraste um arquivo</p>
                    <p className="text-xs text-muted-foreground mt-1">PDF, imagens (máx. 10MB)</p>
                  </>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={handleFileChange}
                className="hidden"
              />
            </div>

            <div className="space-y-2">
              <Label>Colaborador *</Label>
              <Select value={watch("usuario_id") || ""} onValueChange={(v) => setValue("usuario_id", v)}>
                <SelectTrigger><SelectValue placeholder="Selecione..." /></SelectTrigger>
                <SelectContent>
                  {usuariosData?.items.map((u) => (
                    <SelectItem key={u.id} value={u.id}>{u.nome}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.usuario_id && <p className="text-sm text-destructive">{errors.usuario_id.message}</p>}
            </div>

            <div className="space-y-2">
              <Label>Tipo *</Label>
              <Select value={watch("tipo")} onValueChange={(v) => setValue("tipo", v as any)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="atestado">Atestado Médico</SelectItem>
                  <SelectItem value="declaracao">Declaração</SelectItem>
                  <SelectItem value="comprovante">Comprovante</SelectItem>
                  <SelectItem value="contrato">Contrato</SelectItem>
                  <SelectItem value="outro">Outro</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Data de Referência</Label>
              <Input type="date" {...register("data_referencia")} />
            </div>

            <div className="space-y-2">
              <Label>Descrição</Label>
              <Textarea {...register("descricao")} placeholder="Descrição opcional..." />
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setUploadDialogOpen(false)}>Cancelar</Button>
              <Button type="submit" disabled={uploadMutation.isPending || !selectedFile}>
                {uploadMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Enviar
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Review Dialog */}
      <Dialog open={reviewDialogOpen} onOpenChange={(open) => { setReviewDialogOpen(open); if (!open) { setSelectedDoc(null); setRejectReason(""); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Revisar Documento</DialogTitle>
            <DialogDescription>Aprove ou rejeite o documento</DialogDescription>
          </DialogHeader>
          {selectedDoc && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Arquivo</p>
                  <p className="font-medium">{selectedDoc.nome_arquivo}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Tipo</p>
                  <p className="font-medium">{TIPO_LABELS[selectedDoc.tipo]}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Colaborador</p>
                  <p className="font-medium">{selectedDoc.usuario?.nome}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Data Ref.</p>
                  <p className="font-medium">{selectedDoc.data_referencia ? formatDate(new Date(selectedDoc.data_referencia)) : "N/A"}</p>
                </div>
              </div>

              {selectedDoc.descricao && (
                <div>
                  <p className="text-muted-foreground text-sm">Descrição</p>
                  <p className="mt-1 p-3 bg-muted rounded-md text-sm">{selectedDoc.descricao}</p>
                </div>
              )}

              <div className="flex justify-center">
                <Button variant="outline" onClick={() => handleDownload(selectedDoc)}>
                  <Download className="mr-2 h-4 w-4" />
                  Visualizar/Baixar Arquivo
                </Button>
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
              onClick={() => selectedDoc && rejeitarMutation.mutate({ id: selectedDoc.id, motivo: rejectReason })}
              disabled={rejeitarMutation.isPending}
            >
              {rejeitarMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <XCircle className="mr-2 h-4 w-4" />}
              Rejeitar
            </Button>
            <Button
              onClick={() => selectedDoc && aprovarMutation.mutate(selectedDoc.id)}
              disabled={aprovarMutation.isPending}
            >
              {aprovarMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
              Aprovar
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
              Tem certeza que deseja remover o documento <strong>{deletingDoc?.nome_arquivo}</strong>?
              Esta ação não pode ser desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deletingDoc && deleteMutation.mutate(deletingDoc.id)}
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
