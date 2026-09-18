/**
 * Serviço de API para Documentos
 */

import api from "@/lib/api";
import { PaginatedResponse } from "./usuarios";

// Tipos
export type TipoDocumento = 
  | "atestado"
  | "declaracao"
  | "comprovante"
  | "contrato"
  | "termo"
  | "outro"
  | "outros";

export type DocumentoTipo = TipoDocumento;

export type StatusDocumento = "pendente" | "aprovado" | "rejeitado";
export type DocumentoStatus = StatusDocumento;

export interface Documento {
  id: string;
  tenant_id: string;
  usuario_id: string;
  tipo: TipoDocumento;
  titulo: string;
  descricao?: string;
  arquivo_url: string;
  arquivo_nome: string;
  arquivo_tipo?: string;  // mime type legado
  arquivo_mime?: string;
  arquivo_tamanho: number;  // bytes
  nome_arquivo: string;
  mime_type: string;
  tamanho: number;
  data_documento?: string;
  data_inicio?: string;  // para atestados/declarações
  data_fim?: string;
  data_referencia?: string;
  status: StatusDocumento;
  assinatura_status?: StatusDocumento;
  aprovador_id?: string;
  aprovado_em?: string;
  observacao_aprovador?: string;
  created_at: string;
  updated_at: string;
  usuario?: {
    id: string;
    nome: string;
    matricula?: string;
    foto_url?: string;
  };
}

export interface DocumentoUpload {
  tipo: TipoDocumento;
  titulo: string;
  descricao?: string;
  arquivo: File;
  data_documento?: string;
  data_inicio?: string;
  data_fim?: string;
  usuario_id?: string;  // se admin enviando para outro usuário
}

export interface DocumentoAprovacao {
  status: "aprovado" | "rejeitado";
  observacao?: string;
}

export type DocumentoPageResponse = PaginatedResponse<Documento> & { total_pages: number };

export interface ListDocumentosParams {
  page?: number;
  per_page?: number;
  tipo?: TipoDocumento;
  status?: StatusDocumento;
  usuario_id?: string;
  data_inicio?: string;
  data_fim?: string;
  q?: string;
}


function normalizeDocumento(documento: Documento): Documento {
  return {
    ...documento,
    nome_arquivo: documento.nome_arquivo || documento.arquivo_nome,
    mime_type: documento.mime_type || documento.arquivo_mime || documento.arquivo_tipo || "application/octet-stream",
    tamanho: documento.tamanho ?? documento.arquivo_tamanho,
    status: documento.status || documento.assinatura_status || "pendente",
  };
}

function normalizeDocumentoPage(response: PaginatedResponse<Documento> & { total_pages?: number }): DocumentoPageResponse {
  const perPage = response.per_page || response.items.length || 1;
  return {
    ...response,
    items: response.items.map(normalizeDocumento),
    total_pages: response.total_pages || response.pages || Math.ceil(response.total / perPage),
  };
}

// Funções de API
export const documentosService = {
  /**
   * Listar documentos
   */
  async list(params: ListDocumentosParams = {}): Promise<DocumentoPageResponse> {
    const { data } = await api.get("/documentos", { params });
    return normalizeDocumentoPage(data);
  },

  /**
   * Buscar documento por ID
   */
  async get(id: string): Promise<Documento> {
    const { data } = await api.get(`/documentos/${id}`);
    return normalizeDocumento(data);
  },

  /**
   * Fazer upload de documento
   */
  async upload(fileOrDocumento: File | DocumentoUpload, metadata?: Partial<Omit<DocumentoUpload, "arquivo">> & { data_referencia?: string }): Promise<Documento> {
    const documento: DocumentoUpload = fileOrDocumento instanceof File
      ? {
          arquivo: fileOrDocumento,
          tipo: metadata?.tipo || "outro",
          titulo: metadata?.titulo || fileOrDocumento.name,
          descricao: metadata?.descricao,
          usuario_id: metadata?.usuario_id,
          data_documento: metadata?.data_documento || metadata?.data_referencia,
          data_inicio: metadata?.data_inicio,
          data_fim: metadata?.data_fim,
        }
      : fileOrDocumento;

    const formData = new FormData();
    formData.append("arquivo", documento.arquivo);
    formData.append("tipo", documento.tipo);
    formData.append("titulo", documento.titulo);
    if (documento.descricao) formData.append("descricao", documento.descricao);
    if (documento.data_documento) formData.append("data_documento", documento.data_documento);
    if (documento.data_inicio) formData.append("data_inicio", documento.data_inicio);
    if (documento.data_fim) formData.append("data_fim", documento.data_fim);
    if (documento.usuario_id) formData.append("usuario_id", documento.usuario_id);

    const { data } = await api.post("/documentos/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return normalizeDocumento(data);
  },

  /**
   * Download de documento
   */
  async download(id: string): Promise<Blob> {
    const response = await api.get(`/documentos/${id}/download`, {
      responseType: "blob",
    });
    return response.data;
  },

  /**
   * Aprovar/Rejeitar documento
   */
  async aprovar(id: string, aprovacao: DocumentoAprovacao = { status: "aprovado" }): Promise<Documento> {
    const { data } = await api.post(`/documentos/${id}/aprovar`, aprovacao);
    return normalizeDocumento(data);
  },

  async rejeitar(id: string, observacao?: string): Promise<Documento> {
    const { data } = await api.post(`/documentos/${id}/aprovar`, { status: "rejeitado", observacao });
    return normalizeDocumento(data);
  },

  /**
   * Excluir documento
   */
  async delete(id: string): Promise<void> {
    await api.delete(`/documentos/${id}`);
  },

  /**
   * Meus documentos
   */
  async meusDocumentos(params: Omit<ListDocumentosParams, "usuario_id"> = {}): Promise<PaginatedResponse<Documento>> {
    const { data } = await api.get("/documentos/meus", { params });
    return data;
  },

  /**
   * Documentos pendentes de aprovação
   */
  async pendentes(params: Omit<ListDocumentosParams, "status"> = {}): Promise<PaginatedResponse<Documento>> {
    return this.list({ ...params, status: "pendente" });
  },
};

export default documentosService;
