const { chromium } = require('playwright');

async function checkLiveMode() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();
  
  console.log('🔴 실거래 모드 확인 중...\n');
  
  try {
    // Navigate to settings tab
    await page.goto('http://158.180.82.112:8080/', { waitUntil: 'networkidle' });
    await page.click('[data-tab="settings"]');
    await page.waitForTimeout(2000);
    
    // Check API response
    const configResponse = await page.evaluate(async () => {
      const response = await fetch('/api/config');
      return await response.json();
    });
    
    console.log('📊 설정 정보:');
    console.log(`   거래 모드: ${configResponse.trading_mode}`);
    console.log(`   최대 포지션: ₩${configResponse.max_position?.toLocaleString()}`);
    console.log(`   일일 손실 한도: ${configResponse.daily_loss_limit}%`);
    console.log(`   신호 임계값: ${configResponse.signal_threshold}`);
    
    // Check displayed text
    const displayedMode = await page.evaluate(() => {
      const bodyText = document.body.textContent;
      if (bodyText.includes('🔴 실거래')) {
        return 'LIVE (실거래)';
      } else if (bodyText.includes('🟡 테스트') || bodyText.includes('dry-run')) {
        return 'DRY-RUN (테스트)';
      } else {
        const modeElement = document.querySelector('.metric-value');
        return modeElement ? modeElement.textContent : 'Unknown';
      }
    });
    
    console.log(`\n🎯 화면 표시: ${displayedMode}`);
    
    if (configResponse.trading_mode === 'live') {
      console.log('\n✅ 실거래 모드가 활성화되어 있습니다!');
      console.log('⚠️  주의: 실제 자금이 사용됩니다!');
    } else {
      console.log('\n⚠️  아직 테스트 모드입니다.');
      console.log('   config.yaml의 mode를 "live"로 설정하세요.');
    }
    
    // Take screenshot
    await page.screenshot({ path: 'screenshots/live_mode_check.png', fullPage: false });
    console.log('\n📸 스크린샷 저장: live_mode_check.png');
    
  } catch (error) {
    console.error('❌ 확인 실패:', error.message);
  } finally {
    await browser.close();
  }
}

// Run the check
checkLiveMode().catch(console.error);