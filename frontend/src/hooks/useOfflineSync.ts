/**
 * Hook para gerenciar sincronização offline
 * Integra com Service Worker e IndexedDB
 */

import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { useAuthStore } from '@/store/auth';

interface PendingSyncItem {
  id: number;
  type: string;
  url: string;
  method: string;
  body: any;
  timestamp: number;
  retries: number;
}

interface OfflineSyncState {
  isOnline: boolean;
  isServiceWorkerReady: boolean;
  pendingCount: number;
  isSyncing: boolean;
  lastSyncTime: Date | null;
}

export function useOfflineSync() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const [state, setState] = useState<OfflineSyncState>({
    isOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
    isServiceWorkerReady: false,
    pendingCount: 0,
    isSyncing: false,
    lastSyncTime: null,
  });

  // Registrar Service Worker
  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
      return;
    }

    const registerSW = async () => {
      try {
        const registration = await navigator.serviceWorker.register('/sw.js', {
          scope: '/',
        });

        console.log('Service Worker registered:', registration.scope);

        // Verificar atualizações
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          if (newWorker) {
            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                toast.info('Nova versão disponível!', {
                  action: {
                    label: 'Atualizar',
                    onClick: () => {
                      newWorker.postMessage({ type: 'SKIP_WAITING' });
                      window.location.reload();
                    },
                  },
                });
              }
            });
          }
        });

        setState(prev => ({ ...prev, isServiceWorkerReady: true }));
        
        // Atualizar contagem de pendentes
        updatePendingCount();
      } catch (error) {
        console.error('Service Worker registration failed:', error);
      }
    };

    registerSW();
  }, []);

  // Monitorar status de conexão
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const handleOnline = () => {
      setState(prev => ({ ...prev, isOnline: true }));
      toast.success('Conexão restaurada!');
      
      // Tentar sincronizar pendentes
      forceSync();
    };

    const handleOffline = () => {
      setState(prev => ({ ...prev, isOnline: false }));
      toast.warning('Você está offline. As alterações serão salvas localmente.');
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Escutar mensagens do Service Worker
  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
      return;
    }

    const handleMessage = (event: MessageEvent) => {
      switch (event.data.type) {
        case 'SYNC_SUCCESS':
          toast.success(`Sincronizado: ${event.data.item.type}`);
          updatePendingCount();
          break;
          
        case 'SYNC_ERROR':
          toast.error(`Erro na sincronização: ${event.data.error}`);
          break;
      }
    };

    navigator.serviceWorker.addEventListener('message', handleMessage);

    return () => {
      navigator.serviceWorker.removeEventListener('message', handleMessage);
    };
  }, []);

  // Atualizar contagem de itens pendentes
  const updatePendingCount = useCallback(async () => {
    const controller = navigator.serviceWorker.controller;
    if (!controller) return;

    const messageChannel = new MessageChannel();
    
    return new Promise<number>((resolve) => {
      messageChannel.port1.onmessage = (event) => {
        const count = event.data.count || 0;
        setState(prev => ({ ...prev, pendingCount: count }));
        resolve(count);
      };

      controller.postMessage(
        { type: 'GET_PENDING_COUNT', accessToken },
        [messageChannel.port2]
      );
    });
  }, [accessToken]);

  // Forçar sincronização
  const forceSync = useCallback(async () => {
    const controller = navigator.serviceWorker.controller;
    if (!controller) return;

    setState(prev => ({ ...prev, isSyncing: true }));

    try {
      const messageChannel = new MessageChannel();

      await new Promise<void>((resolve) => {
        messageChannel.port1.onmessage = () => {
          resolve();
        };

        controller.postMessage(
          { type: 'FORCE_SYNC', accessToken },
          [messageChannel.port2]
        );
      });

      setState(prev => ({ 
        ...prev, 
        isSyncing: false,
        lastSyncTime: new Date(),
      }));
      
      await updatePendingCount();
      
    } catch (error) {
      console.error('Sync failed:', error);
      setState(prev => ({ ...prev, isSyncing: false }));
    }
  }, [accessToken, updatePendingCount]);

  // Limpar cache
  const clearCache = useCallback(async () => {
    const controller = navigator.serviceWorker.controller;
    if (!controller) return;

    const messageChannel = new MessageChannel();
    
    return new Promise<void>((resolve) => {
      messageChannel.port1.onmessage = () => {
        toast.success('Cache limpo!');
        resolve();
      };

      controller.postMessage(
        { type: 'CLEAR_CACHE' },
        [messageChannel.port2]
      );
    });
  }, []);

  // Solicitar permissão de notificação
  const requestNotificationPermission = useCallback(async () => {
    if (!('Notification' in window)) {
      toast.error('Notificações não suportadas neste navegador');
      return false;
    }

    if (Notification.permission === 'granted') {
      return true;
    }

    const permission = await Notification.requestPermission();
    
    if (permission === 'granted') {
      toast.success('Notificações ativadas!');
      return true;
    } else {
      toast.error('Permissão de notificação negada');
      return false;
    }
  }, []);

  return {
    ...state,
    updatePendingCount,
    forceSync,
    clearCache,
    requestNotificationPermission,
  };
}

// Hook para verificar se pode instalar PWA
export function usePWAInstall() {
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isInstallable, setIsInstallable] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    // Verificar se já está instalado
    if (window.matchMedia('(display-mode: standalone)').matches) {
      setIsInstalled(true);
      return;
    }

    const handleBeforeInstall = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
      setIsInstallable(true);
    };

    const handleAppInstalled = () => {
      setIsInstalled(true);
      setIsInstallable(false);
      setDeferredPrompt(null);
      toast.success('App instalado com sucesso!');
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstall);
    window.addEventListener('appinstalled', handleAppInstalled);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, []);

  const install = useCallback(async () => {
    if (!deferredPrompt) return false;

    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    
    setDeferredPrompt(null);
    setIsInstallable(false);
    
    return outcome === 'accepted';
  }, [deferredPrompt]);

  return {
    isInstallable,
    isInstalled,
    install,
  };
}
