// VibePonto Service Worker
const CACHE_NAME = "vibeponto-static-v2";
const OFFLINE_URL = "/offline";
const SYNC_QUEUE_NAME = "vibeponto-sync";
const DB_NAME = "vibeponto-offline";
const DB_VERSION = 2;
const STORES = {
  PENDING_SYNC: "pending-sync",
};

const STATIC_CACHE = [
  OFFLINE_URL,
  "/manifest.json",
  "/icons/icon-192x192.png",
  "/icons/icon-512x512.png",
];

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      for (const name of Array.from(db.objectStoreNames)) {
        db.deleteObjectStore(name);
      }
      const store = db.createObjectStore(STORES.PENDING_SYNC, {
        keyPath: "id",
        autoIncrement: true,
      });
      store.createIndex("timestamp", "timestamp", { unique: false });
      store.createIndex("owner", "owner", { unique: false });
    };
  });
}

async function addToSyncQueue(data) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.PENDING_SYNC, "readwrite");
    const store = tx.objectStore(STORES.PENDING_SYNC);
    const request = store.add({
      ...data,
      timestamp: Date.now(),
      retries: 0,
    });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getPendingSyncItems(owner) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.PENDING_SYNC, "readonly");
    const store = tx.objectStore(STORES.PENDING_SYNC);
    const request = store.getAll();
    request.onsuccess = () => {
      const items = request.result || [];
      resolve(owner ? items.filter((item) => item.owner === owner) : items);
    };
    request.onerror = () => reject(request.error);
  });
}

async function removeFromSyncQueue(id) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORES.PENDING_SYNC, "readwrite");
    const store = tx.objectStore(STORES.PENDING_SYNC);
    const request = store.delete(id);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

function deleteDatabase(name) {
  return new Promise((resolve) => {
    const request = indexedDB.deleteDatabase(name);
    request.onsuccess = () => resolve();
    request.onerror = () => resolve();
    request.onblocked = () => resolve();
  });
}

function base64UrlDecode(value) {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length / 4) * 4, "=");
  return atob(padded);
}

function tokenOwnerFromBearer(header) {
  if (!header || !header.startsWith("Bearer ")) {
    return null;
  }

  try {
    const token = header.slice("Bearer ".length);
    const [, payload] = token.split(".");
    const claims = JSON.parse(base64UrlDecode(payload));
    return claims.sub && claims.tenant_id ? `${claims.tenant_id}:${claims.sub}` : null;
  } catch {
    return null;
  }
}

function ownerFromAccessToken(token) {
  return tokenOwnerFromBearer(token ? `Bearer ${token}` : null);
}

function isAllowedOfflinePonto(url, method) {
  return method === "POST" && url.pathname === "/api/v1/ponto/registrar";
}

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_CACHE)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    Promise.all([
      caches.keys().then((names) =>
        Promise.all(names.filter((name) => name.startsWith("vibeponto") && name !== CACHE_NAME).map((name) => caches.delete(name)))
      ),
      self.clients.claim(),
    ])
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (url.origin !== self.location.origin && !url.pathname.startsWith("/api/")) {
    return;
  }

  if (request.method !== "GET") {
    if (isAllowedOfflinePonto(url, request.method)) {
      event.respondWith(handleOfflinePonto(request, url));
    }
    return;
  }

  if (url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(request));
    return;
  }

  if (url.pathname.match(/\.(js|css|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot)$/)) {
    event.respondWith(cacheFirstWithNetwork(request));
    return;
  }

  event.respondWith(networkOnlyWithOffline(request));
});

async function cacheFirstWithNetwork(request) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }

  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(CACHE_NAME);
    await cache.put(request, response.clone());
  }
  return response;
}

async function networkOnlyWithOffline(request) {
  try {
    return await fetch(request);
  } catch {
    return caches.match(OFFLINE_URL);
  }
}

async function handleOfflinePonto(request, url) {
  try {
    return await fetch(request.clone());
  } catch {
    const owner = tokenOwnerFromBearer(request.headers.get("Authorization"));
    if (!owner) {
      return new Response(JSON.stringify({ detail: "Sessao necessaria para registro offline." }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    }

    const body = await request.json();
    await addToSyncQueue({
      type: "PONTO",
      owner,
      url: request.url,
      method: request.method,
      body,
    });

    return new Response(
      JSON.stringify({
        success: true,
        offline: true,
        message: "Ponto registrado offline. Sera sincronizado quando a conexao voltar.",
        timestamp: new Date().toISOString(),
      }),
      {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}

self.addEventListener("sync", (event) => {
  if (event.tag === SYNC_QUEUE_NAME) {
    event.waitUntil(syncPendingRequests({}));
  }
});

async function syncPendingRequests({ accessToken } = {}) {
  const owner = ownerFromAccessToken(accessToken);
  if (!accessToken || !owner) {
    return;
  }

  const pendingItems = await getPendingSyncItems(owner);
  for (const item of pendingItems) {
    try {
      const response = await fetch(item.url, {
        method: item.method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
          "X-Auth-Mode": "cookie",
        },
        body: JSON.stringify(item.body),
      });

      if (response.ok) {
        await removeFromSyncQueue(item.id);
        const clients = await self.clients.matchAll();
        clients.forEach((client) => {
          client.postMessage({ type: "SYNC_SUCCESS", item });
        });
      } else if (response.status !== 401 && response.status >= 400 && response.status < 500) {
        await removeFromSyncQueue(item.id);
      }
    } catch {
      // Mantem na fila para a proxima tentativa autenticada.
    }
  }
}

self.addEventListener("periodicsync", (event) => {
  if (event.tag === "sync-pending") {
    event.waitUntil(syncPendingRequests({}));
  }
});

self.addEventListener("push", (event) => {
  let data = { title: "VibePonto", body: "Nova notificacao" };
  if (event.data) {
    try {
      data = event.data.json();
    } catch {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: "/icons/icon-192x192.png",
    badge: "/icons/badge-72x72.png",
    vibrate: [100, 50, 100],
    data: data.data || {},
    actions: data.actions || [],
    tag: data.tag || "vibeponto-notification",
    renotify: true,
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const urlToOpen = event.notification.data?.url || "/dashboard";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && "focus" in client) {
          client.navigate(urlToOpen);
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(urlToOpen);
      }
      return undefined;
    })
  );
});

self.addEventListener("message", (event) => {
  const data = event.data || {};

  switch (data.type) {
    case "SKIP_WAITING":
      self.skipWaiting();
      break;

    case "GET_PENDING_COUNT": {
      const owner = ownerFromAccessToken(data.accessToken);
      getPendingSyncItems(owner).then((items) => {
        event.ports[0]?.postMessage({ count: items.length });
      });
      break;
    }

    case "FORCE_SYNC":
      syncPendingRequests({ accessToken: data.accessToken }).then(() => {
        event.ports[0]?.postMessage({ success: true });
      });
      break;

    case "CLEAR_CACHE":
      caches.delete(CACHE_NAME).then(() => {
        event.ports[0]?.postMessage({ success: true });
      });
      break;

    case "CLEAR_AUTH":
      Promise.all([caches.delete(CACHE_NAME), deleteDatabase(DB_NAME)]).then(() => {
        event.ports[0]?.postMessage({ success: true });
      });
      break;
  }
});
