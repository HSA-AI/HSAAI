import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

// FIX (runtime): vitest-tsconfig-paths package was unavailable on the npm
// registry (ETARGET). The same @/ alias is configured via resolve.alias below.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/*.test.{ts,tsx}", "**/*.spec.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html", "lcov"],
      include: [
        "lib/**/*.ts",
        "services/**/*.ts",
        "components/**/*.{ts,tsx}",
      ],
      exclude: [
        "node_modules/**",
        "**/*.test.{ts,tsx}",
        "**/*.spec.{ts,tsx}",
        "**/types.ts",
      ],
      thresholds: {
        statements: 60,
        branches: 50,
        functions: 50,
        lines: 60,
      },
    },
    css: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./"),
    },
  },
});
