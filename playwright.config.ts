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
    screenshot: 'on',
    video: 'retain-on-failure',
    headless: true, // 헤드리스 모드로 변경
    actionTimeout: 30000,
    navigationTimeout: 30000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    }
  ],

  // External server - no need for webServer config
});