/**
 * Hook para gerenciar sincronização offline
 * Integra com Service Worker e IndexedDB
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'sonner';
import { useAuthStore } from '@/store/auth';

interface OfflineSyncState {
  isOnline: boolean;
  isServiceWorkerReady: boolean;
  pendingCount: number;
  isSyncing: boolean;
  lastSyncTime: Date | null;
}

function getServiceWorkerController(): ServiceWorker | null {
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) {
    return null;
  }

  return navigator.serviceWorker.controller;
}

export function useOfflineSync() {
  const syncInProgressRef = useRef(false);
  const accessToken = useAuthStore((state) => state.accessToken);
  const [state, setState] = useState<OfflineSyncState>({
    isOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
    isServiceWorkerReady: false,
    pendingCount: 0,
    isSyncing: false,
    lastSyncTime: null,
  });

  // Atualizar contagem de itens pendentes
  const updatePendingCount = useCallback(async () => {
    const controller = getServiceWorkerController();
    if (!controller) return 0;

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
    const controller = getServiceWorkerController();
    if (!controller || syncInProgressRef.current) return;

    syncInProgressRef.current = true;
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
        lastSyncTime: new Date(),
      }));

      await updatePendingCount();
    } catch (error) {
      console.error('Sync failed:', error);
    } finally {
      syncInProgressRef.current = false;
      setState(prev => ({ ...prev, isSyncing: false }));
    }
  }, [accessToken, updatePendingCount]);

  // Limpar cache
  const clearCache = useCallback(async () => {
    const controller = getServiceWorkerController();
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
        await updatePendingCount();
      } catch (error) {
        console.error('Service Worker registration failed:', error);
      }
    };

    void registerSW();
  }, [updatePendingCount]);

  // Monitorar status de conexão
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const handleOnline = () => {
      setState(prev => ({ ...prev, isOnline: true }));
      toast.success('Conexão restaurada!');

      // Tentar sincronizar pendentes
      void forceSync();
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
  }, [forceSync]);

  // Escutar mensagens do Service Worker
  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
      return;
    }

    const handleMessage = (event: MessageEvent) => {
      switch (event.data.type) {
        case 'SYNC_SUCCESS':
          toast.success(`Sincronizado: ${event.data.item.type}`);
          void updatePendingCount();
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
  }, [updatePendingCount]);

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
