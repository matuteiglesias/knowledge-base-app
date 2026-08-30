import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Generated shadcn primitives are dependency-like UI scaffolding; product
    // code composes them but does not maintain their internal lint semantics.
    "src/components/ui/**",
    // create-next-app / Storybook sample files are not workbench product code.
    "src/stories/**",
  ]),
]);

export default eslintConfig;
