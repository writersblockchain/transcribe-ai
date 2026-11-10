import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './visual-tests',
  use: { baseURL: 'http://127.0.0.1:6006', browserName: 'chromium' },
  webServer: { command: 'npm run storybook -- --ci --host 127.0.0.1', url: 'http://127.0.0.1:6006', reuseExistingServer: !process.env.CI, timeout: 120000 },
});
