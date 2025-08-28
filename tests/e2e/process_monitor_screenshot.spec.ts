import { test, expect } from '@playwright/test';

test('Control Panel - Process Monitor Screenshot', async ({ page }) => {
  // 대시보드 페이지에 접속
  await page.goto('http://158.180.82.112:8080/');
  
  // 페이지 로딩 대기
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(5000);
  
  // 제어판 탭이 이미 활성화되어 있는지 확인하고, 아니라면 클릭
  const controlTabButton = page.locator('text=제어판');
  if (await controlTabButton.isVisible()) {
    await controlTabButton.click();
    await page.waitForTimeout(2000);
  }
  
  // 프로세스 모니터 헤더가 있는지 확인
  await page.waitForSelector('text=프로세스 모니터', { timeout: 10000 });
  
  // 전체 페이지 스크린샷 (제어판 탭 상태)
  await page.screenshot({
    path: '/Users/namseokyoo/project/bit_auto_v2_250712/control_panel_full_page.png',
    fullPage: true
  });
  
  // 프로세스 모니터 섹션을 포함한 뷰포트 스크린샷
  await page.screenshot({
    path: '/Users/namseokyoo/project/bit_auto_v2_250712/process_monitor_viewport.png'
  });
  
  // 페이지를 아래로 스크롤해서 프로세스 모니터 섹션이 잘 보이도록 조정
  await page.locator('text=프로세스 모니터').scrollIntoViewIfNeeded();
  await page.waitForTimeout(1000);
  
  // 프로세스 모니터 섹션 집중 스크린샷
  await page.screenshot({
    path: '/Users/namseokyoo/project/bit_auto_v2_250712/process_monitor_focused.png'
  });
  
  // 프로세스 모니터 섹션만 스크린샷 (요소 기반)
  const processMonitorSection = page.locator('text=프로세스 모니터').locator('..');
  if (await processMonitorSection.isVisible()) {
    await processMonitorSection.screenshot({
      path: '/Users/namseokyoo/project/bit_auto_v2_250712/process_monitor_section_only.png'
    });
  }
  
  console.log('스크린샷 완료: 제어판 - 프로세스 모니터');
});