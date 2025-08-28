const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  try {
    console.log('Navigating to Oracle server dashboard...');
    
    // Navigate to the dashboard
    await page.goto('http://158.180.82.112:8080/', { 
      waitUntil: 'networkidle',
      timeout: 30000 
    });
    
    console.log('Dashboard loaded, looking for Control Panel tab...');
    
    // Wait for the page to load and look for the Control Panel tab
    await page.waitForLoadState('networkidle');
    
    // Try to click on the Control Panel (제어판) tab
    // Look for various possible selectors
    const controlPanelSelectors = [
      'text=제어판',
      '[role="tab"]:has-text("제어판")',
      'a:has-text("제어판")',
      'button:has-text("제어판")',
      '.tab:has-text("제어판")',
      '[data-tab="control"]',
      '[href*="control"]'
    ];
    
    let controlPanelFound = false;
    for (const selector of controlPanelSelectors) {
      try {
        const element = await page.locator(selector).first();
        if (await element.isVisible({ timeout: 2000 })) {
          console.log(`Found Control Panel tab with selector: ${selector}`);
          await element.click();
          controlPanelFound = true;
          break;
        }
      } catch (e) {
        // Continue to next selector
      }
    }
    
    if (!controlPanelFound) {
      console.log('Control Panel tab not found, taking screenshot of current page...');
    } else {
      // Wait for the control panel content to load
      await page.waitForTimeout(2000);
      console.log('Control Panel tab clicked, waiting for content...');
    }
    
    // Look for Process Monitor section
    const processMonitorSelectors = [
      'text=프로세스 모니터',
      '.process-monitor',
      '[id*="process"]',
      'h2:has-text("프로세스")',
      'h3:has-text("프로세스")',
      '.monitor-section'
    ];
    
    let processMonitorFound = false;
    for (const selector of processMonitorSelectors) {
      try {
        const element = await page.locator(selector).first();
        if (await element.isVisible({ timeout: 3000 })) {
          console.log(`Found Process Monitor section with selector: ${selector}`);
          processMonitorFound = true;
          break;
        }
      } catch (e) {
        // Continue to next selector
      }
    }
    
    // Take screenshot of the current page
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const screenshotPath = `dashboard-control-panel-${timestamp}.png`;
    
    await page.screenshot({ 
      path: screenshotPath,
      fullPage: true 
    });
    
    console.log(`Screenshot saved as: ${screenshotPath}`);
    
    // Also try to get the page content to understand the structure
    const pageTitle = await page.title();
    console.log(`Page title: ${pageTitle}`);
    
    // Look for any text containing "Quantum Trading" or "quantum"
    const quantumElements = await page.locator('text=/quantum/i').all();
    console.log(`Found ${quantumElements.length} elements containing 'quantum'`);
    
    // Look for any status indicators
    const statusElements = await page.locator('text=/running|stopped|active|inactive|status/i').all();
    console.log(`Found ${statusElements.length} elements with status-related text`);
    
    if (processMonitorFound) {
      console.log('Process Monitor section found - focusing screenshot on that area');
      
      // Take a more focused screenshot of the process monitor area
      const processMonitorElement = await page.locator('text=프로세스 모니터').first();
      if (await processMonitorElement.isVisible()) {
        const focusedScreenshotPath = `process-monitor-focused-${timestamp}.png`;
        await processMonitorElement.screenshot({ 
          path: focusedScreenshotPath 
        });
        console.log(`Focused screenshot saved as: ${focusedScreenshotPath}`);
      }
    }
    
  } catch (error) {
    console.error('Error occurred:', error.message);
    
    // Take screenshot even if there's an error
    const errorTimestamp = new Date().toISOString().replace(/[:.]/g, '-');
    await page.screenshot({ 
      path: `error-screenshot-${errorTimestamp}.png`,
      fullPage: true 
    });
  } finally {
    await browser.close();
  }
})();