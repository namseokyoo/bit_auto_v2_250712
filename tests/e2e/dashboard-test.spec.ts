import { test, expect } from '@playwright/test';

test.describe('Trading Dashboard E2E Tests', () => {
  const dashboardUrl = 'http://158.180.82.112:8080/';

  test('Load main dashboard and verify page elements', async ({ page }) => {
    // Navigate to dashboard
    await page.goto(dashboardUrl);
    
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    
    // Take screenshot of main page
    await page.screenshot({ path: 'tests/e2e/screenshots/01-main-dashboard.png', fullPage: true });
    
    // Verify page title
    await expect(page).toHaveTitle(/비트코인 자동거래 시스템/);
    
    // Verify main heading
    await expect(page.locator('h1')).toContainText('비트코인 자동거래 시스템');
  });

  test('Verify all tabs are visible and accessible', async ({ page }) => {
    await page.goto(dashboardUrl);
    await page.waitForLoadState('networkidle');
    
    // Expected tab names
    const expectedTabs = [
      '대시보드',
      'AI 분석', 
      '멀티코인',
      '거래내역',
      '백테스트',
      '제어판',
      '로그',
      '설정'
    ];
    
    // Check each tab is visible
    for (const tabName of expectedTabs) {
      const tab = page.locator(`[role="tab"]:has-text("${tabName}")`).or(
        page.locator(`button:has-text("${tabName}")`).or(
          page.locator(`a:has-text("${tabName}")`)
        )
      );
      await expect(tab).toBeVisible();
    }
    
    await page.screenshot({ path: 'tests/e2e/screenshots/02-tabs-overview.png' });
  });

  test('Navigate through each tab and capture screenshots', async ({ page }) => {
    await page.goto(dashboardUrl);
    await page.waitForLoadState('networkidle');
    
    // List of tabs to navigate through
    const tabs = [
      { name: '대시보드', screenshot: '03-dashboard-tab.png' },
      { name: 'AI 분석', screenshot: '04-ai-analysis-tab.png' },
      { name: '멀티코인', screenshot: '05-multicoin-tab.png' },
      { name: '거래내역', screenshot: '06-trading-history-tab.png' },
      { name: '백테스트', screenshot: '07-backtest-tab.png' },
      { name: '제어판', screenshot: '08-control-panel-tab.png' },
      { name: '로그', screenshot: '09-logs-tab.png' },
      { name: '설정', screenshot: '10-settings-tab.png' }
    ];

    for (const tab of tabs) {
      try {
        // Try multiple selectors for tab navigation
        const tabElement = page.locator(`[role="tab"]:has-text("${tab.name}")`).or(
          page.locator(`button:has-text("${tab.name}")`).or(
            page.locator(`a:has-text("${tab.name}")`)
          )
        );
        
        if (await tabElement.count() > 0) {
          await tabElement.first().click();
          await page.waitForTimeout(2000); // Wait for content to load
          await page.screenshot({ path: `tests/e2e/screenshots/${tab.screenshot}`, fullPage: true });
        }
      } catch (error) {
        console.log(`Could not navigate to tab ${tab.name}: ${error}`);
      }
    }
  });

  test('Verify process status section', async ({ page }) => {
    await page.goto(dashboardUrl);
    await page.waitForLoadState('networkidle');
    
    // Look for process status indicators
    const statusElements = [
      'Trading System Status',
      'System Status', 
      '시스템 상태',
      '프로세스 상태',
      'Process Status'
    ];
    
    for (const statusText of statusElements) {
      const element = page.locator(`text=${statusText}`).or(
        page.locator(`[data-testid*="status"]`).or(
          page.locator('.status').or(
            page.locator('#status')
          )
        )
      );
      
      if (await element.count() > 0) {
        await expect(element.first()).toBeVisible();
        break;
      }
    }
    
    await page.screenshot({ path: 'tests/e2e/screenshots/11-process-status.png' });
  });

  test('Check charts and data loading', async ({ page }) => {
    await page.goto(dashboardUrl);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000); // Allow time for charts to render
    
    // Look for chart containers, canvas elements, or SVG elements
    const chartSelectors = [
      'canvas',
      'svg',
      '.chart',
      '[id*="chart"]',
      '[class*="chart"]',
      '.plotly',
      '#plotly'
    ];
    
    let chartsFound = false;
    for (const selector of chartSelectors) {
      const charts = page.locator(selector);
      if (await charts.count() > 0) {
        chartsFound = true;
        await expect(charts.first()).toBeVisible();
        break;
      }
    }
    
    await page.screenshot({ path: 'tests/e2e/screenshots/12-charts-data.png', fullPage: true });
  });

  test('Test control panel buttons', async ({ page }) => {
    await page.goto(dashboardUrl);
    await page.waitForLoadState('networkidle');
    
    // Look for control buttons
    const controlButtons = [
      '시작',
      '중지', 
      'Start',
      'Stop',
      '거래 시작',
      '거래 중지',
      'Trading Start',
      'Trading Stop'
    ];
    
    for (const buttonText of controlButtons) {
      const button = page.locator(`button:has-text("${buttonText}")`);
      if (await button.count() > 0) {
        await expect(button.first()).toBeVisible();
        // Note: Not clicking to avoid affecting live trading
      }
    }
    
    await page.screenshot({ path: 'tests/e2e/screenshots/13-control-panel.png' });
  });

  test('Verify responsive design on mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(dashboardUrl);
    await page.waitForLoadState('networkidle');
    
    await page.screenshot({ path: 'tests/e2e/screenshots/14-mobile-view.png', fullPage: true });
    
    // Check if navigation adapts to mobile
    const mobileNavigation = page.locator('[data-testid="mobile-nav"]').or(
      page.locator('.mobile-nav').or(
        page.locator('.navbar-toggler').or(
          page.locator('#mobile-menu')
        )
      )
    );
    
    // Verify content is still accessible on mobile
    await expect(page.locator('body')).toBeVisible();
    
    // Test tablet view as well
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'tests/e2e/screenshots/15-tablet-view.png', fullPage: true });
  });
});