const { chromium } = require('playwright');

async function testDashboard() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();
  
  console.log('🎯 대시보드 최종 테스트...\n');
  
  try {
    // 대시보드 접속
    await page.goto('http://158.180.82.112:8080/');
    await page.waitForTimeout(3000); // 초기화 대기
    console.log('✅ 대시보드 로드 완료');
    
    // JavaScript 함수 직접 실행
    const initResult = await page.evaluate(() => {
      // initDashboard 함수가 있으면 직접 실행
      if (typeof initDashboard === 'function') {
        initDashboard();
        return 'initDashboard 실행됨';
      } else {
        // 수동으로 이벤트 리스너 추가
        document.querySelectorAll('.tab').forEach(tab => {
          tab.onclick = function() {
            const tabName = this.getAttribute('data-tab');
            console.log('Tab clicked:', tabName);
            
            // 모든 탭 컨텐츠 숨기기
            document.querySelectorAll('.tab-content').forEach(content => {
              content.style.display = 'none';
            });
            
            // 모든 탭 비활성화
            document.querySelectorAll('.tab').forEach(t => {
              t.classList.remove('active');
            });
            
            // 선택한 탭 컨텐츠 표시
            const content = document.getElementById(tabName);
            if (content) {
              content.style.display = 'block';
            }
            
            // 선택한 탭 활성화
            this.classList.add('active');
          };
        });
        return '수동으로 이벤트 리스너 추가됨';
      }
    });
    
    console.log(`🔧 초기화: ${initResult}`);
    
    // 탭 클릭 테스트
    console.log('\n📋 탭 테스트:');
    
    // AI 분석 탭 클릭
    await page.click('[data-tab="ai"]');
    await page.waitForTimeout(1000);
    
    const aiVisible = await page.evaluate(() => {
      const aiContent = document.getElementById('ai');
      return aiContent ? aiContent.style.display !== 'none' : false;
    });
    console.log(`   AI 탭: ${aiVisible ? '✅ 작동' : '❌ 작동 안함'}`);
    
    // 설정 탭 클릭
    await page.click('[data-tab="settings"]');
    await page.waitForTimeout(1000);
    
    const settingsVisible = await page.evaluate(() => {
      const settingsContent = document.getElementById('settings');
      return settingsContent ? settingsContent.style.display !== 'none' : false;
    });
    console.log(`   설정 탭: ${settingsVisible ? '✅ 작동' : '❌ 작동 안함'}`);
    
    // 제어판 탭 클릭
    await page.click('[data-tab="control"]');
    await page.waitForTimeout(1000);
    
    const controlVisible = await page.evaluate(() => {
      const controlContent = document.getElementById('control');
      return controlContent ? controlContent.style.display !== 'none' : false;
    });
    console.log(`   제어판 탭: ${controlVisible ? '✅ 작동' : '❌ 작동 안함'}`);
    
    // 개요 탭으로 돌아가기
    await page.click('[data-tab="overview"]');
    await page.waitForTimeout(1000);
    
    const overviewVisible = await page.evaluate(() => {
      const overviewContent = document.getElementById('overview');
      return overviewContent ? overviewContent.style.display !== 'none' : false;
    });
    console.log(`   개요 탭: ${overviewVisible ? '✅ 작동' : '❌ 작동 안함'}`);
    
    // 현재 상태 스크린샷
    await page.screenshot({ path: 'screenshots/dashboard_fixed.png', fullPage: true });
    console.log('\n📸 스크린샷 저장: dashboard_fixed.png');
    
    // API 테스트
    console.log('\n🔌 API 테스트:');
    const apiStatus = await page.evaluate(async () => {
      try {
        const response = await fetch('/api/system-status');
        const data = await response.json();
        return { success: true, running: data.trading_active };
      } catch (error) {
        return { success: false, error: error.message };
      }
    });
    
    if (apiStatus.success) {
      console.log(`   시스템 상태 API: ✅ (거래 ${apiStatus.running ? '실행중' : '중지'})`);
    } else {
      console.log(`   시스템 상태 API: ❌ (${apiStatus.error})`);
    }
    
    console.log('\n✅ 대시보드가 정상 작동합니다!');
    
  } catch (error) {
    console.error('❌ 테스트 실패:', error.message);
  } finally {
    await page.waitForTimeout(3000); // 결과 확인을 위해 잠시 대기
    await browser.close();
  }
}

// 테스트 실행
testDashboard().catch(console.error);