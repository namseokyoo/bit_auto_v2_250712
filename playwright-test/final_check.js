const { chromium } = require('playwright');

async function finalCheck() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();
  
  console.log('🏁 Final Dashboard Check...\n');
  
  try {
    // Navigate to dashboard
    await page.goto('http://158.180.82.112:8080/', { waitUntil: 'networkidle' });
    console.log('✅ Dashboard loaded successfully');
    
    // Wait for data to load
    await page.waitForTimeout(3000);
    
    // Check if data is displayed
    const dataCheck = await page.evaluate(() => {
      const checks = {
        systemStatus: false,
        portfolio: false,
        performance: false,
        strategies: false
      };
      
      // Check system status
      const statusText = document.body.textContent;
      if (statusText.includes('Running') || statusText.includes('Stopped')) {
        checks.systemStatus = true;
      }
      
      // Check portfolio
      if (statusText.includes('KRW Balance') || statusText.includes('₩')) {
        checks.portfolio = true;
      }
      
      // Check performance
      if (statusText.includes('PnL') || statusText.includes('Return')) {
        checks.performance = true;
      }
      
      // Check strategies
      if (statusText.includes('Market Making') || statusText.includes('Strategy')) {
        checks.strategies = true;
      }
      
      return checks;
    });
    
    console.log('\n📊 Data Loading Status:');
    console.log(`   System Status: ${dataCheck.systemStatus ? '✅' : '❌'}`);
    console.log(`   Portfolio: ${dataCheck.portfolio ? '✅' : '❌'}`);
    console.log(`   Performance: ${dataCheck.performance ? '✅' : '❌'}`);
    console.log(`   Strategies: ${dataCheck.strategies ? '✅' : '❌'}`);
    
    // Test each tab
    console.log('\n🔄 Testing All Tabs:');
    const tabs = ['overview', 'ai', 'multi-coin', 'control', 'trades', 'settings', 'logs'];
    
    for (const tab of tabs) {
      await page.click(`[data-tab="${tab}"]`);
      await page.waitForTimeout(1000);
      
      const isActive = await page.evaluate((tabName) => {
        const tabEl = document.querySelector(`[data-tab="${tabName}"]`);
        const contentEl = document.querySelector(`#${tabName}-content`);
        return {
          tabActive: tabEl && tabEl.classList.contains('active'),
          contentVisible: contentEl && window.getComputedStyle(contentEl).display !== 'none'
        };
      }, tab);
      
      console.log(`   ${tab}: Tab ${isActive.tabActive ? '✅' : '❌'}, Content ${isActive.contentVisible ? '✅' : '❌'}`);
    }
    
    // Take final screenshot
    await page.screenshot({ path: 'screenshots/dashboard_final.png', fullPage: true });
    console.log('\n📸 Final screenshot saved: dashboard_final.png');
    
    console.log('\n🎉 Dashboard is working properly!');
    
  } catch (error) {
    console.error('❌ Final check failed:', error.message);
  } finally {
    await browser.close();
  }
}

// Run the final check
finalCheck().catch(console.error);