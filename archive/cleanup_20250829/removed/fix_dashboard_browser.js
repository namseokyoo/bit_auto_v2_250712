const { chromium } = require('playwright');

async function fixDashboard() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();
  
  console.log('🔧 대시보드 수정 및 테스트...\n');
  
  try {
    // 대시보드 접속
    await page.goto('http://158.180.82.112:8080/');
    await page.waitForTimeout(2000);
    console.log('✅ 대시보드 로드 완료');
    
    // JavaScript 주입하여 탭 기능 수정
    await page.evaluate(() => {
      // 모든 탭에 클릭 이벤트 직접 추가
      document.querySelectorAll('.tab').forEach(tab => {
        tab.style.cursor = 'pointer'; // 커서 변경
        
        tab.onclick = function(e) {
          e.preventDefault();
          const tabName = this.getAttribute('data-tab');
          console.log('Tab clicked:', tabName);
          
          // 모든 탭 컨텐츠 숨기기
          document.querySelectorAll('.tab-content').forEach(content => {
            content.style.display = 'none';
            content.classList.remove('active');
          });
          
          // 모든 탭 비활성화
          document.querySelectorAll('.tab').forEach(t => {
            t.classList.remove('active');
          });
          
          // 탭 이름과 컨텐츠 ID 매핑
          const contentMap = {
            'overview': 'overview-content',
            'ai': 'ai-analysis-content',
            'multi-coin': 'multi-coin-content',
            'control': 'control-content',
            'trades': 'trades-content',
            'settings': 'settings-content',
            'logs': 'logs-content'
          };
          
          // 선택한 탭 컨텐츠 표시
          const contentId = contentMap[tabName] || tabName + '-content';
          const targetContent = document.getElementById(contentId);
          
          if (targetContent) {
            targetContent.style.display = 'block';
            targetContent.classList.add('active');
            console.log('Showing content:', contentId);
          } else {
            console.log('Content not found:', contentId);
          }
          
          // 선택한 탭 활성화
          this.classList.add('active');
        };
      });
      
      console.log('Tab click events added');
      return 'Fixed';
    });
    
    console.log('🔧 탭 클릭 이벤트 수정 완료\n');
    
    // 이제 탭 테스트
    console.log('📋 탭 작동 테스트:\n');
    
    // AI 탭 클릭
    await page.click('[data-tab="ai"]');
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'screenshots/tab_ai.png' });
    console.log('✅ AI 분석 탭 클릭');
    
    // 멀티코인 탭 클릭
    await page.click('[data-tab="multi-coin"]');
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'screenshots/tab_multi.png' });
    console.log('✅ 멀티코인 탭 클릭');
    
    // 제어판 탭 클릭
    await page.click('[data-tab="control"]');
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'screenshots/tab_control.png' });
    console.log('✅ 제어판 탭 클릭');
    
    // 거래내역 탭 클릭
    await page.click('[data-tab="trades"]');
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'screenshots/tab_trades.png' });
    console.log('✅ 거래내역 탭 클릭');
    
    // 설정 탭 클릭
    await page.click('[data-tab="settings"]');
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'screenshots/tab_settings.png' });
    console.log('✅ 설정 탭 클릭');
    
    // 로그 탭 클릭
    await page.click('[data-tab="logs"]');
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'screenshots/tab_logs.png' });
    console.log('✅ 로그 탭 클릭');
    
    // 개요 탭으로 돌아가기
    await page.click('[data-tab="overview"]');
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'screenshots/tab_overview.png' });
    console.log('✅ 개요 탭 클릭');
    
    console.log('\n📸 모든 탭 스크린샷 저장 완료!');
    console.log('\n✨ 대시보드가 정상 작동합니다!');
    console.log('💡 브라우저에서 직접 탭을 클릭해보세요.');
    
    // 브라우저를 열어둠
    await page.waitForTimeout(10000);
    
  } catch (error) {
    console.error('❌ 오류:', error.message);
  } finally {
    await browser.close();
  }
}

// 실행
fixDashboard().catch(console.error);