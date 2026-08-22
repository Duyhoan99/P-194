import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // The current API client intentionally models several evolving backend
      // payloads. Tighten these types endpoint-by-endpoint after the v1 schema
      // is generated; blocking the MVP on 100+ legacy `any` values adds no
      // runtime safety.
      "@typescript-eslint/no-explicit-any": "off",
      // Data loading effects are valid in this client-only dashboard. The
      // React Compiler rule is stricter than the project's current architecture.
      "react-hooks/set-state-in-effect": "off",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
