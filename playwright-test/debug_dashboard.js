const { chromium } = require('playwright');

async function debugDashboard() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();
  
  console.log('🔍 Starting detailed dashboard debugging...');
  
  // Listen to all network requests
  const networkLogs = [];
  page.on('request', request => {
    networkLogs.push({
      type: 'REQUEST',
      url: request.url(),
      method: request.method(),
      headers: request.headers()
    });
    console.log(`📤 ${request.method()} ${request.url()}`);
  });
  
  page.on('response', response => {
    networkLogs.push({
      type: 'RESPONSE',
      url: response.url(),
      status: response.status(),
      statusText: response.statusText()
    });
    console.log(`📥 ${response.status()} ${response.url()}`);
  });
  
  // Listen to console messages
  page.on('console', msg => {
    console.log(`🖥️  CONSOLE ${msg.type()}: ${msg.text()}`);
  });
  
  try {
    // Navigate to dashboard
    console.log('📍 Navigating to dashboard...');
    await page.goto('http://158.180.82.112:8080/', { waitUntil: 'networkidle' });
    
    // Wait for page to load
    await page.waitForTimeout(5000);
    
    // Check if API endpoints are being called
    console.log('\n📊 Analyzing API calls...');
    const apiCalls = networkLogs.filter(log => 
      log.url.includes('/api/') || 
      log.url.includes('/status') || 
      log.url.includes('/portfolio') || 
      log.url.includes('/performance')
    );
    
    console.log(`Found ${apiCalls.length} API-related requests`);
    apiCalls.forEach(call => {
      console.log(`   - ${call.type}: ${call.method || call.status} ${call.url}`);
    });
    
    // Try to make direct API calls to check if backend is responding
    console.log('\n🔧 Testing direct API calls...');
    
    const apiTests = [
      '/api/system-status',
      '/api/portfolio',
      '/api/performance/today',
      '/api/strategies',
      '/api/trades/recent'
    ];
    
    for (const endpoint of apiTests) {
      try {
        const response = await page.goto(`http://158.180.82.112:8080${endpoint}`);
        const contentType = response.headers()['content-type'] || '';
        const status = response.status();
        
        console.log(`   ${endpoint}: ${status} (${contentType})`);
        
        if (contentType.includes('application/json')) {
          const data = await response.json();
          console.log(`     JSON keys: ${Object.keys(data).join(', ')}`);
        } else {
          const text = await response.text();
          console.log(`     Response length: ${text.length} chars`);
          if (text.length < 200) {
            console.log(`     Content preview: ${text.substring(0, 100)}...`);
          }
        }
      } catch (error) {
        console.log(`   ${endpoint}: ERROR - ${error.message}`);
      }
    }
    
    // Go back to main page
    await page.goto('http://158.180.82.112:8080/', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    
    // Check if JavaScript is loading data
    console.log('\n🧩 Checking JavaScript execution...');
    
    const jsCheck = await page.evaluate(() => {
      return {
        hasJQuery: typeof $ !== 'undefined',
        hasFetch: typeof fetch !== 'undefined',
        hasSetInterval: typeof setInterval !== 'undefined',
        docReadyState: document.readyState,
        scriptTags: document.querySelectorAll('script').length,
        loadingElements: document.querySelectorAll('[innerHTML*="Loading"], [textContent*="Loading"]').length,
        dataElements: document.querySelectorAll('.value, .price, .percentage').length
      };
    });
    
    console.log('JavaScript environment:', jsCheck);
    
    // Check specific DOM elements
    const domCheck = await page.evaluate(() => {
      const systemStatus = document.querySelector('[data-id="system-status"], .system-status');
      const portfolio = document.querySelector('[data-id="portfolio"], .portfolio');
      const performance = document.querySelector('[data-id="performance"], .performance');
      
      return {
        systemStatusExists: !!systemStatus,
        portfolioExists: !!portfolio,
        performanceExists: !!performance,
        systemStatusContent: systemStatus?.textContent || 'Not found',
        portfolioContent: portfolio?.textContent || 'Not found',
        performanceContent: performance?.textContent || 'Not found'
      };
    });
    
    console.log('\n🎯 DOM element check:', domCheck);
    
    // Try to trigger data refresh manually
    console.log('\n🔄 Attempting manual data refresh...');
    
    const refreshResult = await page.evaluate(() => {
      // Look for refresh functions
      const refreshFunctions = [
        'refreshData',
        'loadData',
        'updateDashboard',
        'fetchData',
        'getData'
      ];
      
      const available = [];
      refreshFunctions.forEach(funcName => {
        if (typeof window[funcName] === 'function') {
          available.push(funcName);
          try {
            window[funcName]();
          } catch (e) {
            console.log(`Error calling ${funcName}:`, e);
          }
        }
      });
      
      return {
        availableFunctions: available,
        windowKeys: Object.keys(window).filter(key => key.includes('refresh') || key.includes('load') || key.includes('data'))
      };
    });
    
    console.log('Refresh attempt result:', refreshResult);
    
    // Wait and take final screenshot
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshots/debug_final.png', fullPage: true });
    
    console.log('\n✅ Debug analysis completed');
    
  } catch (error) {
    console.error('❌ Debug failed:', error);
  } finally {
    await browser.close();
  }
}

// Run the debug
debugDashboard().catch(console.error);