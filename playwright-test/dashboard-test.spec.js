const { chromium } = require('playwright');

async function testDashboard() {
  console.log('Starting dashboard test...');
  
  // Launch browser
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();
  
  // Enable console logging
  page.on('console', msg => {
    console.log(`BROWSER: ${msg.type()}: ${msg.text()}`);
  });
  
  // Enable error logging
  page.on('pageerror', err => {
    console.log(`PAGE ERROR: ${err.message}`);
  });

  try {
    // Navigate to the dashboard
    console.log('Navigating to dashboard...');
    await page.goto('http://158.180.82.112:8080/', { 
      waitUntil: 'networkidle',
      timeout: 30000 
    });
    
    // Wait for the page to load completely
    await page.waitForTimeout(3000);
    
    // Take initial screenshot
    console.log('Taking initial screenshot...');
    await page.screenshot({ 
      path: '/Users/namseokyoo/project/bit_auto_v2_250712/screenshot-initial.png',
      fullPage: true 
    });
    
    // Check page title
    const title = await page.title();
    console.log(`Page title: ${title}`);
    
    // Check if Loading messages are present
    const loadingElements = await page.locator('text=Loading').count();
    console.log(`Found ${loadingElements} "Loading..." messages`);
    
    // Check for actual data - look for specific elements that should contain real data
    console.log('Checking for real data...');
    
    // Look for P&L data
    const plElements = await page.locator('text=/P&L|profit|loss|수익|손실/i').count();
    console.log(`Found ${plElements} P&L related elements`);
    
    // Look for strategy data
    const strategyElements = await page.locator('text=/strategy|전략/i').count();
    console.log(`Found ${strategyElements} strategy related elements`);
    
    // Look for trade data
    const tradeElements = await page.locator('text=/trade|거래|buy|sell/i').count();
    console.log(`Found ${tradeElements} trade related elements`);
    
    // Find all tab elements
    console.log('Looking for tabs...');
    const tabs = await page.locator('button[role="tab"], .tab, .nav-link, .tab-button').all();
    console.log(`Found ${tabs.length} potential tab elements`);
    
    // Alternative tab selectors
    const altTabs = await page.locator('text=/Overview|전략|거래|성능|설정/i').all();
    console.log(`Found ${altTabs.length} tabs by text content`);
    
    // Get all clickable elements that might be tabs
    const clickableElements = await page.locator('*:has-text("Overview"):visible, *:has-text("전략"):visible, *:has-text("거래"):visible, *:has-text("성능"):visible, *:has-text("설정"):visible').all();
    console.log(`Found ${clickableElements.length} clickable tab-like elements`);
    
    // Test clicking on tabs
    let tabIndex = 0;
    for (const tab of clickableElements.slice(0, 5)) { // Limit to first 5 to avoid too many
      try {
        const tabText = await tab.textContent();
        console.log(`Testing tab ${tabIndex + 1}: "${tabText}"`);
        
        // Click the tab
        await tab.click();
        await page.waitForTimeout(2000); // Wait for content to load
        
        // Take screenshot after clicking
        await page.screenshot({ 
          path: `/Users/namseokyoo/project/bit_auto_v2_250712/screenshot-tab-${tabIndex + 1}.png`,
          fullPage: true 
        });
        
        console.log(`Screenshot saved for tab ${tabIndex + 1}`);
        tabIndex++;
      } catch (error) {
        console.log(`Error clicking tab ${tabIndex + 1}: ${error.message}`);
      }
    }
    
    // Check for JavaScript errors by examining console messages
    console.log('Test completed successfully');
    
  } catch (error) {
    console.log(`Test error: ${error.message}`);
    
    // Take error screenshot
    await page.screenshot({ 
      path: '/Users/namseokyoo/project/bit_auto_v2_250712/screenshot-error.png',
      fullPage: true 
    });
  } finally {
    await browser.close();
  }
}

// Run the test
testDashboard().catch(console.error);