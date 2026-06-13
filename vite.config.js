import { cpSync, mkdirSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    {
      name: "prepare-static-site",
      writeBundle() {
        const root = import.meta.dirname;
        const output = resolve(root, "dist");
        const assetOutput = resolve(output, "assets");

        mkdirSync(assetOutput, { recursive: true });
        for (const file of readdirSync(root)) {
          if (/\.(png|jpe?g|webp)$/i.test(file)) {
            cpSync(resolve(root, file), resolve(assetOutput, file));
          }
        }
        for (const script of ["script.js", "account.js", "admin.js"]) {
          cpSync(resolve(root, script), resolve(output, script));
        }
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
