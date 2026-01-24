/**
 * Testes de componentes do frontend
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// ==================== Testes de Utilidades ====================

describe('Utilities', () => {
  describe('formatCPF', () => {
    it('should format CPF correctly', () => {
      const formatCPF = (cpf: string) => {
        const cleaned = cpf.replace(/\D/g, '');
        return cleaned.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
      };
      
      expect(formatCPF('12345678901')).toBe('123.456.789-01');
      expect(formatCPF('11122233344')).toBe('111.222.333-44');
    });
  });

  describe('formatPhone', () => {
    it('should format phone number correctly', () => {
      const formatPhone = (phone: string) => {
        const cleaned = phone.replace(/\D/g, '');
        if (cleaned.length === 11) {
          return cleaned.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
        }
        return cleaned.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2-$3');
      };
      
      expect(formatPhone('11999998888')).toBe('(11) 99999-8888');
      expect(formatPhone('1133334444')).toBe('(11) 3333-4444');
    });
  });

  describe('formatCurrency', () => {
    it('should format currency correctly', () => {
      const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('pt-BR', {
          style: 'currency',
          currency: 'BRL',
        }).format(value);
      };
      
      expect(formatCurrency(1234.56)).toBe('R$ 1.234,56');
      expect(formatCurrency(0)).toBe('R$ 0,00');
    });
  });

  describe('formatDate', () => {
    it('should format date correctly', () => {
      const formatDate = (date: Date) => {
        return new Intl.DateTimeFormat('pt-BR').format(date);
      };
      
      const date = new Date('2026-01-23');
      expect(formatDate(date)).toBe('23/01/2026');
    });
  });

  describe('formatTime', () => {
    it('should format time correctly', () => {
      const formatTime = (date: Date) => {
        return new Intl.DateTimeFormat('pt-BR', {
          hour: '2-digit',
          minute: '2-digit',
        }).format(date);
      };
      
      const date = new Date('2026-01-23T14:30:00');
      expect(formatTime(date)).toBe('14:30');
    });
  });
});

// ==================== Testes de Validação ====================

describe('Validation', () => {
  describe('validateCPF', () => {
    const validateCPF = (cpf: string): boolean => {
      const cleaned = cpf.replace(/\D/g, '');
      
      if (cleaned.length !== 11) return false;
      if (/^(\d)\1{10}$/.test(cleaned)) return false;
      
      let sum = 0;
      for (let i = 0; i < 9; i++) {
        sum += parseInt(cleaned[i]) * (10 - i);
      }
      let digit = (sum * 10) % 11;
      if (digit === 10) digit = 0;
      if (digit !== parseInt(cleaned[9])) return false;
      
      sum = 0;
      for (let i = 0; i < 10; i++) {
        sum += parseInt(cleaned[i]) * (11 - i);
      }
      digit = (sum * 10) % 11;
      if (digit === 10) digit = 0;
      if (digit !== parseInt(cleaned[10])) return false;
      
      return true;
    };
    
    it('should validate correct CPF', () => {
      expect(validateCPF('529.982.247-25')).toBe(true);
      expect(validateCPF('52998224725')).toBe(true);
    });
    
    it('should reject invalid CPF', () => {
      expect(validateCPF('111.111.111-11')).toBe(false);
      expect(validateCPF('123.456.789-00')).toBe(false);
      expect(validateCPF('12345')).toBe(false);
    });
  });

  describe('validateEmail', () => {
    const validateEmail = (email: string): boolean => {
      const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      return regex.test(email);
    };
    
    it('should validate correct email', () => {
      expect(validateEmail('test@example.com')).toBe(true);
      expect(validateEmail('user.name@domain.com.br')).toBe(true);
    });
    
    it('should reject invalid email', () => {
      expect(validateEmail('invalid')).toBe(false);
      expect(validateEmail('invalid@')).toBe(false);
      expect(validateEmail('@domain.com')).toBe(false);
    });
  });

  describe('validatePassword', () => {
    const validatePassword = (password: string): { valid: boolean; errors: string[] } => {
      const errors: string[] = [];
      
      if (password.length < 8) {
        errors.push('Mínimo 8 caracteres');
      }
      if (!/[A-Z]/.test(password)) {
        errors.push('Pelo menos uma letra maiúscula');
      }
      if (!/[a-z]/.test(password)) {
        errors.push('Pelo menos uma letra minúscula');
      }
      if (!/[0-9]/.test(password)) {
        errors.push('Pelo menos um número');
      }
      if (!/[!@#$%^&*]/.test(password)) {
        errors.push('Pelo menos um caractere especial');
      }
      
      return { valid: errors.length === 0, errors };
    };
    
    it('should validate strong password', () => {
      const result = validatePassword('Test@123');
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });
    
    it('should reject weak password', () => {
      const result = validatePassword('weak');
      expect(result.valid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });
  });
});

// ==================== Testes de Cálculo de Horas ====================

describe('Hour Calculations', () => {
  describe('calculateWorkedHours', () => {
    const calculateWorkedHours = (
      entrada: Date,
      saida: Date,
      pausaMinutos: number = 0
    ): number => {
      const diffMs = saida.getTime() - entrada.getTime();
      const diffMinutos = diffMs / (1000 * 60);
      return (diffMinutos - pausaMinutos) / 60;
    };
    
    it('should calculate 8 hours worked', () => {
      const entrada = new Date('2026-01-23T08:00:00');
      const saida = new Date('2026-01-23T17:00:00');
      
      expect(calculateWorkedHours(entrada, saida, 60)).toBe(8);
    });
    
    it('should calculate overtime', () => {
      const entrada = new Date('2026-01-23T08:00:00');
      const saida = new Date('2026-01-23T19:00:00');
      
      const horasTrabalhadas = calculateWorkedHours(entrada, saida, 60);
      const horasExtras = horasTrabalhadas - 8;
      
      expect(horasExtras).toBe(2);
    });
  });

  describe('calculateNightHours', () => {
    const calculateNightHours = (
      entrada: Date,
      saida: Date
    ): number => {
      // Horário noturno: 22h às 5h
      let nightMinutes = 0;
      const current = new Date(entrada);
      
      while (current < saida) {
        const hour = current.getHours();
        if (hour >= 22 || hour < 5) {
          nightMinutes++;
        }
        current.setMinutes(current.getMinutes() + 1);
      }
      
      return nightMinutes / 60;
    };
    
    it('should calculate night hours', () => {
      const entrada = new Date('2026-01-23T22:00:00');
      const saida = new Date('2026-01-24T02:00:00');
      
      expect(calculateNightHours(entrada, saida)).toBe(4);
    });
    
    it('should return 0 for day shift', () => {
      const entrada = new Date('2026-01-23T08:00:00');
      const saida = new Date('2026-01-23T17:00:00');
      
      expect(calculateNightHours(entrada, saida)).toBe(0);
    });
  });
});

// ==================== Testes de Estado ====================

describe('State Management', () => {
  describe('Auth State', () => {
    it('should handle login state', () => {
      const initialState = { user: null, token: null, isAuthenticated: false };
      
      const loginReducer = (state: any, action: any) => {
        switch (action.type) {
          case 'LOGIN':
            return {
              user: action.payload.user,
              token: action.payload.token,
              isAuthenticated: true,
            };
          case 'LOGOUT':
            return initialState;
          default:
            return state;
        }
      };
      
      const loggedInState = loginReducer(initialState, {
        type: 'LOGIN',
        payload: {
          user: { id: '1', name: 'Test' },
          token: 'abc123',
        },
      });
      
      expect(loggedInState.isAuthenticated).toBe(true);
      expect(loggedInState.user?.name).toBe('Test');
      
      const loggedOutState = loginReducer(loggedInState, { type: 'LOGOUT' });
      
      expect(loggedOutState.isAuthenticated).toBe(false);
      expect(loggedOutState.user).toBeNull();
    });
  });
});

// ==================== Testes de API Mocking ====================

describe('API Helpers', () => {
  describe('buildQueryString', () => {
    const buildQueryString = (params: Record<string, any>): string => {
      const searchParams = new URLSearchParams();
      
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          searchParams.append(key, String(value));
        }
      });
      
      return searchParams.toString();
    };
    
    it('should build query string correctly', () => {
      const params = { page: 1, per_page: 10, search: 'test' };
      expect(buildQueryString(params)).toBe('page=1&per_page=10&search=test');
    });
    
    it('should ignore undefined values', () => {
      const params = { page: 1, filter: undefined, search: '' };
      expect(buildQueryString(params)).toBe('page=1');
    });
  });

  describe('parseApiError', () => {
    const parseApiError = (error: any): string => {
      if (error?.response?.data?.detail) {
        if (typeof error.response.data.detail === 'string') {
          return error.response.data.detail;
        }
        if (Array.isArray(error.response.data.detail)) {
          return error.response.data.detail.map((e: any) => e.msg).join(', ');
        }
      }
      return error?.message || 'Erro desconhecido';
    };
    
    it('should parse string error', () => {
      const error = { response: { data: { detail: 'Invalid credentials' } } };
      expect(parseApiError(error)).toBe('Invalid credentials');
    });
    
    it('should parse validation errors', () => {
      const error = {
        response: {
          data: {
            detail: [
              { msg: 'Email is required' },
              { msg: 'Password too short' },
            ],
          },
        },
      };
      expect(parseApiError(error)).toBe('Email is required, Password too short');
    });
    
    it('should handle unknown error', () => {
      expect(parseApiError({})).toBe('Erro desconhecido');
    });
  });
});

// ==================== Testes de Permissões ====================

describe('Permissions', () => {
  const ROLES = {
    ADMIN_DP: 'admin_dp',
    GESTOR: 'gestor',
    COLABORADOR: 'colaborador',
  };

  const checkPermission = (userRole: string, requiredRoles: string[]): boolean => {
    return requiredRoles.includes(userRole);
  };

  it('should allow admin access to all', () => {
    expect(checkPermission(ROLES.ADMIN_DP, [ROLES.ADMIN_DP, ROLES.GESTOR, ROLES.COLABORADOR])).toBe(true);
  });

  it('should deny colaborador access to admin features', () => {
    expect(checkPermission(ROLES.COLABORADOR, [ROLES.ADMIN_DP])).toBe(false);
  });

  it('should allow gestor access to team features', () => {
    expect(checkPermission(ROLES.GESTOR, [ROLES.ADMIN_DP, ROLES.GESTOR])).toBe(true);
  });
});
