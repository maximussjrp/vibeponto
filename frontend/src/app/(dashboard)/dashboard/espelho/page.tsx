"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/lib/api";
import { espelhoService, usuariosService, equipesService } from "@/services";
import { usePermissions } from "@/hooks/usePermissions";
import type { EspelhoPonto, EspelhoFilters } from "@/services/espelho";
import { formatDate, formatTime, getInitials } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
  Calendar,
  Download,
  FileSpreadsheet,
  FileText,
  Search,
  RefreshCw,
  Clock,
  AlertTriangle,
  Filter,
  Loader2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

export default function EspelhoPage() {
  const { role } = usePermissions();
  const isColaborador = role === "colaborador";
  
  const [usuarioId, setUsuarioId] = useState<string>("");
  const [equipeId, setEquipeId] = useState<string>("");
  const [mesAno, setMesAno] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });
  const [exportingPdf, setExportingPdf] = useState(false);
  const [exportingExcel, setExportingExcel] = useState(false);

  // Parse mes/ano
  const [ano, mes] = mesAno.split("-").map(Number);

  const filters: EspelhoFilters = {
    mes,
    ano,
    usuario_id: usuarioId && usuarioId !== "all" ? usuarioId : undefined,
    equipe_id: equipeId && equipeId !== "all" ? equipeId : undefined,
  };

  const { data: espelhoData, isLoading, isError, refetch } = useQuery({
    queryKey: ["espelho", filters],
    queryFn: () => espelhoService.getEspelho(filters),
  });

  const { data: usuariosData } = useQuery({
    queryKey: ["usuarios-espelho"],
    queryFn: () => usuariosService.list({ per_page: 100 }),
  });

  const { data: equipesData } = useQuery({
    queryKey: ["equipes-espelho"],
    queryFn: () => equipesService.list({ per_page: 50 }),
  });

  const handlePrevMonth = () => {
    const date = new Date(ano, mes - 1, 1);
    date.setMonth(date.getMonth() - 1);
    setMesAno(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`);
  };

  const handleNextMonth = () => {
    const date = new Date(ano, mes - 1, 1);
    date.setMonth(date.getMonth() + 1);
    setMesAno(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`);
  };

  const handleExportPdf = async () => {
    if (!usuarioId || usuarioId === "all") {
      toast.error("Selecione um colaborador para exportar");
      return;
    }
    setExportingPdf(true);
    try {
      const blob = await espelhoService.exportPdf({ ...filters, usuario_id: usuarioId });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `espelho-ponto-${mesAno}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("PDF exportado com sucesso!");
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setExportingPdf(false);
    }
  };

  const handleExportExcel = async () => {
    setExportingExcel(true);
    try {
      const blob = await espelhoService.exportExcel(filters);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `espelho-ponto-${mesAno}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Excel exportado com sucesso!");
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setExportingExcel(false);
    }
  };

  const formatHoras = (value: number | string | undefined | null) => {
    if (value === undefined || value === null) return "0h";
    if (typeof value === "string") return value; // já formatado "08:30"
    const minutos = Number(value);
    if (isNaN(minutos)) return "0h";
    const h = Math.floor(minutos / 60);
    const m = minutos % 60;
    return `${h}h${m > 0 ? ` ${m}m` : ""}`;
  };

  const getNomeMes = (m: number) => {
    const meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
    return meses[m - 1];
  };

  // Extrair o primeiro espelho da lista (ou undefined se não houver)
  const espelho = espelhoData?.items?.[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Espelho de Ponto</h2>
          <p className="text-muted-foreground">
            Visualize e exporte o espelho de ponto dos colaboradores
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button variant="outline" onClick={handleExportExcel} disabled={exportingExcel}>
            {exportingExcel ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileSpreadsheet className="mr-2 h-4 w-4" />}
            Excel
          </Button>
          <Button onClick={handleExportPdf} disabled={exportingPdf || !usuarioId}>
            {exportingPdf ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileText className="mr-2 h-4 w-4" />}
            PDF
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-4 items-end">
            <div className="flex items-center gap-2">
              <Button variant="outline" size="icon" onClick={handlePrevMonth}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <div className="text-center min-w-[150px]">
                <p className="text-lg font-semibold">{getNomeMes(mes)} {ano}</p>
              </div>
              <Button variant="outline" size="icon" onClick={handleNextMonth}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>

            {!isColaborador && (
              <>
                <div className="flex-1 max-w-xs">
                  <Label className="text-sm text-muted-foreground">Colaborador</Label>
                  <Select value={usuarioId || "all"} onValueChange={setUsuarioId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Todos" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Todos</SelectItem>
                      {usuariosData?.items?.map((u) => (
                        <SelectItem key={u.id} value={u.id}>{u.nome}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex-1 max-w-xs">
                  <Label className="text-sm text-muted-foreground">Equipe</Label>
                  <Select value={equipeId || "all"} onValueChange={setEquipeId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Todas" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Todas</SelectItem>
                      {equipesData?.items?.map((e) => (
                        <SelectItem key={e.id} value={e.id}>{e.nome}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Summary Cards */}
      {espelho && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Horas Trabalhadas</CardDescription>
              <CardTitle className="text-2xl">{formatHoras(espelho.total_horas_trabalhadas)}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Horas Extras</CardDescription>
              <CardTitle className="text-2xl text-green-600">{formatHoras(espelho.total_horas_extras)}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Horas Faltantes</CardDescription>
              <CardTitle className="text-2xl text-red-600">{formatHoras(espelho.total_horas_falta)}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Dias Trabalhados</CardDescription>
              <CardTitle className="text-2xl">{espelho.total_dias_trabalhados || 0} dias</CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* Espelho Table */}
      {isError ? (
        <div className="text-center py-8">
          <p className="text-destructive mb-4">Erro ao carregar espelho de ponto</p>
          <Button variant="outline" onClick={() => refetch()}>Tentar novamente</Button>
        </div>
      ) : isLoading ? (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Data</TableHead>
                <TableHead>Entrada</TableHead>
                <TableHead>Saída Almoço</TableHead>
                <TableHead>Retorno</TableHead>
                <TableHead>Saída</TableHead>
                <TableHead>Total</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array(10).fill(0).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      ) : !espelho?.dias?.length ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Calendar className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">Nenhum registro encontrado para este período</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Espelho de {espelho.usuario_nome}</CardTitle>
            <CardDescription>Matrícula: {espelho.usuario_matricula || "-"}</CardDescription>
          </CardHeader>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Data</TableHead>
                <TableHead>Entrada</TableHead>
                <TableHead>Pausa</TableHead>
                <TableHead>Retorno</TableHead>
                <TableHead>Saída</TableHead>
                <TableHead>Total</TableHead>
                <TableHead>Observações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {espelho.dias.map((dia, idx) => {
                // Extrair marcações por tipo de evento
                const marcacoes = dia.marcacoes || [];
                const entrada = marcacoes.find((m: any) => m.evento === "entrada" || m.evento === "ENTRADA");
                const pausa = marcacoes.find((m: any) => m.evento === "pausa_inicio" || m.evento === "PAUSA_INICIO");
                const retorno = marcacoes.find((m: any) => m.evento === "pausa_fim" || m.evento === "PAUSA_FIM");
                const saida = marcacoes.find((m: any) => m.evento === "saida" || m.evento === "SAIDA");
                
                const diaSemana = new Date(dia.data).getDay();
                const isFimDeSemana = diaSemana === 0 || diaSemana === 6;
                
                return (
                  <TableRow key={idx} className={isFimDeSemana ? "bg-muted/50" : ""}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{formatDate(new Date(dia.data))}</p>
                        {isFimDeSemana && (
                          <p className="text-xs text-muted-foreground">Fim de Semana</p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {entrada ? (
                        <div className="flex items-center gap-1">
                          <Clock className="h-3 w-3 text-muted-foreground" />
                          {formatTime(new Date(entrada.timestamp_local))}
                        </div>
                      ) : "-"}
                    </TableCell>
                    <TableCell>
                      {pausa ? formatTime(new Date(pausa.timestamp_local)) : "-"}
                    </TableCell>
                    <TableCell>
                      {retorno ? formatTime(new Date(retorno.timestamp_local)) : "-"}
                    </TableCell>
                    <TableCell>
                      {saida ? formatTime(new Date(saida.timestamp_local)) : "-"}
                    </TableCell>
                    <TableCell className="font-medium">
                      {dia.horas_trabalhadas || "-"}
                    </TableCell>
                    <TableCell>
                      {dia.observacoes?.length ? (
                        <div className="flex flex-wrap gap-1">
                          {dia.observacoes.map((obs: string, i: number) => (
                            <Badge key={i} variant={obs.toLowerCase().includes("atraso") || obs.toLowerCase().includes("falta") ? "destructive" : "secondary"}>
                              {obs}
                            </Badge>
                          ))}
                        </div>
                      ) : marcacoes.length > 0 ? (
                        <Badge variant="default">OK</Badge>
                      ) : isFimDeSemana ? (
                        <Badge variant="outline">-</Badge>
                      ) : (
                        <Badge variant="secondary">Sem registro</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
