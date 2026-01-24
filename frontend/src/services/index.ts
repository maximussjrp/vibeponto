/**
 * Índice de todos os serviços de API
 */

export * from "./usuarios";
export * from "./equipes";
export * from "./ponto";
export * from "./espelho";
export * from "./locais";
export * from "./auditoria";
export * from "./documentos";
export * from "./beneficios";
export * from "./empresa";
export * from "./dashboard";

// Default exports
export { default as usuariosService } from "./usuarios";
export { default as equipesService } from "./equipes";
export { default as pontoService } from "./ponto";
export { default as espelhoService } from "./espelho";
export { default as locaisService } from "./locais";
export { default as auditoriaService } from "./auditoria";
export { default as documentosService } from "./documentos";
export { default as beneficiosService } from "./beneficios";
export { empresaService, configuracoesService } from "./empresa";
export { default as dashboardService } from "./dashboard";
