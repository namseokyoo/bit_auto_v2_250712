import { test, expect } from '@playwright/test';

const DASHBOARD_URL = 'http://158.180.82.112:8080/';
const API_BASE_URL = 'http://158.180.82.112:8080/api';

test.describe('Quantum Trading Dashboard E2E Tests', () => {
  
  test.beforeEach(async ({ page }) => {
    // 각 테스트 전에 대시보드 URL로 이동
    await page.goto(DASHBOARD_URL);
    
    // 페이지 로드 완료까지 대기
    await page.waitForLoadState('networkidle');
  });

  test('1. 대시보드 메인 페이지 접속 테스트', async ({ page }) => {
    console.log('🔍 대시보드 메인 페이지 접속 테스트 시작');
    
    // URL 접속 가능 여부 확인
    await expect(page).toHaveURL(DASHBOARD_URL);
    
    // 페이지 타이틀 확인
    await expect(page).toHaveTitle(/Quantum Trading Dashboard/);
    
    // 초기 화면 스크린샷 캡처
    await page.screenshot({ 
      path: 'test-results/01-dashboard-main-page.png',
      fullPage: true 
    });
    
    // 콘솔 에러 확인을 위한 이벤트 리스너
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    // 주요 UI 요소들이 존재하는지 확인
    await expect(page.locator('.nav-tabs')).toBeVisible();
    await expect(page.locator('.tab-content')).toBeVisible();
    
    console.log('✅ 메인 페이지 접속 성공');
    console.log(`발견된 콘솔 에러: ${consoleErrors.length}개`);
    if (consoleErrors.length > 0) {
      console.log('콘솔 에러 내용:', consoleErrors);
    }
  });

  test('2. 탭 기능 테스트', async ({ page }) => {
    console.log('🔍 탭 기능 테스트 시작');
    
    const tabs = [
      { name: '대시보드', selector: 'a[href="#dashboard"]', tabPane: '#dashboard' },
      { name: '거래내역', selector: 'a[href="#trades"]', tabPane: '#trades' },
      { name: '로그', selector: 'a[href="#logs"]', tabPane: '#logs' },
      { name: '설정', selector: 'a[href="#settings"]', tabPane: '#settings' }
    ];
    
    for (const tab of tabs) {
      console.log(`📋 ${tab.name} 탭 테스트 중...`);
      
      // 탭 클릭
      await page.click(tab.selector);
      
      // 탭 활성화 대기
      await page.waitForSelector(`${tab.selector}.active`, { timeout: 3000 });
      
      // 해당 탭 패인이 활성화되었는지 확인
      await expect(page.locator(`${tab.tabPane}.show.active`)).toBeVisible();
      
      // 각 탭의 스크린샷 캡처
      await page.screenshot({ 
        path: `test-results/02-tab-${tab.name.toLowerCase()}.png`,
        fullPage: true 
      });
      
      console.log(`✅ ${tab.name} 탭 전환 성공`);
      
      // 잠시 대기 (UI 안정화)
      await page.waitForTimeout(1000);
    }
  });

  test('3. 데이터 표시 확인', async ({ page }) => {
    console.log('🔍 데이터 표시 확인 테스트 시작');
    
    // 대시보드 탭으로 이동
    await page.click('a[href="#dashboard"]');
    await page.waitForSelector('#dashboard.show.active');
    
    // 시스템 상태 확인
    const systemStatus = await page.locator('.system-status').first();
    if (await systemStatus.isVisible()) {
      const statusText = await systemStatus.textContent();
      console.log('시스템 상태:', statusText);
    }
    
    // 포지션 정보 확인
    const positionCards = await page.locator('.position-card').count();
    console.log(`포지션 카드 개수: ${positionCards}개`);
    
    // 전략별 성과 데이터 확인
    const strategyCards = await page.locator('.strategy-card').count();
    console.log(`전략 카드 개수: ${strategyCards}개`);
    
    // 최근 거래 내역 확인
    const tradeRows = await page.locator('.trade-row').count();
    console.log(`최근 거래 내역 개수: ${tradeRows}개`);
    
    // 데이터 표시 스크린샷
    await page.screenshot({ 
      path: 'test-results/03-data-display.png',
      fullPage: true 
    });
    
    console.log('✅ 데이터 표시 확인 완료');
  });

  test('4. 실시간 업데이트 기능 테스트', async ({ page }) => {
    console.log('🔍 실시간 업데이트 기능 테스트 시작');
    
    // 대시보드 탭으로 이동
    await page.click('a[href="#dashboard"]');
    await page.waitForSelector('#dashboard.show.active');
    
    // 업데이트 전 스크린샷
    await page.screenshot({ 
      path: 'test-results/04-before-update.png',
      fullPage: true 
    });
    
    // 현재 데이터 캡처
    const initialData = await page.locator('.dashboard-content').innerHTML();
    
    console.log('⏳ 자동 업데이트 대기 중... (15초)');
    
    // 15초 대기 (10초 간격 + 여유시간)
    await page.waitForTimeout(15000);
    
    // 업데이트 후 스크린샷
    await page.screenshot({ 
      path: 'test-results/04-after-update.png',
      fullPage: true 
    });
    
    // 데이터 변경 여부 확인
    const updatedData = await page.locator('.dashboard-content').innerHTML();
    const dataChanged = initialData !== updatedData;
    
    console.log(`데이터 변경 여부: ${dataChanged ? '변경됨' : '변경되지 않음'}`);
    
    // 마지막 업데이트 시간 확인
    const lastUpdateElement = await page.locator('.last-updated').first();
    if (await lastUpdateElement.isVisible()) {
      const lastUpdateTime = await lastUpdateElement.textContent();
      console.log('마지막 업데이트 시간:', lastUpdateTime);
    }
    
    console.log('✅ 실시간 업데이트 기능 테스트 완료');
  });

  test('5. 설정 탭 기능 테스트', async ({ page }) => {
    console.log('🔍 설정 탭 기능 테스트 시작');
    
    // 설정 탭으로 이동
    await page.click('a[href="#settings"]');
    await page.waitForSelector('#settings.show.active');
    
    // 거래 시작/중지 버튼 확인
    const startButton = page.locator('button:has-text("거래 시작")');
    const stopButton = page.locator('button:has-text("거래 중지")');
    
    if (await startButton.isVisible()) {
      console.log('거래 시작 버튼 발견');
    }
    
    if (await stopButton.isVisible()) {
      console.log('거래 중지 버튼 발견');
    }
    
    // API 상태 확인
    const apiStatus = await page.locator('.api-status').first();
    if (await apiStatus.isVisible()) {
      const statusText = await apiStatus.textContent();
      console.log('API 상태:', statusText);
    }
    
    // 설정 탭 스크린샷
    await page.screenshot({ 
      path: 'test-results/05-settings-tab.png',
      fullPage: true 
    });
    
    console.log('✅ 설정 탭 기능 테스트 완료');
  });

  test('6. 거래내역 탭 테스트', async ({ page }) => {
    console.log('🔍 거래내역 탭 테스트 시작');
    
    // 거래내역 탭으로 이동
    await page.click('a[href="#trades"]');
    await page.waitForSelector('#trades.show.active');
    
    // 거래 내역 테이블 확인
    const tradeTable = page.locator('.trades-table');
    if (await tradeTable.isVisible()) {
      const rowCount = await page.locator('.trades-table tbody tr').count();
      console.log(`거래 내역 행 개수: ${rowCount}개`);
    }
    
    // 필터링 기능 확인
    const filters = await page.locator('.trade-filter').count();
    console.log(`필터 개수: ${filters}개`);
    
    // 거래내역 탭 스크린샷
    await page.screenshot({ 
      path: 'test-results/06-trades-tab.png',
      fullPage: true 
    });
    
    console.log('✅ 거래내역 탭 테스트 완료');
  });

  test('7. 로그 탭 테스트', async ({ page }) => {
    console.log('🔍 로그 탭 테스트 시작');
    
    // 로그 탭으로 이동
    await page.click('a[href="#logs"]');
    await page.waitForSelector('#logs.show.active');
    
    // 로그 컨테이너 확인
    const logContainer = page.locator('.log-container');
    if (await logContainer.isVisible()) {
      const logEntries = await page.locator('.log-entry').count();
      console.log(`로그 엔트리 개수: ${logEntries}개`);
    }
    
    // 로그 레벨 필터 확인
    const logLevelFilters = await page.locator('.log-level-filter').count();
    console.log(`로그 레벨 필터 개수: ${logLevelFilters}개`);
    
    // 로그 탭 스크린샷
    await page.screenshot({ 
      path: 'test-results/07-logs-tab.png',
      fullPage: true 
    });
    
    console.log('✅ 로그 탭 테스트 완료');
  });

  test('8. API 통신 확인 테스트', async ({ page, request }) => {
    console.log('🔍 API 통신 확인 테스트 시작');
    
    const apiEndpoints = [
      { name: 'Status API', url: `${API_BASE_URL}/status` },
      { name: 'Trades API', url: `${API_BASE_URL}/trades` },
      { name: 'Strategies API', url: `${API_BASE_URL}/strategies` }
    ];
    
    const apiResults = [];
    
    for (const endpoint of apiEndpoints) {
      console.log(`📡 ${endpoint.name} 테스트 중...`);
      
      try {
        const startTime = Date.now();
        const response = await request.get(endpoint.url);
        const endTime = Date.now();
        const responseTime = endTime - startTime;
        
        const result = {
          name: endpoint.name,
          url: endpoint.url,
          status: response.status(),
          responseTime: `${responseTime}ms`,
          success: response.ok()
        };
        
        if (response.ok()) {
          try {
            const data = await response.json();
            result.dataKeys = Object.keys(data);
            console.log(`✅ ${endpoint.name}: ${response.status()} (${responseTime}ms)`);
          } catch (e) {
            result.error = 'Invalid JSON response';
            console.log(`⚠️  ${endpoint.name}: JSON 파싱 오류`);
          }
        } else {
          console.log(`❌ ${endpoint.name}: ${response.status()}`);
        }
        
        apiResults.push(result);
        
      } catch (error) {
        console.log(`❌ ${endpoint.name}: 연결 오류 - ${error.message}`);
        apiResults.push({
          name: endpoint.name,
          url: endpoint.url,
          error: error.message,
          success: false
        });
      }
    }
    
    // API 테스트 결과를 콘솔에 출력
    console.log('\n📊 API 테스트 결과 요약:');
    apiResults.forEach(result => {
      console.log(`- ${result.name}: ${result.success ? '성공' : '실패'} ${result.responseTime || ''}`);
    });
    
    console.log('✅ API 통신 확인 테스트 완료');
  });

  test('9. 종합 테스트 결과 정리', async ({ page }) => {
    console.log('🔍 종합 테스트 결과 정리');
    
    // 최종 대시보드 상태 스크린샷
    await page.goto(DASHBOARD_URL);
    await page.waitForLoadState('networkidle');
    
    await page.screenshot({ 
      path: 'test-results/09-final-dashboard-state.png',
      fullPage: true 
    });
    
    // 페이지 성능 메트릭 수집
    const performanceMetrics = await page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0];
      return {
        loadTime: navigation.loadEventEnd - navigation.loadEventStart,
        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
        totalTime: navigation.loadEventEnd - navigation.fetchStart
      };
    });
    
    console.log('\n📈 성능 메트릭:');
    console.log(`- 페이지 로드 시간: ${performanceMetrics.loadTime}ms`);
    console.log(`- DOM 준비 시간: ${performanceMetrics.domContentLoaded}ms`);
    console.log(`- 총 로드 시간: ${performanceMetrics.totalTime}ms`);
    
    console.log('\n✅ 모든 테스트 완료');
  });
});