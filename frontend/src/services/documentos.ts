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
  | "outros";

export type StatusDocumento = "pendente" | "aprovado" | "rejeitado";

export interface Documento {
  id: string;
  tenant_id: string;
  usuario_id: string;
  tipo: TipoDocumento;
  titulo: string;
  descricao?: string;
  arquivo_url: string;
  arquivo_nome: string;
  arquivo_tipo: string;  // mime type
  arquivo_tamanho: number;  // bytes
  data_documento?: string;
  data_inicio?: string;  // para atestados/declarações
  data_fim?: string;
  status: StatusDocumento;
  aprovador_id?: string;
  aprovado_em?: string;
  observacao_aprovador?: string;
  created_at: string;
  updated_at: string;
  usuario?: {
    id: string;
    nome: string;
    matricula: string;
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

// Funções de API
export const documentosService = {
  /**
   * Listar documentos
   */
  async list(params: ListDocumentosParams = {}): Promise<PaginatedResponse<Documento>> {
    const { data } = await api.get("/documentos", { params });
    return data;
  },

  /**
   * Buscar documento por ID
   */
  async get(id: string): Promise<Documento> {
    const { data } = await api.get(`/documentos/${id}`);
    return data;
  },

  /**
   * Fazer upload de documento
   */
  async upload(documento: DocumentoUpload): Promise<Documento> {
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
    return data;
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
  async aprovar(id: string, aprovacao: DocumentoAprovacao): Promise<Documento> {
    const { data } = await api.post(`/documentos/${id}/aprovar`, aprovacao);
    return data;
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
