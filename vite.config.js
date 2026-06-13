import { cpSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    {
      name: "prepare-static-site",
      transformIndexHtml(html) {
        return html.replace(
          /<script src="(script|account|admin)\.js"><\/script>/g,
          '<script type="module" src="/$1.js"></script>'
        );
      },
      writeBundle() {
        cpSync("assets", "dist/assets", { recursive: true });
      }
    }
  ],
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
