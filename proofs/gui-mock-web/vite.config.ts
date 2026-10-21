import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// controls.json / demo.json live one folder up (../gui-mock), shared with the Qt mockup.
export default defineConfig({ plugins: [react()], server: { fs: { allow: [".."] } } });
