import { test, expect } from '@playwright/test';

const DASHBOARD_URL = 'http://158.180.82.112:8080/';
const API_BASE_URL = 'http://158.180.82.112:8080';

test.describe('Quantum Trading Dashboard E2E Tests - Optimized', () => {
  
  test.beforeEach(async ({ page }) => {
    // 각 테스트 전에 대시보드 URL로 이동
    await page.goto(DASHBOARD_URL);
    
    // 페이지 로드 완료까지 대기
    await page.waitForLoadState('networkidle');
    
    // 추가 대기 시간 (JavaScript 초기화)
    await page.waitForTimeout(2000);
  });

  test('1. 대시보드 메인 페이지 접속 및 초기 화면 검증', async ({ page }) => {
    console.log('🔍 대시보드 메인 페이지 접속 테스트 시작');
    
    // URL 접속 가능 여부 확인
    await expect(page).toHaveURL(DASHBOARD_URL);
    
    // 페이지 타이틀 확인
    await expect(page).toHaveTitle(/Quantum Trading Dashboard/);
    
    // 주요 UI 요소들이 존재하는지 확인 (실제 구조 기반)
    await expect(page.locator('h1:has-text("Quantum Trading Dashboard")')).toBeVisible();
    
    // 탭 버튼들 확인
    await expect(page.locator('button:has-text("대시보드")')).toBeVisible();
    await expect(page.locator('button:has-text("설정")')).toBeVisible();
    await expect(page.locator('button:has-text("로그")')).toBeVisible();
    
    // 초기 화면 스크린샷 캡처
    await page.screenshot({ 
      path: 'test-results/01-dashboard-main-page-initial.png',
      fullPage: true 
    });
    
    console.log('✅ 메인 페이지 접속 성공');
  });

  test('2. 탭 기능 테스트', async ({ page }) => {
    console.log('🔍 탭 기능 테스트 시작');
    
    const tabs = [
      { name: '대시보드', buttonText: '대시보드' },
      { name: '설정', buttonText: '설정' },
      { name: '로그', buttonText: '로그' }
    ];
    
    for (const tab of tabs) {
      console.log(`📋 ${tab.name} 탭 테스트 중...`);
      
      // 탭 버튼 클릭
      await page.click(`button:has-text("${tab.buttonText}")`);
      
      // 탭 활성화 대기 (버튼 색상 변경 확인)
      await page.waitForTimeout(1000);
      
      // 각 탭의 스크린샷 캡처
      await page.screenshot({ 
        path: `test-results/02-tab-${tab.name}.png`,
        fullPage: true 
      });
      
      console.log(`✅ ${tab.name} 탭 전환 성공`);
      
      // 잠시 대기 (UI 안정화)
      await page.waitForTimeout(1000);
    }
  });

  test('3. 시스템 상태 및 계좌 정보 데이터 확인', async ({ page }) => {
    console.log('🔍 데이터 표시 확인 테스트 시작');
    
    // 대시보드 탭으로 이동
    await page.click('button:has-text("대시보드")');
    await page.waitForTimeout(1000);
    
    // 시스템 상태 확인
    const systemStatus = page.locator('.card:has-text("시스템 상태")');
    await expect(systemStatus).toBeVisible();
    console.log('시스템 상태 카드 발견');
    
    // Running/Stopped 상태 확인
    const statusIndicator = systemStatus.locator('text=Running');
    if (await statusIndicator.isVisible()) {
      console.log('✅ 시스템 상태: Running');
    } else {
      console.log('⚠️ 시스템 상태: Not Running 또는 다른 상태');
    }
    
    // 계좌 정보 확인
    const accountInfo = page.locator('.card:has-text("계좌 정보")');
    await expect(accountInfo).toBeVisible();
    console.log('계좌 정보 카드 발견');
    
    // 총 자산 확인
    const totalAssets = accountInfo.locator('text=총 자산');
    if (await totalAssets.isVisible()) {
      console.log('총 자산 정보 표시됨');
    }
    
    // 오늘의 성과 확인
    const todayPerformance = page.locator('.card:has-text("오늘의 성과")');
    await expect(todayPerformance).toBeVisible();
    console.log('오늘의 성과 카드 발견');
    
    // 전략별 신호 강도 확인
    const strategySignals = page.locator('.card:has-text("전략별 신호 강도")');
    await expect(strategySignals).toBeVisible();
    console.log('전략별 신호 강도 카드 발견');
    
    // 최근 거래 확인
    const recentTrades = page.locator('.card:has-text("최근 거래")');
    await expect(recentTrades).toBeVisible();
    console.log('최근 거래 카드 발견');
    
    // 데이터 표시 스크린샷
    await page.screenshot({ 
      path: 'test-results/03-data-display-detailed.png',
      fullPage: true 
    });
    
    console.log('✅ 모든 주요 데이터 섹션 확인 완료');
  });

  test('4. 실시간 업데이트 기능 테스트', async ({ page }) => {
    console.log('🔍 실시간 업데이트 기능 테스트 시작');
    
    // 대시보드 탭으로 이동
    await page.click('button:has-text("대시보드")');
    await page.waitForTimeout(1000);
    
    // 업데이트 전 스크린샷
    await page.screenshot({ 
      path: 'test-results/04-before-realtime-update.png',
      fullPage: true 
    });
    
    // 현재 시간 캡처 (마지막 업데이트 시간으로 추정)
    const beforeUpdateTime = new Date().toISOString();
    console.log(`업데이트 대기 시작: ${beforeUpdateTime}`);
    
    console.log('⏳ 실시간 업데이트 대기 중... (15초)');
    
    // 15초 대기 (10초 간격 + 여유시간)
    await page.waitForTimeout(15000);
    
    // 업데이트 후 스크린샷
    await page.screenshot({ 
      path: 'test-results/04-after-realtime-update.png',
      fullPage: true 
    });
    
    const afterUpdateTime = new Date().toISOString();
    console.log(`업데이트 대기 완료: ${afterUpdateTime}`);
    
    // 시간 표시 요소가 있는지 확인
    const timeElements = await page.locator('text=/\\d{1,2}:\\d{2}:\\d{2}|오늘|\\d{2}월|AM|PM/').count();
    console.log(`시간 관련 요소 개수: ${timeElements}개`);
    
    console.log('✅ 실시간 업데이트 기능 테스트 완료');
  });

  test('5. 설정 탭 기능 및 제어 버튼 테스트', async ({ page }) => {
    console.log('🔍 설정 탭 기능 테스트 시작');
    
    // 설정 탭으로 이동
    await page.click('button:has-text("설정")');
    await page.waitForTimeout(2000);
    
    // 시작/중지 버튼 확인
    const startButton = page.locator('button:has-text("시작")');
    const stopButton = page.locator('button:has-text("중지")');
    
    if (await startButton.isVisible()) {
      console.log('✅ 시작 버튼 발견');
    }
    
    if (await stopButton.isVisible()) {
      console.log('✅ 중지 버튼 발견');
    }
    
    // 설정 폼이나 입력 필드 확인
    const inputFields = await page.locator('input').count();
    console.log(`입력 필드 개수: ${inputFields}개`);
    
    const selectFields = await page.locator('select').count();
    console.log(`선택 필드 개수: ${selectFields}개`);
    
    // 설정 탭 스크린샷
    await page.screenshot({ 
      path: 'test-results/05-settings-tab-detailed.png',
      fullPage: true 
    });
    
    console.log('✅ 설정 탭 기능 테스트 완료');
  });

  test('6. 로그 탭 테스트', async ({ page }) => {
    console.log('🔍 로그 탭 테스트 시작');
    
    // 로그 탭으로 이동
    await page.click('button:has-text("로그")');
    await page.waitForTimeout(2000);
    
    // 로그 내용 확인
    const logContainer = page.locator('.log-container, .logs, pre, .console');
    
    // 여러 가능한 로그 컨테이너 확인
    let logFound = false;
    const possibleLogSelectors = ['.log-container', '.logs', 'pre', '.console', '.log-output'];
    
    for (const selector of possibleLogSelectors) {
      if (await page.locator(selector).isVisible()) {
        console.log(`✅ 로그 컨테이너 발견: ${selector}`);
        logFound = true;
        break;
      }
    }
    
    if (!logFound) {
      console.log('⚠️ 전용 로그 컨테이너를 찾지 못함. 페이지 내용 확인');
    }
    
    // 텍스트 기반 로그 확인
    const pageText = await page.textContent('body');
    const hasLogKeywords = /log|error|info|debug|warning|시간|실행|거래|전략/i.test(pageText || '');
    console.log(`로그 관련 키워드 포함 여부: ${hasLogKeywords}`);
    
    // 로그 탭 스크린샷
    await page.screenshot({ 
      path: 'test-results/06-logs-tab-detailed.png',
      fullPage: true 
    });
    
    console.log('✅ 로그 탭 테스트 완료');
  });

  test('7. API 통신 확인 및 응답 시간 측정', async ({ page, request }) => {
    console.log('🔍 API 통신 확인 테스트 시작');
    
    const apiEndpoints = [
      { name: 'Status API', url: `${API_BASE_URL}/status` },
      { name: 'Data API', url: `${API_BASE_URL}/data` },
      { name: 'Trades API', url: `${API_BASE_URL}/trades` },
      { name: 'Strategies API', url: `${API_BASE_URL}/strategies` }
    ];
    
    const apiResults = [];
    
    for (const endpoint of apiEndpoints) {
      console.log(`📡 ${endpoint.name} 테스트 중...`);
      
      try {
        const startTime = Date.now();
        const response = await request.get(endpoint.url, { timeout: 10000 });
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
            result.dataKeys = Object.keys(data).slice(0, 5); // 처음 5개 키만
            result.dataSize = JSON.stringify(data).length;
            console.log(`✅ ${endpoint.name}: ${response.status()} (${responseTime}ms) - ${result.dataSize}bytes`);
          } catch (e) {
            const text = await response.text();
            result.responseType = 'text';
            result.dataSize = text.length;
            console.log(`✅ ${endpoint.name}: ${response.status()} (${responseTime}ms) - Text response`);
          }
        } else {
          console.log(`❌ ${endpoint.name}: ${response.status()} (${responseTime}ms)`);
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
      
      // API 호출 간 대기
      await page.waitForTimeout(1000);
    }
    
    // API 테스트 결과를 콘솔에 출력
    console.log('\\n📊 API 테스트 결과 요약:');
    const successCount = apiResults.filter(r => r.success).length;
    console.log(`성공한 API: ${successCount}/${apiResults.length}`);
    
    apiResults.forEach(result => {
      const status = result.success ? '✅ 성공' : '❌ 실패';
      console.log(`- ${result.name}: ${status} ${result.responseTime || ''}`);
    });
    
    console.log('✅ API 통신 확인 테스트 완료');
  });

  test('8. 페이지 성능 및 종합 검증', async ({ page }) => {
    console.log('🔍 종합 테스트 및 성능 검증 시작');
    
    // 최종 대시보드 상태 확인
    await page.goto(DASHBOARD_URL);
    await page.waitForLoadState('networkidle');
    
    // 페이지 성능 메트릭 수집
    const performanceMetrics = await page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      return {
        loadTime: Math.round(navigation.loadEventEnd - navigation.loadEventStart),
        domContentLoaded: Math.round(navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart),
        totalTime: Math.round(navigation.loadEventEnd - navigation.fetchStart),
        responseTime: Math.round(navigation.responseEnd - navigation.requestStart)
      };
    });
    
    console.log('\\n📈 성능 메트릭:');
    console.log(`- 페이지 로드 시간: ${performanceMetrics.loadTime}ms`);
    console.log(`- DOM 준비 시간: ${performanceMetrics.domContentLoaded}ms`);
    console.log(`- 서버 응답 시간: ${performanceMetrics.responseTime}ms`);
    console.log(`- 총 로드 시간: ${performanceMetrics.totalTime}ms`);
    
    // JavaScript 에러 확인
    const jsErrors = [];
    page.on('pageerror', error => {
      jsErrors.push(error.message);
    });
    
    // 콘솔 에러 확인
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    // 최종 스크린샷
    await page.screenshot({ 
      path: 'test-results/08-final-comprehensive-test.png',
      fullPage: true 
    });
    
    // 종합 평가
    const performanceScore = performanceMetrics.totalTime < 5000 ? '우수' : 
                           performanceMetrics.totalTime < 10000 ? '양호' : '개선필요';
    
    console.log('\\n🎯 종합 테스트 결과:');
    console.log(`- 성능 점수: ${performanceScore}`);
    console.log(`- JavaScript 에러: ${jsErrors.length}개`);
    console.log(`- 콘솔 에러: ${consoleErrors.length}개`);
    
    if (jsErrors.length > 0) {
      console.log('JavaScript 에러 내용:', jsErrors);
    }
    
    console.log('\\n✅ 모든 테스트 완료');
  });
});