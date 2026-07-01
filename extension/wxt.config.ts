import { defineConfig } from "wxt";

// WXT (Vite/MV3) config. Entrypoints are auto-discovered from entrypoints/; every context
// (content script, side panel, service worker) is bundled from the shared src/ modules.
export default defineConfig({
  srcDir: ".",
  manifest: {
    name: "Untethered — RCM job fit",
    description:
      "Scores revenue-cycle job postings for real-remote, real pay, offshore-resistance, and credential fit — on-device. Score-don't-store.",
    permissions: ["sidePanel", "activeTab", "tabs", "storage"],
    host_permissions: [
      "https://*.myworkdayjobs.com/*",
      "https://boards.greenhouse.io/*",
      "https://*.greenhouse.io/*",
      "https://jobs.lever.co/*",
      "https://jobs.ashbyhq.com/*",
      "https://*.indeed.com/*",
    ],
    action: { default_title: "Untethered — score this job" },
    side_panel: { default_path: "sidepanel.html" },
  },
});
