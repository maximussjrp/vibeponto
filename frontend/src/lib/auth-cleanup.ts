const AUTH_STORAGE_KEY = "vibeponto-auth";
const AUTH_CLEARED_EVENT = "vibeponto:auth-cleared";
const OFFLINE_DB_NAME = "vibeponto-offline";

export function notifyAuthCleared() {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(new Event(AUTH_CLEARED_EVENT));
}

export function onAuthCleared(callback: () => void) {
  if (typeof window === "undefined") {
    return () => undefined;
  }

  window.addEventListener(AUTH_CLEARED_EVENT, callback);
  return () => window.removeEventListener(AUTH_CLEARED_EVENT, callback);
}

function deleteIndexedDB(name: string) {
  if (typeof window === "undefined" || !("indexedDB" in window)) {
    return Promise.resolve();
  }

  return new Promise<void>((resolve) => {
    const request = indexedDB.deleteDatabase(name);
    request.onsuccess = () => resolve();
    request.onerror = () => resolve();
    request.onblocked = () => resolve();
  });
}

async function clearServiceWorkerAuth() {
  if (
    typeof navigator === "undefined" ||
    !("serviceWorker" in navigator) ||
    !navigator.serviceWorker.controller
  ) {
    return;
  }

  const channel = new MessageChannel();
  await new Promise<void>((resolve) => {
    const timer = window.setTimeout(resolve, 1000);
    channel.port1.onmessage = () => {
      window.clearTimeout(timer);
      resolve();
    };
    navigator.serviceWorker.controller?.postMessage({ type: "CLEAR_AUTH" }, [channel.port2]);
  });
}

export async function clearBrowserAuthData() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
  }

  await Promise.allSettled([
    clearServiceWorkerAuth(),
    typeof caches !== "undefined"
      ? caches.keys().then((keys) =>
          Promise.all(keys.filter((key) => key.startsWith("vibeponto")).map((key) => caches.delete(key)))
        )
      : Promise.resolve(),
    deleteIndexedDB(OFFLINE_DB_NAME),
  ]);

  notifyAuthCleared();
}
