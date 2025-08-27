const { chromium } = require('playwright');

async function testDashboard() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();
  
  console.log('🚀 Starting comprehensive dashboard testing...');
  
  try {
    // 1. Navigate to dashboard and take initial screenshot
    console.log('📍 Step 1: Navigating to dashboard...');
    await page.goto('http://158.180.82.112:8080/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshots/01_initial_page.png', fullPage: true });
    console.log('✅ Initial screenshot taken');
    
    // 2. Check if loading messages are replaced with actual data
    console.log('📍 Step 2: Checking for loading indicators...');
    const loadingElements = await page.locator('text="Loading"').count();
    const spinners = await page.locator('.spinner, .loading').count();
    console.log(`Found ${loadingElements} loading text elements and ${spinners} spinner elements`);
    
    // Wait a bit more for data to load
    await page.waitForTimeout(5000);
    
    // Take screenshot after waiting for data
    await page.screenshot({ path: 'screenshots/02_after_data_load.png', fullPage: true });
    
    // Get all tab elements
    const tabs = [
      { name: 'Overview', selector: 'a[href="#overview"], button:has-text("Overview")' },
      { name: 'AI Analysis', selector: 'a[href="#ai-analysis"], button:has-text("AI Analysis")' },
      { name: 'Multi-Coin', selector: 'a[href="#multi-coin"], button:has-text("Multi-Coin")' },
      { name: 'Control', selector: 'a[href="#control"], button:has-text("Control")' },
      { name: 'Trades', selector: 'a[href="#trades"], button:has-text("Trades")' },
      { name: 'Settings', selector: 'a[href="#settings"], button:has-text("Settings")' },
      { name: 'Logs', selector: 'a[href="#logs"], button:has-text("Logs")' }
    ];
    
    // 3-9. Test each tab
    for (let i = 0; i < tabs.length; i++) {
      const tab = tabs[i];
      console.log(`📍 Step ${3 + i}: Testing ${tab.name} tab...`);
      
      try {
        // Try to find and click the tab
        const tabElement = page.locator(tab.selector).first();
        const isVisible = await tabElement.isVisible({ timeout: 2000 });
        
        if (isVisible) {
          await tabElement.click();
          await page.waitForTimeout(2000); // Wait for content to load
          
          // Take screenshot
          await page.screenshot({ 
            path: `screenshots/03_${tab.name.toLowerCase().replace(/\s+/g, '_')}_tab.png`, 
            fullPage: true 
          });
          
          // Check for content
          const content = await page.textContent('body');
          const hasData = content && content.length > 1000; // Arbitrary threshold for meaningful content
          
          console.log(`✅ ${tab.name} tab clicked - Content length: ${content ? content.length : 0} chars`);
          
          // Look for specific indicators of loaded data
          const tableRows = await page.locator('table tr, .table-row').count();
          const charts = await page.locator('canvas, .chart, svg').count();
          const dataElements = await page.locator('.value, .price, .percentage, .amount').count();
          
          console.log(`   - Table rows: ${tableRows}`);
          console.log(`   - Charts/graphics: ${charts}`);
          console.log(`   - Data elements: ${dataElements}`);
          
        } else {
          console.log(`❌ ${tab.name} tab not found or not visible`);
        }
      } catch (error) {
        console.log(`❌ Error testing ${tab.name} tab: ${error.message}`);
      }
    }
    
    // 10. Check browser console for errors
    console.log('📍 Step 10: Checking browser console...');
    const consoleLogs = [];
    page.on('console', msg => {
      consoleLogs.push({
        type: msg.type(),
        text: msg.text(),
        location: msg.location()
      });
    });
    
    // Reload page to capture console messages
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(5000);
    
    // Filter for errors and warnings
    const errors = consoleLogs.filter(log => log.type === 'error');
    const warnings = consoleLogs.filter(log => log.type === 'warning');
    
    console.log(`Console errors: ${errors.length}`);
    errors.forEach(error => console.log(`   ERROR: ${error.text}`));
    
    console.log(`Console warnings: ${warnings.length}`);
    warnings.forEach(warning => console.log(`   WARNING: ${warning.text}`));
    
    // Final screenshot
    await page.screenshot({ path: 'screenshots/11_final_state.png', fullPage: true });
    
    console.log('✅ Comprehensive testing completed');
    
  } catch (error) {
    console.error('❌ Test failed:', error);
    await page.screenshot({ path: 'screenshots/error_state.png', fullPage: true });
  } finally {
    await browser.close();
  }
}

// Run the test
testDashboard().catch(console.error);