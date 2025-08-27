const { chromium } = require('playwright');

async function testKoreanDashboard() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();
  
  console.log('🇰🇷 한글 대시보드 테스트 시작...\n');
  
  try {
    // Navigate to dashboard
    await page.goto('http://158.180.82.112:8080/', { waitUntil: 'networkidle' });
    console.log('✅ 대시보드 로드 완료');
    
    // Wait for data to load
    await page.waitForTimeout(2000);
    
    // Check Korean text
    const koreanCheck = await page.evaluate(() => {
      const bodyText = document.body.textContent;
      const checks = {
        title: bodyText.includes('퀀텀 트레이딩 대시보드'),
        tabs: {
          overview: bodyText.includes('개요'),
          ai: bodyText.includes('AI 분석'),
          multiCoin: bodyText.includes('멀티코인'),
          control: bodyText.includes('제어판'),
          trades: bodyText.includes('거래내역'),
          settings: bodyText.includes('설정'),
          logs: bodyText.includes('로그')
        },
        sections: {
          systemStatus: bodyText.includes('시스템 상태'),
          portfolio: bodyText.includes('포트폴리오'),
          performance: bodyText.includes('오늘의 성과'),
          strategies: bodyText.includes('활성 전략')
        },
        statusText: {
          running: bodyText.includes('실행중') || bodyText.includes('중지됨'),
          tradeStart: bodyText.includes('거래 시작'),
          tradeStop: bodyText.includes('거래 중지')
        }
      };
      return checks;
    });
    
    console.log('\n📊 한글화 확인:');
    console.log(`   제목: ${koreanCheck.title ? '✅' : '❌'} 퀀텀 트레이딩 대시보드`);
    
    console.log('\n   탭 메뉴:');
    console.log(`     개요: ${koreanCheck.tabs.overview ? '✅' : '❌'}`);
    console.log(`     AI 분석: ${koreanCheck.tabs.ai ? '✅' : '❌'}`);
    console.log(`     멀티코인: ${koreanCheck.tabs.multiCoin ? '✅' : '❌'}`);
    console.log(`     제어판: ${koreanCheck.tabs.control ? '✅' : '❌'}`);
    console.log(`     거래내역: ${koreanCheck.tabs.trades ? '✅' : '❌'}`);
    console.log(`     설정: ${koreanCheck.tabs.settings ? '✅' : '❌'}`);
    console.log(`     로그: ${koreanCheck.tabs.logs ? '✅' : '❌'}`);
    
    console.log('\n   섹션:');
    console.log(`     시스템 상태: ${koreanCheck.sections.systemStatus ? '✅' : '❌'}`);
    console.log(`     포트폴리오: ${koreanCheck.sections.portfolio ? '✅' : '❌'}`);
    console.log(`     오늘의 성과: ${koreanCheck.sections.performance ? '✅' : '❌'}`);
    console.log(`     활성 전략: ${koreanCheck.sections.strategies ? '✅' : '❌'}`);
    
    console.log('\n   상태 텍스트:');
    console.log(`     실행 상태: ${koreanCheck.statusText.running ? '✅' : '❌'}`);
    console.log(`     거래 제어: ${koreanCheck.statusText.tradeStart ? '✅' : '❌'}`);
    
    // Check trading mode
    await page.click('[data-tab="settings"]');
    await page.waitForTimeout(1000);
    
    const tradingMode = await page.evaluate(() => {
      const bodyText = document.body.textContent;
      const isLive = bodyText.includes('live') || bodyText.includes('실거래');
      const isDryRun = bodyText.includes('dry-run') || bodyText.includes('테스트');
      return { isLive, isDryRun };
    });
    
    console.log('\n⚠️  거래 모드 확인:');
    if (tradingMode.isLive) {
      console.log('   🔴 실거래 모드 활성화됨! (실제 자금이 사용됩니다)');
    } else if (tradingMode.isDryRun) {
      console.log('   🟡 테스트 모드 (dry-run)');
    } else {
      console.log('   ⚪ 모드 확인 불가');
    }
    
    // Check system status
    await page.click('[data-tab="overview"]');
    await page.waitForTimeout(1000);
    
    const systemRunning = await page.evaluate(() => {
      const statusElement = document.querySelector('.status-indicator');
      return statusElement && statusElement.classList.contains('status-running');
    });
    
    console.log('\n🚀 시스템 상태:');
    if (systemRunning) {
      console.log('   ✅ 시스템 실행중 (거래 진행중)');
    } else {
      console.log('   ⏸️ 시스템 중지됨');
    }
    
    // Take screenshot
    await page.screenshot({ path: 'screenshots/korean_dashboard.png', fullPage: true });
    console.log('\n📸 스크린샷 저장: korean_dashboard.png');
    
    console.log('\n✅ 한글 대시보드 테스트 완료!');
    console.log('🔴 실제 거래 모드가 활성화되어 있습니다. 주의하세요!');
    
  } catch (error) {
    console.error('❌ 테스트 실패:', error.message);
  } finally {
    await browser.close();
  }
}

// Run the test
testKoreanDashboard().catch(console.error);