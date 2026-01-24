// VibePonto Service Worker v1.0.0
const CACHE_NAME = 'vibeponto-v1';
const OFFLINE_URL = '/offline';

// Recursos para cache estático
const STATIC_CACHE = [
  '/',
  '/offline',
  '/manifest.json',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
];

// Recursos de API para cache dinâmico
const API_CACHE_NAME = 'vibeponto-api-v1';
const SYNC_QUEUE_NAME = 'vibeponto-sync';

// IndexedDB para sincronização offline
const DB_NAME = 'vibeponto-offline';
const DB_VERSION = 1;
const STORES = {
  PENDING_SYNC: 'pending-sync',
  CACHED_DATA: 'cached-data',
  USER_DATA: 'user-data',
};

// Abrir IndexedDB
function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      
      // Store para operações pendentes de sincronização
      if (!db.objectStoreNames.contains(STORES.PENDING_SYNC)) {
        const syncStore = db.createObjectStore(STORES.PENDING_SYNC, { 
          keyPath: 'id', 
          autoIncrement: true 
        });
        syncStore.createIndex('timestamp', 'timestamp', { unique: false });
        syncStore.createIndex('type', 'type', { unique: false });
      }
      
      // Store para dados em cache
      if (!db.objectStoreNames.contains(STORES.CACHED_DATA)) {
        const cacheStore = db.createObjectStore(STORES.CACHED_DATA, { 
          keyPath: 'url' 
        });
        cacheStore.createIndex('expiry', 'expiry', { unique: false });
      }
      
      // Store para dados do usuário
      if (!db.objectStoreNames.contains(STORES.USER_DATA)) {
        db.createObjectStore(STORES.USER_DATA, { keyPath: 'key' });
      }
    };
  });
}

// Adicionar item à fila de sincronização
async function addToSyncQueue(data) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.PENDING_SYNC, 'readwrite');
    const store = tx.objectStore(STORES.PENDING_SYNC);
    
    const item = {
      ...data,
      timestamp: Date.now(),
      retries: 0,
    };
    
    const request = store.add(item);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// Obter itens pendentes de sincronização
async function getPendingSyncItems() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.PENDING_SYNC, 'readonly');
    const store = tx.objectStore(STORES.PENDING_SYNC);
    const request = store.getAll();
    
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// Remover item da fila de sincronização
async function removeFromSyncQueue(id) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.PENDING_SYNC, 'readwrite');
    const store = tx.objectStore(STORES.PENDING_SYNC);
    const request = store.delete(id);
    
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

// Salvar dados em cache
async function saveToCachedData(url, data, ttl = 3600000) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.CACHED_DATA, 'readwrite');
    const store = tx.objectStore(STORES.CACHED_DATA);
    
    const item = {
      url,
      data,
      expiry: Date.now() + ttl,
      timestamp: Date.now(),
    };
    
    const request = store.put(item);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

// Obter dados do cache
async function getFromCachedData(url) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.CACHED_DATA, 'readonly');
    const store = tx.objectStore(STORES.CACHED_DATA);
    const request = store.get(url);
    
    request.onsuccess = () => {
      const result = request.result;
      if (result && result.expiry > Date.now()) {
        resolve(result.data);
      } else {
        resolve(null);
      }
    };
    request.onerror = () => reject(request.error);
  });
}

// Instalação do Service Worker
self.addEventListener('install', (event) => {
  console.log('[SW] Installing Service Worker...');
  
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Caching static assets');
      return cache.addAll(STATIC_CACHE);
    })
  );
  
  self.skipWaiting();
});

// Ativação do Service Worker
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating Service Worker...');
  
  event.waitUntil(
    Promise.all([
      // Limpar caches antigos
      caches.keys().then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => name !== CACHE_NAME && name !== API_CACHE_NAME)
            .map((name) => caches.delete(name))
        );
      }),
      // Assumir controle imediatamente
      self.clients.claim(),
    ])
  );
});

// Interceptar requisições
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Ignorar requisições não-GET para cache (exceto ponto offline)
  if (request.method !== 'GET') {
    // Tratamento especial para registro de ponto offline
    if (url.pathname.includes('/api/v1/ponto') && request.method === 'POST') {
      event.respondWith(handleOfflinePonto(request));
      return;
    }
    return;
  }
  
  // Estratégia para API
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstWithCache(request));
    return;
  }
  
  // Estratégia para assets estáticos
  if (url.pathname.match(/\.(js|css|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot)$/)) {
    event.respondWith(cacheFirstWithNetwork(request));
    return;
  }
  
  // Estratégia para páginas HTML
  event.respondWith(networkFirstWithOffline(request));
});

// Network first com fallback para cache
async function networkFirstWithCache(request) {
  try {
    const response = await fetch(request);
    
    if (response.ok) {
      const cache = await caches.open(API_CACHE_NAME);
      cache.put(request, response.clone());
      
      // Também salvar no IndexedDB para acesso offline
      const data = await response.clone().json();
      await saveToCachedData(request.url, data);
    }
    
    return response;
  } catch (error) {
    // Tentar cache
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Tentar IndexedDB
    const cachedData = await getFromCachedData(request.url);
    if (cachedData) {
      return new Response(JSON.stringify(cachedData), {
        headers: { 'Content-Type': 'application/json' },
      });
    }
    
    throw error;
  }
}

// Cache first com fallback para network
async function cacheFirstWithNetwork(request) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    const response = await fetch(request);
    const cache = await caches.open(CACHE_NAME);
    cache.put(request, response.clone());
    return response;
  } catch (error) {
    console.error('[SW] Failed to fetch asset:', error);
    throw error;
  }
}

// Network first com página offline
async function networkFirstWithOffline(request) {
  try {
    const response = await fetch(request);
    
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    
    return response;
  } catch (error) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Retornar página offline
    return caches.match(OFFLINE_URL);
  }
}

// Tratamento especial para registro de ponto offline
async function handleOfflinePonto(request) {
  try {
    // Tentar enviar normalmente
    const response = await fetch(request.clone());
    return response;
  } catch (error) {
    // Se offline, salvar na fila de sincronização
    const body = await request.json();
    
    await addToSyncQueue({
      type: 'PONTO',
      url: request.url,
      method: request.method,
      body: body,
      headers: Object.fromEntries(request.headers.entries()),
    });
    
    // Retornar resposta simulada
    return new Response(JSON.stringify({
      success: true,
      offline: true,
      message: 'Ponto registrado offline. Será sincronizado quando houver conexão.',
      timestamp: new Date().toISOString(),
    }), {
      status: 202,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

// Background Sync
self.addEventListener('sync', (event) => {
  console.log('[SW] Sync event:', event.tag);
  
  if (event.tag === SYNC_QUEUE_NAME) {
    event.waitUntil(syncPendingRequests());
  }
});

// Sincronizar requisições pendentes
async function syncPendingRequests() {
  const pendingItems = await getPendingSyncItems();
  
  console.log(`[SW] Syncing ${pendingItems.length} pending items...`);
  
  for (const item of pendingItems) {
    try {
      const response = await fetch(item.url, {
        method: item.method,
        headers: item.headers,
        body: JSON.stringify(item.body),
      });
      
      if (response.ok) {
        await removeFromSyncQueue(item.id);
        console.log(`[SW] Synced item ${item.id}`);
        
        // Notificar o cliente
        const clients = await self.clients.matchAll();
        clients.forEach((client) => {
          client.postMessage({
            type: 'SYNC_SUCCESS',
            item: item,
          });
        });
      } else if (response.status >= 400 && response.status < 500) {
        // Erro do cliente, remover da fila
        await removeFromSyncQueue(item.id);
        console.error(`[SW] Client error for item ${item.id}, removing from queue`);
      }
    } catch (error) {
      console.error(`[SW] Failed to sync item ${item.id}:`, error);
      // Manter na fila para tentar novamente
    }
  }
}

// Periodic Background Sync (se suportado)
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'sync-pending') {
    event.waitUntil(syncPendingRequests());
  }
});

// Push Notifications
self.addEventListener('push', (event) => {
  console.log('[SW] Push received:', event);
  
  let data = { title: 'VibePonto', body: 'Nova notificação' };
  
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data.body = event.data.text();
    }
  }
  
  const options = {
    body: data.body,
    icon: '/icons/icon-192x192.png',
    badge: '/icons/badge-72x72.png',
    vibrate: [100, 50, 100],
    data: data.data || {},
    actions: data.actions || [],
    tag: data.tag || 'vibeponto-notification',
    renotify: true,
  };
  
  event.waitUntil(self.registration.showNotification(data.title, options));
});

// Clique em notificação
self.addEventListener('notificationclick', (event) => {
  console.log('[SW] Notification clicked:', event);
  
  event.notification.close();
  
  const urlToOpen = event.notification.data?.url || '/dashboard';
  
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Se já existe uma janela aberta, focar nela
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(urlToOpen);
          return client.focus();
        }
      }
      // Caso contrário, abrir nova janela
      if (self.clients.openWindow) {
        return self.clients.openWindow(urlToOpen);
      }
    })
  );
});

// Mensagens do cliente
self.addEventListener('message', (event) => {
  console.log('[SW] Message received:', event.data);
  
  switch (event.data.type) {
    case 'SKIP_WAITING':
      self.skipWaiting();
      break;
      
    case 'GET_PENDING_COUNT':
      getPendingSyncItems().then((items) => {
        event.ports[0].postMessage({ count: items.length });
      });
      break;
      
    case 'FORCE_SYNC':
      syncPendingRequests().then(() => {
        event.ports[0].postMessage({ success: true });
      });
      break;
      
    case 'CLEAR_CACHE':
      Promise.all([
        caches.delete(CACHE_NAME),
        caches.delete(API_CACHE_NAME),
      ]).then(() => {
        event.ports[0].postMessage({ success: true });
      });
      break;
  }
});

console.log('[SW] Service Worker loaded');
