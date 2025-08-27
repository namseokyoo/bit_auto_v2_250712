const { chromium } = require('playwright');

async function debugDashboard() {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();
  
  console.log('🔍 대시보드 디버깅 시작...\n');
  
  // 콘솔 에러 로깅
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log('❌ Console Error:', msg.text());
    }
  });
  
  page.on('pageerror', error => {
    console.log('❌ Page Error:', error.message);
  });
  
  try {
    // 대시보드 접속
    await page.goto('http://158.180.82.112:8080/', { waitUntil: 'networkidle' });
    console.log('✅ 대시보드 로드 완료');
    
    // JavaScript 에러 확인
    const jsErrors = await page.evaluate(() => {
      const errors = [];
      
      // 전역 오류 체크
      if (window.error) {
        errors.push('Window error: ' + window.error);
      }
      
      // jQuery 로드 확인
      if (typeof $ === 'undefined') {
        errors.push('jQuery not loaded');
      }
      
      // 탭 이벤트 리스너 확인
      const tabs = document.querySelectorAll('.tab');
      let hasClickListener = false;
      tabs.forEach(tab => {
        // getEventListeners는 개발자 도구에서만 작동하므로 대체 방법 사용
        if (tab.onclick || tab.addEventListener) {
          hasClickListener = true;
        }
      });
      
      if (!hasClickListener && tabs.length > 0) {
        errors.push('Tab click listeners may not be attached');
      }
      
      return {
        errors: errors,
        tabCount: tabs.length,
        activeTab: document.querySelector('.tab.active')?.textContent,
        contentVisible: document.querySelector('.tab-content')?.style.display
      };
    });
    
    console.log('\n📊 JavaScript 상태:');
    console.log(`   탭 개수: ${jsErrors.tabCount}`);
    console.log(`   활성 탭: ${jsErrors.activeTab}`);
    console.log(`   컨텐츠 표시: ${jsErrors.contentVisible}`);
    
    if (jsErrors.errors.length > 0) {
      console.log('\n❌ 발견된 문제:');
      jsErrors.errors.forEach(err => console.log(`   - ${err}`));
    }
    
    // 탭 클릭 테스트
    console.log('\n🔧 탭 클릭 테스트:');
    
    // AI 분석 탭 클릭
    const aiTabClicked = await page.evaluate(() => {
      const aiTab = document.querySelector('[data-tab="ai"]');
      if (aiTab) {
        aiTab.click();
        return true;
      }
      return false;
    });
    
    if (aiTabClicked) {
      await page.waitForTimeout(1000);
      
      // AI 탭 컨텐츠 확인
      const aiContentVisible = await page.evaluate(() => {
        const aiContent = document.getElementById('ai');
        return aiContent ? aiContent.style.display !== 'none' : false;
      });
      
      console.log(`   AI 탭 클릭: ${aiTabClicked ? '✅' : '❌'}`);
      console.log(`   AI 컨텐츠 표시: ${aiContentVisible ? '✅' : '❌'}`);
    }
    
    // 이벤트 리스너 직접 확인
    const eventCheck = await page.evaluate(() => {
      const tabs = document.querySelectorAll('.tab');
      const results = [];
      
      tabs.forEach((tab, index) => {
        const tabName = tab.getAttribute('data-tab');
        const hasOnclick = !!tab.onclick;
        
        // 클릭 시뮬레이션
        tab.click();
        const content = document.getElementById(tabName);
        const isVisible = content ? content.style.display !== 'none' : false;
        
        results.push({
          name: tabName,
          hasOnclick: hasOnclick,
          isVisible: isVisible
        });
      });
      
      return results;
    });
    
    console.log('\n📋 탭 동작 상태:');
    eventCheck.forEach(tab => {
      console.log(`   ${tab.name}: onclick=${tab.hasOnclick ? '✅' : '❌'}, visible=${tab.isVisible ? '✅' : '❌'}`);
    });
    
    // 스크립트 로드 확인
    const scriptsLoaded = await page.evaluate(() => {
      return {
        hasTabSwitching: typeof switchTab !== 'undefined',
        hasUpdateFunctions: typeof updateSystemStatus !== 'undefined',
        hasjQuery: typeof $ !== 'undefined',
        documentReady: document.readyState
      };
    });
    
    console.log('\n🔌 스크립트 로드 상태:');
    console.log(`   switchTab 함수: ${scriptsLoaded.hasTabSwitching ? '✅' : '❌'}`);
    console.log(`   update 함수들: ${scriptsLoaded.hasUpdateFunctions ? '✅' : '❌'}`);
    console.log(`   jQuery: ${scriptsLoaded.hasjQuery ? '✅' : '❌'}`);
    console.log(`   Document Ready: ${scriptsLoaded.documentReady}`);
    
    // 스크린샷 저장
    await page.screenshot({ path: 'screenshots/debug_dashboard.png', fullPage: true });
    console.log('\n📸 스크린샷 저장: debug_dashboard.png');
    
  } catch (error) {
    console.error('❌ 디버깅 실패:', error.message);
  } finally {
    await browser.close();
  }
}

// 디버깅 실행
debugDashboard().catch(console.error);