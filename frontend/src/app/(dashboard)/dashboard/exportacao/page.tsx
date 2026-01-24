'use client';

import { useState } from 'react';
import { 
  FileDown, 
  Calendar, 
  FileText, 
  Users, 
  CheckCircle2, 
  AlertCircle,
  Loader2,
  Download,
  FileSpreadsheet,
  Info
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardHeader, 
  CardTitle 
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from '@/components/ui/alert';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import toast from 'react-hot-toast';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

interface Usuario {
  id: string;
  nome: string;
  cpf: string;
  matricula: string;
}

interface ExportacaoResult {
  success: boolean;
  filename?: string;
  size?: number;
  records?: number;
  errors?: string[];
}

export default function ExportacaoAEJPage() {
  const [isExporting, setIsExporting] = useState(false);
  const [tipoExportacao, setTipoExportacao] = useState<'aej' | 'afd' | 'csv'>('aej');
  const [dataInicio, setDataInicio] = useState('');
  const [dataFim, setDataFim] = useState('');
  const [usuariosSelecionados, setUsuariosSelecionados] = useState<string[]>([]);
  const [selecionarTodos, setSelecionarTodos] = useState(true);
  const [resultado, setResultado] = useState<ExportacaoResult | null>(null);
  const [progresso, setProgresso] = useState(0);

  // Buscar lista de usuários
  const { data: usuarios = [], isLoading: loadingUsuarios } = useQuery({
    queryKey: ['usuarios-exportacao'],
    queryFn: async () => {
      const response = await api.get('/usuarios', { params: { per_page: 1000 } });
      return response.data.items as Usuario[];
    },
  });

  const handleExportar = async () => {
    if (!dataInicio || !dataFim) {
      toast.error('Selecione o período de exportação');
      return;
    }

    if (new Date(dataFim) < new Date(dataInicio)) {
      toast.error('Data final deve ser maior que data inicial');
      return;
    }

    setIsExporting(true);
    setProgresso(0);
    setResultado(null);

    try {
      // Simular progresso
      const progressInterval = setInterval(() => {
        setProgresso(prev => Math.min(prev + 10, 90));
      }, 500);

      const endpoint = tipoExportacao === 'aej' 
        ? '/exportacao/aej' 
        : tipoExportacao === 'afd'
        ? '/exportacao/afd'
        : '/exportacao/csv';

      const response = await api.post(endpoint, {
        data_inicial: dataInicio,
        data_final: dataFim,
        usuario_ids: selecionarTodos ? null : usuariosSelecionados,
      }, {
        responseType: 'blob',
      });

      clearInterval(progressInterval);
      setProgresso(100);

      // Extrair nome do arquivo do header
      const contentDisposition = response.headers['content-disposition'];
      let filename = `exportacao_${tipoExportacao}_${dataInicio}_${dataFim}.txt`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?(.+)"?/);
        if (match) filename = match[1];
      }

      // Criar download
      const blob = new Blob([response.data], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);

      setResultado({
        success: true,
        filename,
        size: blob.size,
      });

      toast.success('Arquivo exportado com sucesso!');
    } catch (error: any) {
      setResultado({
        success: false,
        errors: [error.response?.data?.detail || 'Erro ao exportar arquivo'],
      });
      toast.error('Erro ao exportar arquivo');
    } finally {
      setIsExporting(false);
    }
  };

  const handleToggleUsuario = (id: string) => {
    setUsuariosSelecionados(prev => 
      prev.includes(id) 
        ? prev.filter(u => u !== id)
        : [...prev, id]
    );
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Exportação AEJ - Portaria 671</h1>
        <p className="text-slate-500">
          Gere arquivos no formato AEJ (Arquivo Eletrônico de Jornada) conforme 
          exigências do Ministério do Trabalho
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Painel de configuração */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Configuração da Exportação</CardTitle>
              <CardDescription>
                Selecione o tipo de arquivo e período desejado
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Tipo de exportação */}
              <Tabs value={tipoExportacao} onValueChange={(v) => setTipoExportacao(v as any)}>
                <TabsList className="grid grid-cols-3 w-full">
                  <TabsTrigger value="aej" className="gap-2">
                    <FileText className="h-4 w-4" />
                    AEJ
                  </TabsTrigger>
                  <TabsTrigger value="afd" className="gap-2">
                    <FileDown className="h-4 w-4" />
                    AFD
                  </TabsTrigger>
                  <TabsTrigger value="csv" className="gap-2">
                    <FileSpreadsheet className="h-4 w-4" />
                    CSV
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="aej" className="mt-4">
                  <Alert>
                    <Info className="h-4 w-4" />
                    <AlertTitle>Arquivo Eletrônico de Jornada</AlertTitle>
                    <AlertDescription>
                      Formato padrão conforme Portaria 671/2021. Contém registros de 
                      trabalhadores, marcações e cálculos de jornada.
                    </AlertDescription>
                  </Alert>
                </TabsContent>

                <TabsContent value="afd" className="mt-4">
                  <Alert>
                    <Info className="h-4 w-4" />
                    <AlertTitle>Arquivo Fonte de Dados</AlertTitle>
                    <AlertDescription>
                      Formato AFD conforme Portaria 1510/2009. Usado para REPs 
                      (Registradores Eletrônicos de Ponto).
                    </AlertDescription>
                  </Alert>
                </TabsContent>

                <TabsContent value="csv" className="mt-4">
                  <Alert>
                    <Info className="h-4 w-4" />
                    <AlertTitle>Planilha CSV</AlertTitle>
                    <AlertDescription>
                      Formato simplificado para importação em planilhas Excel, 
                      Google Sheets ou sistemas de folha de pagamento.
                    </AlertDescription>
                  </Alert>
                </TabsContent>
              </Tabs>

              {/* Período */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Data Inicial</Label>
                  <Input
                    type="date"
                    value={dataInicio}
                    onChange={(e) => setDataInicio(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Data Final</Label>
                  <Input
                    type="date"
                    value={dataFim}
                    onChange={(e) => setDataFim(e.target.value)}
                  />
                </div>
              </div>

              {/* Seleção de usuários */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>Colaboradores</Label>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="todos"
                      checked={selecionarTodos}
                      onCheckedChange={(checked) => setSelecionarTodos(!!checked)}
                    />
                    <label htmlFor="todos" className="text-sm cursor-pointer">
                      Exportar todos
                    </label>
                  </div>
                </div>

                {!selecionarTodos && (
                  <div className="border rounded-lg max-h-48 overflow-y-auto">
                    {loadingUsuarios ? (
                      <div className="p-4 text-center">
                        <Loader2 className="h-5 w-5 animate-spin mx-auto" />
                      </div>
                    ) : (
                      <div className="divide-y">
                        {usuarios.map((usuario) => (
                          <label
                            key={usuario.id}
                            className="flex items-center gap-3 p-3 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer"
                          >
                            <Checkbox
                              checked={usuariosSelecionados.includes(usuario.id)}
                              onCheckedChange={() => handleToggleUsuario(usuario.id)}
                            />
                            <div className="flex-1 min-w-0">
                              <p className="font-medium truncate">{usuario.nome}</p>
                              <p className="text-xs text-slate-500">
                                {usuario.matricula} • {usuario.cpf}
                              </p>
                            </div>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {!selecionarTodos && (
                  <p className="text-sm text-slate-500">
                    {usuariosSelecionados.length} de {usuarios.length} selecionados
                  </p>
                )}
              </div>

              {/* Progresso */}
              {isExporting && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Exportando...</span>
                    <span>{progresso}%</span>
                  </div>
                  <Progress value={progresso} />
                </div>
              )}

              {/* Resultado */}
              {resultado && (
                <Alert variant={resultado.success ? 'default' : 'destructive'}>
                  {resultado.success ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <AlertCircle className="h-4 w-4" />
                  )}
                  <AlertTitle>
                    {resultado.success ? 'Exportação concluída!' : 'Erro na exportação'}
                  </AlertTitle>
                  <AlertDescription>
                    {resultado.success ? (
                      <div className="space-y-1">
                        <p>Arquivo: {resultado.filename}</p>
                        <p>Tamanho: {formatBytes(resultado.size || 0)}</p>
                      </div>
                    ) : (
                      <ul className="list-disc list-inside">
                        {resultado.errors?.map((err, i) => (
                          <li key={i}>{err}</li>
                        ))}
                      </ul>
                    )}
                  </AlertDescription>
                </Alert>
              )}

              {/* Botão exportar */}
              <Button
                onClick={handleExportar}
                disabled={isExporting || !dataInicio || !dataFim}
                className="w-full"
                size="lg"
              >
                {isExporting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Download className="h-4 w-4 mr-2" />
                )}
                {isExporting ? 'Exportando...' : 'Exportar Arquivo'}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Painel informativo */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Sobre a Portaria 671</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-slate-600 dark:text-slate-400 space-y-3">
              <p>
                A Portaria 671/2021 do Ministério do Trabalho consolida as regras 
                sobre o controle de jornada de trabalho.
              </p>
              <p>
                O arquivo AEJ (Arquivo Eletrônico de Jornada) é obrigatório para 
                empresas que utilizam sistemas alternativos de controle de ponto.
              </p>
              <div className="pt-2 border-t">
                <p className="font-medium mb-2">Tipos de registro:</p>
                <ul className="space-y-1 text-xs">
                  <li><Badge variant="outline">Tipo 1</Badge> Cabeçalho</li>
                  <li><Badge variant="outline">Tipo 2</Badge> Trabalhador</li>
                  <li><Badge variant="outline">Tipo 3</Badge> Marcações</li>
                  <li><Badge variant="outline">Tipo 4</Badge> Justificativas</li>
                  <li><Badge variant="outline">Tipo 5</Badge> Cálculo diário</li>
                  <li><Badge variant="outline">Tipo 9</Badge> Totalizador</li>
                </ul>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Histórico de Exportações</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-slate-500 text-center py-4">
                Nenhuma exportação recente
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
