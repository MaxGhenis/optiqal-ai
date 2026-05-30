import "@testing-library/jest-dom/vitest";

// jsdom in this environment does not provide a usable Web Storage
// implementation (the built-in `localStorage` object lacks working methods).
// Install a minimal in-memory localStorage so client components that persist
// profile state can render under test.
function isUsableStorage(candidate: unknown): candidate is Storage {
  return (
    typeof candidate === "object" &&
    candidate !== null &&
    typeof (candidate as Storage).clear === "function" &&
    typeof (candidate as Storage).getItem === "function" &&
    typeof (candidate as Storage).setItem === "function"
  );
}

if (!isUsableStorage(globalThis.localStorage)) {
  const store = new Map<string, string>();
  const localStorageMock: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(globalThis, "localStorage", {
    value: localStorageMock,
    writable: true,
    configurable: true,
  });
}
