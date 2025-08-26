const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  try {
    console.log('대시보드에 접속 중...');
    await page.goto('http://158.180.82.112:8080/', { waitUntil: 'networkidle' });
    
    // 페이지 로딩 대기
    await page.waitForTimeout(3000);
    
    console.log('초기 스크린샷 촬영 중...');
    await page.screenshot({ 
      path: 'dashboard-initial.png', 
      fullPage: true 
    });
    
    // 각 카드 확인
    const cards = [
      'System Status Card',
      'Account Information Card', 
      'Today\'s Performance Card',
      'Strategy Signal Strengths Card',
      'Recent Trades Card'
    ];
    
    for (const card of cards) {
      console.log(`${card} 확인 중...`);
      
      // 카드별 요소 확인
      try {
        if (card === 'System Status Card') {
          const statusElement = await page.$('.status-indicator');
          if (statusElement) {
            const status = await statusElement.textContent();
            console.log(`시스템 상태: ${status}`);
          }
        }
        
        if (card === 'Account Information Card') {
          const krwBalance = await page.$('[data-label="KRW Balance"]');
          const btcBalance = await page.$('[data-label="BTC Balance"]');
          if (krwBalance) {
            const krw = await krwBalance.textContent();
            console.log(`KRW 잔액: ${krw}`);
          }
          if (btcBalance) {
            const btc = await btcBalance.textContent();
            console.log(`BTC 잔액: ${btc}`);
          }
        }
        
        if (card === 'Today\'s Performance Card') {
          const dailyPL = await page.$('[data-label="Daily P&L"]');
          if (dailyPL) {
            const pl = await dailyPL.textContent();
            console.log(`일일 손익: ${pl}`);
          }
        }
        
        if (card === 'Strategy Signal Strengths Card') {
          const strategies = ['market-making', 'stat-arb', 'microstructure', 'momentum', 'mean-reversion'];
          for (const strategy of strategies) {
            const element = await page.$(`[data-strategy="${strategy}"]`);
            if (element) {
              const signal = await element.textContent();
              console.log(`${strategy} 신호: ${signal}`);
            }
          }
        }
        
      } catch (error) {
        console.log(`${card} 확인 중 오류: ${error.message}`);
      }
    }
    
    // 30초 동안 대시보드 모니터링
    console.log('30초간 업데이트 모니터링 시작...');
    for (let i = 0; i < 6; i++) {
      await page.waitForTimeout(5000);
      console.log(`${(i + 1) * 5}초 경과...`);
      
      // 중간 스크린샷
      if (i === 2) {
        await page.screenshot({ 
          path: 'dashboard-15sec.png', 
          fullPage: true 
        });
        console.log('15초 경과 스크린샷 촬영');
      }
    }
    
    console.log('최종 스크린샷 촬영 중...');
    await page.screenshot({ 
      path: 'dashboard-final.png', 
      fullPage: true 
    });
    
    console.log('대시보드 점검 완료');
    
  } catch (error) {
    console.error('대시보드 접속 실패:', error);
    await page.screenshot({ 
      path: 'dashboard-error.png', 
      fullPage: true 
    });
  }
  
  await browser.close();
})();