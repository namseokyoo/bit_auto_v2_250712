const { chromium } = require('playwright');

async function testControlPanel() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();
  
  console.log('🎮 제어판 테스트 시작...\n');
  
  try {
    // 대시보드 접속
    await page.goto('http://158.180.82.112:8080/', { waitUntil: 'networkidle' });
    console.log('✅ 대시보드 로드 완료');
    
    // 제어판 탭 클릭
    await page.click('[data-tab="control"]');
    await page.waitForTimeout(2000);
    console.log('✅ 제어판 탭 활성화');
    
    // 제어판 요소 확인
    const controlPanel = await page.evaluate(() => {
      const panel = document.getElementById('control');
      if (!panel) return null;
      
      return {
        visible: panel.style.display !== 'none',
        hasModeBtns: !!document.getElementById('mode-dryrun') && !!document.getElementById('mode-live'),
        hasSystemBtns: document.querySelectorAll('.btn').length > 0,
        currentMode: document.getElementById('current-mode')?.textContent || 'N/A',
        processStatus: document.getElementById('process-status')?.textContent || 'N/A'
      };
    });
    
    if (!controlPanel) {
      console.log('❌ 제어판을 찾을 수 없습니다.');
      console.log('페이지 HTML 확인 중...');
      
      const tabs = await page.evaluate(() => {
        const tabButtons = document.querySelectorAll('[data-tab]');
        return Array.from(tabButtons).map(tab => tab.textContent);
      });
      console.log('사용 가능한 탭:', tabs);
    } else {
      console.log('\n📊 제어판 상태:');
      console.log(`   표시 여부: ${controlPanel.visible ? '✅' : '❌'}`);
      console.log(`   모드 전환 버튼: ${controlPanel.hasModeBtns ? '✅' : '❌'}`);
      console.log(`   시스템 제어 버튼: ${controlPanel.hasSystemBtns ? '✅' : '❌'}`);
      console.log(`   현재 모드: ${controlPanel.currentMode}`);
      console.log(`   프로세스 상태: ${controlPanel.processStatus}`);
    }
    
    // API 테스트
    console.log('\n📡 API 테스트:');
    
    // 거래 모드 조회
    const modeResponse = await page.evaluate(async () => {
      try {
        const response = await fetch('/api/trading-mode');
        return await response.json();
      } catch (error) {
        return { error: error.message };
      }
    });
    
    console.log('   거래 모드 API:', modeResponse.error ? `❌ ${modeResponse.error}` : '✅');
    if (!modeResponse.error) {
      console.log(`     - 현재 모드: ${modeResponse.current_mode}`);
      console.log(`     - 설정 모드: ${modeResponse.config_mode}`);
      console.log(`     - 프로세스 실행: ${modeResponse.process_running ? '예' : '아니오'}`);
    }
    
    // 스크린샷 저장
    await page.screenshot({ path: 'screenshots/control_panel.png', fullPage: true });
    console.log('\n📸 스크린샷 저장: control_panel.png');
    
    // 모드 전환 버튼 테스트 (실제로 클릭하지는 않음)
    const modeButtons = await page.evaluate(() => {
      const dryBtn = document.getElementById('mode-dryrun');
      const liveBtn = document.getElementById('mode-live');
      return {
        dryRun: dryBtn ? dryBtn.textContent.trim() : null,
        live: liveBtn ? liveBtn.textContent.trim() : null
      };
    });
    
    console.log('\n🔘 모드 전환 버튼:');
    if (modeButtons.dryRun) {
      console.log(`   테스트 모드: "${modeButtons.dryRun}"`);
    } else {
      console.log('   테스트 모드 버튼을 찾을 수 없음');
    }
    
    if (modeButtons.live) {
      console.log(`   실거래 모드: "${modeButtons.live}"`);
    } else {
      console.log('   실거래 모드 버튼을 찾을 수 없음');
    }
    
    console.log('\n✅ 제어판 테스트 완료!');
    console.log('💡 이제 제어판에서 실거래/테스트 모드를 전환할 수 있습니다.');
    
  } catch (error) {
    console.error('❌ 테스트 실패:', error.message);
  } finally {
    await browser.close();
  }
}

// 테스트 실행
testControlPanel().catch(console.error);