export function createSafeStorage(storage) {
  return {
    getItem(key, fallback = null) {
      try {
        return storage?.getItem(key) ?? fallback;
      } catch {
        return fallback;
      }
    },
    setItem(key, value) {
      try {
        storage?.setItem(key, value);
        return true;
      } catch {
        return false;
      }
    },
    removeItem(key) {
      try {
        storage?.removeItem(key);
        return true;
      } catch {
        return false;
      }
    },
    getJson(key, fallback) {
      const value = this.getItem(key);
      if (!value) return fallback;
      try {
        return JSON.parse(value);
      } catch {
        return fallback;
      }
    },
    setJson(key, value) {
      return this.setItem(key, JSON.stringify(value));
    },
  };
}

export const safeLocalStorage = createSafeStorage(globalThis.localStorage);
export const safeSessionStorage = createSafeStorage(globalThis.sessionStorage);
