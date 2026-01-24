/**
 * Sistema de Permissões por Hierarquia
 * 
 * Papéis:
 * - admin_dp: Acesso total (Administrador do DP)
 * - gestor: Gerencia sua equipe + relatórios
 * - auditor: Visualização + auditoria
 * - financeiro: Benefícios + relatórios financeiros
 * - colaborador: Apenas seu próprio ponto e espelho
 */

export type UserRole = "admin_dp" | "gestor" | "colaborador" | "auditor" | "financeiro";

export interface Permission {
  view: boolean;
  create: boolean;
  edit: boolean;
  delete: boolean;
}

export interface ModulePermissions {
  dashboard: Permission;
  registrar_ponto: Permission;
  colaboradores: Permission;
  equipes: Permission;
  escalas: Permission;
  locais: Permission;
  perimetros: Permission;
  ponto: Permission;
  espelho: Permission;
  exportacao: Permission;
  auditoria: Permission;
  documentos: Permission;
  beneficios: Permission;
  empresa: Permission;
  configuracoes: Permission;
}

// Definição de permissões por papel
const PERMISSIONS: Record<UserRole, ModulePermissions> = {
  admin_dp: {
    dashboard: { view: true, create: true, edit: true, delete: true },
    registrar_ponto: { view: true, create: true, edit: true, delete: true },
    colaboradores: { view: true, create: true, edit: true, delete: true },
    equipes: { view: true, create: true, edit: true, delete: true },
    escalas: { view: true, create: true, edit: true, delete: true },
    locais: { view: true, create: true, edit: true, delete: true },
    perimetros: { view: true, create: true, edit: true, delete: true },
    ponto: { view: true, create: true, edit: true, delete: true },
    espelho: { view: true, create: true, edit: true, delete: true },
    exportacao: { view: true, create: true, edit: true, delete: true },
    auditoria: { view: true, create: true, edit: true, delete: true },
    documentos: { view: true, create: true, edit: true, delete: true },
    beneficios: { view: true, create: true, edit: true, delete: true },
    empresa: { view: true, create: true, edit: true, delete: true },
    configuracoes: { view: true, create: true, edit: true, delete: true },
  },
  gestor: {
    dashboard: { view: true, create: false, edit: false, delete: false },
    registrar_ponto: { view: true, create: true, edit: false, delete: false },
    colaboradores: { view: true, create: false, edit: true, delete: false },
    equipes: { view: true, create: false, edit: false, delete: false },
    escalas: { view: true, create: true, edit: true, delete: false },
    locais: { view: true, create: false, edit: false, delete: false },
    perimetros: { view: true, create: false, edit: false, delete: false },
    ponto: { view: true, create: true, edit: true, delete: false },
    espelho: { view: true, create: false, edit: false, delete: false },
    exportacao: { view: true, create: true, edit: false, delete: false },
    auditoria: { view: true, create: false, edit: true, delete: false },
    documentos: { view: true, create: true, edit: true, delete: false },
    beneficios: { view: true, create: false, edit: false, delete: false },
    empresa: { view: false, create: false, edit: false, delete: false },
    configuracoes: { view: true, create: false, edit: true, delete: false },
  },
  auditor: {
    dashboard: { view: true, create: false, edit: false, delete: false },
    registrar_ponto: { view: true, create: true, edit: false, delete: false },
    colaboradores: { view: true, create: false, edit: false, delete: false },
    equipes: { view: true, create: false, edit: false, delete: false },
    escalas: { view: true, create: false, edit: false, delete: false },
    locais: { view: true, create: false, edit: false, delete: false },
    perimetros: { view: true, create: false, edit: false, delete: false },
    ponto: { view: true, create: false, edit: false, delete: false },
    espelho: { view: true, create: false, edit: false, delete: false },
    exportacao: { view: true, create: true, edit: false, delete: false },
    auditoria: { view: true, create: true, edit: true, delete: false },
    documentos: { view: true, create: false, edit: false, delete: false },
    beneficios: { view: false, create: false, edit: false, delete: false },
    empresa: { view: false, create: false, edit: false, delete: false },
    configuracoes: { view: true, create: false, edit: true, delete: false },
  },
  financeiro: {
    dashboard: { view: true, create: false, edit: false, delete: false },
    registrar_ponto: { view: true, create: true, edit: false, delete: false },
    colaboradores: { view: true, create: false, edit: false, delete: false },
    equipes: { view: false, create: false, edit: false, delete: false },
    escalas: { view: false, create: false, edit: false, delete: false },
    locais: { view: false, create: false, edit: false, delete: false },
    perimetros: { view: false, create: false, edit: false, delete: false },
    ponto: { view: false, create: false, edit: false, delete: false },
    espelho: { view: true, create: false, edit: false, delete: false },
    exportacao: { view: true, create: true, edit: false, delete: false },
    auditoria: { view: false, create: false, edit: false, delete: false },
    documentos: { view: true, create: true, edit: true, delete: false },
    beneficios: { view: true, create: true, edit: true, delete: true },
    empresa: { view: false, create: false, edit: false, delete: false },
    configuracoes: { view: true, create: false, edit: true, delete: false },
  },
  colaborador: {
    dashboard: { view: false, create: false, edit: false, delete: false },
    registrar_ponto: { view: true, create: true, edit: false, delete: false },
    colaboradores: { view: false, create: false, edit: false, delete: false },
    equipes: { view: false, create: false, edit: false, delete: false },
    escalas: { view: false, create: false, edit: false, delete: false },
    locais: { view: false, create: false, edit: false, delete: false },
    perimetros: { view: false, create: false, edit: false, delete: false },
    ponto: { view: true, create: true, edit: false, delete: false },
    espelho: { view: true, create: false, edit: false, delete: false },
    exportacao: { view: false, create: false, edit: false, delete: false },
    auditoria: { view: false, create: false, edit: false, delete: false },
    documentos: { view: true, create: true, edit: false, delete: false },
    beneficios: { view: true, create: false, edit: false, delete: false },
    empresa: { view: false, create: false, edit: false, delete: false },
    configuracoes: { view: true, create: false, edit: true, delete: false },
  },
};

/**
 * Obter permissões de um módulo para um papel
 */
export function getModulePermission(role: UserRole, module: keyof ModulePermissions): Permission {
  return PERMISSIONS[role]?.[module] || { view: false, create: false, edit: false, delete: false };
}

/**
 * Verificar se usuário pode acessar um módulo
 */
export function canAccess(role: UserRole, module: keyof ModulePermissions): boolean {
  return getModulePermission(role, module).view;
}

/**
 * Verificar se usuário pode criar em um módulo
 */
export function canCreate(role: UserRole, module: keyof ModulePermissions): boolean {
  return getModulePermission(role, module).create;
}

/**
 * Verificar se usuário pode editar em um módulo
 */
export function canEdit(role: UserRole, module: keyof ModulePermissions): boolean {
  return getModulePermission(role, module).edit;
}

/**
 * Verificar se usuário pode deletar em um módulo
 */
export function canDelete(role: UserRole, module: keyof ModulePermissions): boolean {
  return getModulePermission(role, module).delete;
}

/**
 * Menu items com permissões
 */
export interface MenuItem {
  name: string;
  href: string;
  module: keyof ModulePermissions;
  icon: string;
}

export const MENU_ITEMS: MenuItem[] = [
  { name: "Dashboard", href: "/dashboard", module: "dashboard", icon: "LayoutDashboard" },
  { name: "Registrar Ponto", href: "/dashboard/registrar-ponto", module: "registrar_ponto", icon: "Fingerprint" },
  { name: "Colaboradores", href: "/dashboard/usuarios", module: "colaboradores", icon: "Users" },
  { name: "Equipes", href: "/dashboard/equipes", module: "equipes", icon: "UsersRound" },
  { name: "Escalas", href: "/dashboard/escalas", module: "escalas", icon: "Calendar" },
  { name: "Locais", href: "/dashboard/locais", module: "locais", icon: "MapPin" },
  { name: "Perímetros", href: "/dashboard/perimetros", module: "perimetros", icon: "Map" },
  { name: "Ponto", href: "/dashboard/ponto", module: "ponto", icon: "CalendarClock" },
  { name: "Espelho de Ponto", href: "/dashboard/espelho", module: "espelho", icon: "FileText" },
  { name: "Exportação AEJ", href: "/dashboard/exportacao", module: "exportacao", icon: "FileDown" },
  { name: "Auditoria", href: "/dashboard/auditoria", module: "auditoria", icon: "ShieldCheck" },
  { name: "Documentos", href: "/dashboard/documentos", module: "documentos", icon: "FileStack" },
  { name: "Benefícios", href: "/dashboard/beneficios", module: "beneficios", icon: "Gift" },
  { name: "Empresa", href: "/dashboard/empresa", module: "empresa", icon: "Building2" },
  { name: "Configurações", href: "/dashboard/configuracoes", module: "configuracoes", icon: "Settings" },
];

/**
 * Filtrar menu items baseado no papel do usuário
 */
export function getMenuItemsForRole(role: UserRole): MenuItem[] {
  return MENU_ITEMS.filter(item => canAccess(role, item.module));
}

/**
 * Obter página inicial baseada no papel
 */
export function getHomePageForRole(role: UserRole): string {
  if (role === "colaborador") {
    return "/dashboard/registrar-ponto";
  }
  return "/dashboard";
}
