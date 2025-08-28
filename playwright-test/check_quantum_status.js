const { chromium } = require('playwright');

(async () => {
  console.log('Starting browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log('Navigating to dashboard...');
    await page.goto('http://158.180.82.112:8080/', { 
      waitUntil: 'networkidle',
      timeout: 30000 
    });
    
    // Wait for page to load
    await page.waitForTimeout(3000);
    
    console.log('Looking for Control Panel tab...');
    
    // Try different selectors for the Control Panel tab
    const controlPanelSelectors = [
      'text=제어판',
      '[href="#control-panel"]',
      'a:has-text("제어판")',
      '.nav-tabs a:has-text("제어판")',
      '#control-panel-tab'
    ];
    
    let controlPanelTab = null;
    for (const selector of controlPanelSelectors) {
      try {
        controlPanelTab = await page.waitForSelector(selector, { timeout: 2000 });
        if (controlPanelTab) {
          console.log(`Found control panel tab with selector: ${selector}`);
          break;
        }
      } catch (e) {
        console.log(`Selector ${selector} not found, trying next...`);
      }
    }
    
    if (!controlPanelTab) {
      console.log('Control panel tab not found, taking screenshot of current page...');
      await page.screenshot({ path: 'dashboard-no-control-panel.png', fullPage: true });
      
      // Let's see what tabs are available
      const tabs = await page.$$eval('a', links => 
        links.map(link => ({ 
          text: link.textContent?.trim(), 
          href: link.href,
          id: link.id,
          className: link.className
        })).filter(link => link.text)
      );
      console.log('Available tabs/links:', tabs);
      
      return;
    }
    
    console.log('Clicking on Control Panel tab...');
    await controlPanelTab.click();
    
    // Wait for the control panel content to load
    await page.waitForTimeout(2000);
    
    console.log('Taking screenshot of control panel...');
    await page.screenshot({ 
      path: 'control-panel-full.png', 
      fullPage: true 
    });
    
    // Look for Process Monitor section
    console.log('Looking for Process Monitor section...');
    
    const processMonitorSelectors = [
      'text=프로세스 모니터',
      '.process-monitor',
      '#process-monitor',
      '[data-section="process-monitor"]'
    ];
    
    let processMonitorSection = null;
    for (const selector of processMonitorSelectors) {
      try {
        processMonitorSection = await page.waitForSelector(selector, { timeout: 2000 });
        if (processMonitorSection) {
          console.log(`Found process monitor section with selector: ${selector}`);
          break;
        }
      } catch (e) {
        console.log(`Process monitor selector ${selector} not found, trying next...`);
      }
    }
    
    if (processMonitorSection) {
      console.log('Taking focused screenshot of Process Monitor...');
      await processMonitorSection.screenshot({ 
        path: 'process-monitor-focused.png' 
      });
    }
    
    // Check for Quantum Trading process status
    console.log('Checking Quantum Trading process status...');
    
    const quantumStatusSelectors = [
      'text=Quantum Trading',
      '.quantum-trading',
      '[data-process="quantum-trading"]'
    ];
    
    let quantumStatus = null;
    for (const selector of quantumStatusSelectors) {
      try {
        const element = await page.waitForSelector(selector, { timeout: 2000 });
        if (element) {
          console.log(`Found quantum trading element with selector: ${selector}`);
          
          // Get the parent container to check status
          const parent = await element.evaluateHandle(el => el.closest('.process-item') || el.parentElement);
          
          // Check for status indicators
          const statusInfo = await parent.evaluate(container => {
            const statusIndicator = container.querySelector('.status-indicator, .process-status, .green-circle, .red-circle');
            const pidElement = container.querySelector('.pid, .process-id');
            
            return {
              hasGreenCircle: !!container.querySelector('.green-circle, .status-running'),
              hasRedCircle: !!container.querySelector('.red-circle, .status-stopped'),
              statusText: statusIndicator?.textContent?.trim() || 'Unknown',
              pid: pidElement?.textContent?.trim() || 'N/A',
              containerHTML: container.innerHTML
            };
          });
          
          console.log('Quantum Trading Status:', statusInfo);
          quantumStatus = statusInfo;
          break;
        }
      } catch (e) {
        console.log(`Quantum status selector ${selector} not found, trying next...`);
      }
    }
    
    // Get all process information visible on the page
    console.log('Getting all process information...');
    const allProcessInfo = await page.evaluate(() => {
      const processes = [];
      
      // Look for common process container patterns
      const processContainers = document.querySelectorAll(
        '.process-item, .service-item, .monitor-item, tr, .row'
      );
      
      processContainers.forEach(container => {
        const text = container.textContent?.trim();
        if (text && (
          text.includes('Quantum') || 
          text.includes('Trading') || 
          text.includes('PID') ||
          text.includes('프로세스') ||
          text.includes('상태')
        )) {
          processes.push({
            text: text,
            html: container.innerHTML
          });
        }
      });
      
      return processes;
    });
    
    console.log('All process information found:', allProcessInfo);
    
    // Final screenshot
    console.log('Taking final screenshot...');
    await page.screenshot({ 
      path: 'quantum-status-final.png', 
      fullPage: true 
    });
    
    console.log('Process check completed successfully!');
    
    if (quantumStatus) {
      if (quantumStatus.hasGreenCircle) {
        console.log('✅ Quantum Trading is RUNNING with PID:', quantumStatus.pid);
      } else if (quantumStatus.hasRedCircle) {
        console.log('❌ Quantum Trading is STOPPED');
      } else {
        console.log('⚠️  Quantum Trading status unclear:', quantumStatus.statusText);
      }
    } else {
      console.log('⚠️  Could not find Quantum Trading process information');
    }
    
  } catch (error) {
    console.error('Error during process check:', error);
    await page.screenshot({ path: 'error-screenshot.png', fullPage: true });
  } finally {
    await browser.close();
  }
})();