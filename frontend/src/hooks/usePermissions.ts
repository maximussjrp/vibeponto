"use client";

import { useMemo } from "react";
import { useAuthStore } from "@/store/auth";
import {
  UserRole,
  ModulePermissions,
  getModulePermission,
  canAccess,
  canCreate,
  canEdit,
  canDelete,
  getMenuItemsForRole,
  getHomePageForRole,
  Permission,
} from "@/lib/permissions";

export function usePermissions() {
  const { user } = useAuthStore();
  
  const role = (user?.papel || "colaborador") as UserRole;

  const permissions = useMemo(() => ({
    role,
    
    /**
     * Verificar se pode acessar um módulo
     */
    canAccess: (module: keyof ModulePermissions): boolean => {
      return canAccess(role, module);
    },
    
    /**
     * Verificar se pode criar em um módulo
     */
    canCreate: (module: keyof ModulePermissions): boolean => {
      return canCreate(role, module);
    },
    
    /**
     * Verificar se pode editar em um módulo
     */
    canEdit: (module: keyof ModulePermissions): boolean => {
      return canEdit(role, module);
    },
    
    /**
     * Verificar se pode deletar em um módulo
     */
    canDelete: (module: keyof ModulePermissions): boolean => {
      return canDelete(role, module);
    },
    
    /**
     * Obter todas as permissões de um módulo
     */
    getPermission: (module: keyof ModulePermissions): Permission => {
      return getModulePermission(role, module);
    },
    
    /**
     * Itens de menu permitidos para o usuário
     */
    menuItems: getMenuItemsForRole(role).map(item => ({
      ...item,
      label: item.name,
    })),
    
    /**
     * Página inicial do usuário
     */
    homePage: getHomePageForRole(role),
    
    /**
     * Verificações rápidas de papel
     */
    isAdmin: role === "admin_dp",
    isGestor: role === "gestor",
    isColaborador: role === "colaborador",
    isAuditor: role === "auditor",
    isFinanceiro: role === "financeiro",
    
    /**
     * Verificar se é gestor ou superior
     */
    isGestorOrAbove: ["admin_dp", "gestor"].includes(role),
    
  }), [role]);

  return permissions;
}

export default usePermissions;
