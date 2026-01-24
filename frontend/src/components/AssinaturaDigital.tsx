'use client';

import { useState, useRef, useCallback } from 'react';
import { 
  FileSignature, 
  Upload, 
  Check, 
  X, 
  Shield, 
  AlertTriangle,
  Loader2,
  Eye,
  EyeOff,
  Download,
  FileText
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
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { api } from '@/lib/api';

interface CertificadoInfo {
  titular: string;
  cpf?: string;
  cnpj?: string;
  email?: string;
  emissor: string;
  validade_inicio: string;
  validade_fim: string;
  numero_serie: string;
  tipo: string;
  is_valido: boolean;
  motivo_invalido?: string;
}

interface AssinaturaResult {
  success: boolean;
  envelope?: any;
  error?: string;
}

interface AssinaturaDigitalProps {
  documentoId: string;
  documentoTipo: 'espelho' | 'folha' | 'ferias' | 'atestado' | 'outro';
  documentoNome: string;
  onAssinado?: (envelope: any) => void;
  periodoInicio?: string;
  periodoFim?: string;
}

const POLITICAS = {
  'AD-RB': 'Referência Básica',
  'AD-RT': 'Referência de Tempo',
  'AD-RV': 'Referências para Validação',
  'AD-RC': 'Referências Completas',
  'AD-RA': 'Referências para Arquivamento',
};

export default function AssinaturaDigital({
  documentoId,
  documentoTipo,
  documentoNome,
  onAssinado,
  periodoInicio,
  periodoFim,
}: AssinaturaDigitalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [step, setStep] = useState<'upload' | 'info' | 'signing' | 'success'>('upload');
  const [certificadoFile, setCertificadoFile] = useState<File | null>(null);
  const [certificadoBase64, setCertificadoBase64] = useState<string>('');
  const [senha, setSenha] = useState('');
  const [showSenha, setShowSenha] = useState(false);
  const [politica, setPolitica] = useState('AD-RB');
  const [certificadoInfo, setCertificadoInfo] = useState<CertificadoInfo | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [resultado, setResultado] = useState<AssinaturaResult | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validar extensão
    const ext = file.name.toLowerCase().split('.').pop();
    if (!['pfx', 'p12'].includes(ext || '')) {
      toast.error('Arquivo inválido. Use um certificado .pfx ou .p12');
      return;
    }

    setCertificadoFile(file);

    // Converter para base64
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = (reader.result as string).split(',')[1];
      setCertificadoBase64(base64);
    };
    reader.readAsDataURL(file);
  }, []);

  const handleValidarCertificado = async () => {
    if (!certificadoBase64 || !senha) {
      toast.error('Selecione o certificado e digite a senha');
      return;
    }

    setIsLoading(true);
    try {
      const response = await api.post('/assinatura/validar-certificado', {
        certificado_base64: certificadoBase64,
        senha: senha,
      });

      const info = response.data as CertificadoInfo;
      setCertificadoInfo(info);

      if (!info.is_valido) {
        toast.error(`Certificado inválido: ${info.motivo_invalido}`);
      } else {
        setStep('info');
        toast.success('Certificado validado com sucesso!');
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Erro ao validar certificado');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAssinar = async () => {
    setIsLoading(true);
    setStep('signing');

    try {
      let endpoint = '/assinatura/assinar';
      let payload: any = {
        documento_id: documentoId,
        certificado_base64: certificadoBase64,
        senha: senha,
        politica: politica,
      };

      // Endpoint específico para espelho de ponto
      if (documentoTipo === 'espelho' && periodoInicio && periodoFim) {
        endpoint = '/assinatura/assinar-espelho';
        payload = {
          ...payload,
          periodo_inicio: periodoInicio,
          periodo_fim: periodoFim,
        };
      }

      const response = await api.post(endpoint, payload);
      
      setResultado({ success: true, envelope: response.data });
      setStep('success');
      toast.success('Documento assinado com sucesso!');
      
      if (onAssinado) {
        onAssinado(response.data);
      }
    } catch (error: any) {
      setResultado({ 
        success: false, 
        error: error.response?.data?.detail || 'Erro ao assinar documento' 
      });
      toast.error('Erro ao assinar documento');
      setStep('info');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadEnvelope = () => {
    if (!resultado?.envelope) return;

    const blob = new Blob(
      [JSON.stringify(resultado.envelope, null, 2)], 
      { type: 'application/json' }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${documentoNome}_assinado.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClose = () => {
    setIsOpen(false);
    setStep('upload');
    setCertificadoFile(null);
    setCertificadoBase64('');
    setSenha('');
    setCertificadoInfo(null);
    setResultado(null);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="gap-2">
          <FileSignature className="h-4 w-4" />
          Assinar Digitalmente
        </Button>
      </DialogTrigger>
      
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-blue-500" />
            Assinatura Digital ICP-Brasil
          </DialogTitle>
          <DialogDescription>
            Assine o documento com seu certificado digital A1 ou A3
          </DialogDescription>
        </DialogHeader>

        {/* Step: Upload */}
        {step === 'upload' && (
          <div className="space-y-4">
            <div className="border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-lg p-6 text-center">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pfx,.p12"
                onChange={handleFileSelect}
                className="hidden"
              />
              
              {certificadoFile ? (
                <div className="space-y-2">
                  <Check className="h-10 w-10 mx-auto text-green-500" />
                  <p className="font-medium">{certificadoFile.name}</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    Trocar arquivo
                  </Button>
                </div>
              ) : (
                <div 
                  className="cursor-pointer"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload className="h-10 w-10 mx-auto text-slate-400 mb-2" />
                  <p className="text-sm text-slate-600 dark:text-slate-400">
                    Clique para selecionar seu certificado
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    Formatos aceitos: .pfx, .p12
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="senha">Senha do Certificado</Label>
              <div className="relative">
                <Input
                  id="senha"
                  type={showSenha ? 'text' : 'password'}
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                  placeholder="Digite a senha do certificado"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="absolute right-0 top-0 h-full px-3"
                  onClick={() => setShowSenha(!showSenha)}
                >
                  {showSenha ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Política de Assinatura</Label>
              <Select value={politica} onValueChange={setPolitica}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(POLITICAS).map(([key, value]) => (
                    <SelectItem key={key} value={key}>
                      {key} - {value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <DialogFooter>
              <Button variant="ghost" onClick={handleClose}>
                Cancelar
              </Button>
              <Button 
                onClick={handleValidarCertificado}
                disabled={!certificadoFile || !senha || isLoading}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : null}
                Validar Certificado
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step: Info */}
        {step === 'info' && certificadoInfo && (
          <div className="space-y-4">
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">Certificado Digital</CardTitle>
                  <Badge variant={certificadoInfo.is_valido ? 'default' : 'destructive'}>
                    {certificadoInfo.tipo}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <p className="text-slate-500">Titular</p>
                    <p className="font-medium">{certificadoInfo.titular}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">CPF/CNPJ</p>
                    <p className="font-medium">
                      {certificadoInfo.cpf || certificadoInfo.cnpj || '-'}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500">Emissor</p>
                    <p className="font-medium truncate" title={certificadoInfo.emissor}>
                      {certificadoInfo.emissor}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500">Validade</p>
                    <p className="font-medium">
                      {formatDate(certificadoInfo.validade_fim)}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Documento a Assinar</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-slate-500" />
                  <span>{documentoNome}</span>
                </div>
                {periodoInicio && periodoFim && (
                  <p className="text-slate-500">
                    Período: {formatDate(periodoInicio)} a {formatDate(periodoFim)}
                  </p>
                )}
                <p className="text-slate-500">
                  Política: {politica} - {POLITICAS[politica as keyof typeof POLITICAS]}
                </p>
              </CardContent>
            </Card>

            <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5" />
                <div className="text-sm">
                  <p className="font-medium text-yellow-800 dark:text-yellow-200">
                    Atenção
                  </p>
                  <p className="text-yellow-700 dark:text-yellow-300">
                    Ao assinar digitalmente, você declara que revisou e concorda 
                    com o conteúdo do documento. Esta ação tem validade jurídica.
                  </p>
                </div>
              </div>
            </div>

            <DialogFooter>
              <Button variant="ghost" onClick={() => setStep('upload')}>
                Voltar
              </Button>
              <Button onClick={handleAssinar} disabled={isLoading}>
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <FileSignature className="h-4 w-4 mr-2" />
                )}
                Assinar Documento
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step: Signing */}
        {step === 'signing' && (
          <div className="py-8 text-center">
            <Loader2 className="h-12 w-12 animate-spin mx-auto text-blue-500 mb-4" />
            <p className="font-medium">Assinando documento...</p>
            <p className="text-sm text-slate-500 mt-1">
              Aguarde enquanto processamos sua assinatura digital
            </p>
          </div>
        )}

        {/* Step: Success */}
        {step === 'success' && resultado?.success && (
          <div className="space-y-4">
            <div className="text-center py-4">
              <div className="w-16 h-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
                <Check className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="font-semibold text-lg">Documento Assinado!</h3>
              <p className="text-sm text-slate-500 mt-1">
                A assinatura digital foi aplicada com sucesso
              </p>
            </div>

            <Card>
              <CardContent className="pt-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">Assinante</span>
                  <span className="font-medium">
                    {resultado.envelope?.certificado?.titular}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">CPF</span>
                  <span className="font-medium">
                    {resultado.envelope?.certificado?.cpf || '-'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Data/Hora</span>
                  <span className="font-medium">
                    {formatDate(resultado.envelope?.assinatura?.timestamp)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Política</span>
                  <span className="font-medium">{resultado.envelope?.politica}</span>
                </div>
              </CardContent>
            </Card>

            <DialogFooter>
              <Button variant="outline" onClick={handleDownloadEnvelope}>
                <Download className="h-4 w-4 mr-2" />
                Baixar Envelope
              </Button>
              <Button onClick={handleClose}>
                Concluir
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
