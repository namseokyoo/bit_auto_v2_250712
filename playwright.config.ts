import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false, // 순차 실행으로 설정
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1, // 단일 워커로 설정
  reporter: 'html',
  
  use: {
    baseURL: 'http://158.180.82.112:8080/',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    headless: false, // 브라우저 GUI 표시
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    }
  ],

  webServer: {
    command: 'echo "External server at 158.180.82.112:8080"',
    port: 8080,
    reuseExistingServer: true,
  },
});