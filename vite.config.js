import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        index: resolve(import.meta.dirname, "index.html"),
        account: resolve(import.meta.dirname, "account.html"),
        admin: resolve(import.meta.dirname, "admin.html")
      }
    }
  }
});
