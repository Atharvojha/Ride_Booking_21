import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests', timeout: 45000, workers: 1,
  use: { baseURL: 'http://127.0.0.1:5174', channel: 'chrome', trace: 'retain-on-failure' },
  webServer: [
    { command: (process.env.RIDESYNC_TEST_PYTHON || 'python3') + ' ../tests/browser_server.py', url: 'http://127.0.0.1:8001/api/health', timeout: 60000, reuseExistingServer: false, gracefulShutdown: { signal: 'SIGTERM', timeout: 10000 } },
    { command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort', url: 'http://127.0.0.1:5174', env: { RIDESYNC_API_TARGET: 'http://127.0.0.1:8001' }, reuseExistingServer: false },
  ],
})
