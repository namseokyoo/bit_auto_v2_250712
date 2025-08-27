const { chromium } = require('playwright');

async function testTabs() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();
  
  console.log('🔍 Testing dashboard tab functionality...\n');
  
  // Listen to console messages
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log(`❌ JS ERROR: ${msg.text()}`);
    } else {
      console.log(`📝 CONSOLE ${msg.type()}: ${msg.text()}`);
    }
  });
  
  // Listen for uncaught exceptions
  page.on('pageerror', error => {
    console.log(`🚨 PAGE ERROR: ${error.message}`);
  });
  
  try {
    // Navigate to dashboard
    console.log('📍 Navigating to dashboard...');
    await page.goto('http://158.180.82.112:8080/', { waitUntil: 'networkidle' });
    
    // Wait for tabs to be available
    await page.waitForTimeout(2000);
    
    // Check initial state
    const initialActiveTab = await page.evaluate(() => {
      const activeTab = document.querySelector('.tab.active');
      return activeTab ? activeTab.textContent : 'No active tab';
    });
    console.log(`\n✅ Initial active tab: ${initialActiveTab}`);
    
    // Get all tabs
    const tabs = await page.evaluate(() => {
      const tabElements = document.querySelectorAll('.tab');
      return Array.from(tabElements).map(tab => ({
        text: tab.textContent,
        dataTab: tab.getAttribute('data-tab'),
        hasClickListener: typeof tab.onclick === 'function' || tab.hasAttribute('onclick')
      }));
    });
    
    console.log('\n📋 Found tabs:');
    tabs.forEach(tab => {
      console.log(`   - ${tab.text} (data-tab: ${tab.dataTab}, has onclick: ${tab.hasClickListener})`);
    });
    
    // Try clicking each tab
    console.log('\n🖱️ Testing tab clicks:');
    for (const tab of tabs) {
      if (tab.dataTab && tab.dataTab !== 'overview') {
        console.log(`\n   Clicking: ${tab.text}`);
        
        // Click the tab
        await page.click(`[data-tab="${tab.dataTab}"]`);
        await page.waitForTimeout(1000);
        
        // Check if tab became active
        const isActive = await page.evaluate((tabName) => {
          const tab = document.querySelector(`[data-tab="${tabName}"]`);
          return tab && tab.classList.contains('active');
        }, tab.dataTab);
        
        // Check if content changed
        const visibleContent = await page.evaluate((tabName) => {
          const content = document.querySelector(`#${tabName}-content`);
          if (!content) return 'Content div not found';
          const style = window.getComputedStyle(content);
          return {
            exists: true,
            displayed: style.display !== 'none',
            visibility: style.visibility,
            text: content.textContent.substring(0, 100)
          };
        }, tab.dataTab);
        
        console.log(`      Tab active: ${isActive ? '✅' : '❌'}`);
        console.log(`      Content displayed: ${visibleContent.displayed ? '✅' : '❌'}`);
        if (visibleContent.text) {
          console.log(`      Content preview: ${visibleContent.text}...`);
        }
      }
    }
    
    // Check if switchTab function exists
    const functionCheck = await page.evaluate(() => {
      return {
        switchTabExists: typeof switchTab === 'function',
        showTabExists: typeof showTab === 'function',
        refreshDataExists: typeof refreshData === 'function'
      };
    });
    
    console.log('\n📊 Function availability:');
    console.log(`   switchTab: ${functionCheck.switchTabExists ? '✅' : '❌'}`);
    console.log(`   showTab: ${functionCheck.showTabExists ? '✅' : '❌'}`);
    console.log(`   refreshData: ${functionCheck.refreshDataExists ? '✅' : '❌'}`);
    
    // Try calling switchTab directly
    if (functionCheck.switchTabExists) {
      console.log('\n🔧 Testing direct switchTab calls:');
      
      const testTabs = ['ai', 'multi-coin', 'trades'];
      for (const tabName of testTabs) {
        console.log(`   Calling switchTab('${tabName}')...`);
        
        await page.evaluate((name) => {
          if (typeof switchTab === 'function') {
            switchTab(name);
          }
        }, tabName);
        
        await page.waitForTimeout(500);
        
        const result = await page.evaluate((name) => {
          const tab = document.querySelector(`[data-tab="${name}"]`);
          const content = document.querySelector(`#${name}-content`);
          return {
            tabActive: tab && tab.classList.contains('active'),
            contentVisible: content && window.getComputedStyle(content).display !== 'none'
          };
        }, tabName);
        
        console.log(`      Tab active: ${result.tabActive ? '✅' : '❌'}, Content visible: ${result.contentVisible ? '✅' : '❌'}`);
      }
    }
    
    // Take screenshots of each tab
    console.log('\n📸 Taking screenshots of each tab state...');
    const screenshotTabs = ['overview', 'ai', 'multi-coin', 'trades'];
    for (let i = 0; i < screenshotTabs.length; i++) {
      const tabName = screenshotTabs[i];
      await page.click(`[data-tab="${tabName}"]`);
      await page.waitForTimeout(1500);
      await page.screenshot({ 
        path: `screenshots/tab_${i+1}_${tabName}.png`, 
        fullPage: false 
      });
      console.log(`   Saved: tab_${i+1}_${tabName}.png`);
    }
    
    console.log('\n✅ Tab testing completed');
    
  } catch (error) {
    console.error('❌ Test failed:', error);
  } finally {
    await browser.close();
  }
}

// Run the test
testTabs().catch(console.error);