/**
 * Serviço de API para Locais/Geocercas
 */

import api from "@/lib/api";
import { toFiniteNumber } from "@/lib/utils";
import { PaginatedResponse } from "./usuarios";

// Tipos
export interface Perimetro {
  id: string;
  tenant_id: string;
  nome: string;
  descricao?: string;
  tipo: "circulo" | "poligono";
  latitude: number;
  longitude: number;
  raio?: number;  // metros, para tipo circulo
  raio_metros: number;
  coordenadas?: { lat: number; lng: number }[];  // para tipo poligono
  endereco?: string;
  ativo: boolean;
  tolerancia_metros: number;
  horario_inicio?: string;
  horario_fim?: string;
  dias_semana?: number[];  // 0-6 (domingo-sábado)
  created_at: string;
  updated_at: string;
}

export interface PerimetroCreate {
  nome: string;
  descricao?: string;
  tipo?: "circulo" | "poligono";
  latitude: number;
  longitude: number;
  raio?: number;
  raio_metros: number;
  coordenadas?: { lat: number; lng: number }[];
  endereco?: string;
  tolerancia_metros?: number;
  horario_inicio?: string;
  horario_fim?: string;
  dias_semana?: number[];
}

export interface PerimetroUpdate {
  nome?: string;
  descricao?: string;
  latitude?: number;
  longitude?: number;
  raio?: number;
  raio_metros: number;
  coordenadas?: { lat: number; lng: number }[];
  endereco?: string;
  ativo?: boolean;
  tolerancia_metros?: number;
  horario_inicio?: string;
  horario_fim?: string;
  dias_semana?: number[];
}

export interface ListPerimetrosParams {
  page?: number;
  per_page?: number;
  ativo?: boolean;
  q?: string;
}

export interface ValidacaoGeo {
  dentro_perimetro: boolean;
  perimetro_id?: string;
  perimetro_nome?: string;
  distancia_metros?: number;
}


function normalizePerimetro(perimetro: Perimetro): Perimetro {
  return {
    ...perimetro,
    latitude: toFiniteNumber(perimetro.latitude) ?? Number.NaN,
    longitude: toFiniteNumber(perimetro.longitude) ?? Number.NaN,
    raio_metros: toFiniteNumber(perimetro.raio_metros ?? perimetro.raio) ?? 100,
    tolerancia_metros: toFiniteNumber(perimetro.tolerancia_metros) ?? 0,
  };
}

// Funções de API
export const locaisService = {
  /**
   * Listar perímetros/locais
   */
  async list(params: ListPerimetrosParams = {}): Promise<PaginatedResponse<Perimetro>> {
    const { data } = await api.get("/geo/perimetros", { params });
    return { ...data, items: data.items.map(normalizePerimetro) };
  },

  /**
   * Buscar perímetro por ID
   */
  async get(id: string): Promise<Perimetro> {
    const { data } = await api.get(`/geo/perimetros/${id}`);
    return normalizePerimetro(data);
  },

  /**
   * Criar novo perímetro
   */
  async create(perimetro: PerimetroCreate): Promise<Perimetro> {
    const { data } = await api.post("/geo/perimetros", perimetro);
    return normalizePerimetro(data);
  },

  /**
   * Atualizar perímetro
   */
  async update(id: string, perimetro: PerimetroUpdate): Promise<Perimetro> {
    const { data } = await api.patch(`/geo/perimetros/${id}`, perimetro);
    return normalizePerimetro(data);
  },

  /**
   * Excluir perímetro
   */
  async delete(id: string): Promise<void> {
    await api.delete(`/geo/perimetros/${id}`);
  },

  /**
   * Ativar/Desativar perímetro
   */
  async toggleAtivo(id: string, ativo: boolean): Promise<Perimetro> {
    const { data } = await api.patch(`/geo/perimetros/${id}`, { ativo });
    return normalizePerimetro(data);
  },

  async activate(id: string): Promise<Perimetro> {
    return this.toggleAtivo(id, true);
  },

  async deactivate(id: string): Promise<Perimetro> {
    return this.toggleAtivo(id, false);
  },

  /**
   * Validar se coordenadas estão dentro de algum perímetro
   */
  async validarLocalizacao(latitude: number, longitude: number): Promise<ValidacaoGeo> {
    const { data } = await api.post("/geo/validar", { latitude, longitude });
    return data;
  },

  /**
   * Buscar endereço por CEP
   */
  async buscarCEP(cep: string): Promise<{
    logradouro: string;
    bairro: string;
    cidade: string;
    estado: string;
    uf?: string;
    latitude?: number;
    longitude?: number;
  }> {
    const { data } = await api.get(`/geo/cep/${cep}`);
    return { ...data, uf: data.uf || data.estado };
  },

  async lookupCep(cep: string): Promise<{
    logradouro: string;
    bairro: string;
    cidade: string;
    estado: string;
    uf?: string;
    latitude?: number;
    longitude?: number;
  }> {
    return this.buscarCEP(cep);
  },

  /**
   * Geocodificar endereço (obter lat/lng)
   */
  async geocodificar(endereco: string): Promise<{ latitude: number; longitude: number }> {
    const { data } = await api.post("/geo/geocodificar", { endereco });
    return data;
  },
};

export default locaisService;
