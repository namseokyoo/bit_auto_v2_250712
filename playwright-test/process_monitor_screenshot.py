#!/usr/bin/env python3
"""
Process Monitor Screenshot Script
Captures screenshot of the Process Monitor section in the Control Panel tab
"""

import asyncio
from playwright.async_api import async_playwright
import sys
import os

async def take_process_monitor_screenshot():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='ko-KR'
        )
        page = await context.new_page()
        
        try:
            print("📱 대시보드 접속 중...")
            # Navigate to dashboard
            await page.goto('http://localhost:8080', wait_until='networkidle')
            
            # Wait for page to load
            await page.wait_for_timeout(3000)
            
            print("🎯 제어판 탭 클릭...")
            # Click on Control Panel (제어판) tab
            control_tab_selector = 'a[href="#control"], button[onclick*="control"], .nav-link:has-text("제어판")'
            
            # Try multiple selectors to find the control tab
            try:
                await page.click('text=제어판')
            except:
                try:
                    await page.click('[data-tab="control"]')
                except:
                    try:
                        await page.click('#control-tab')
                    except:
                        # If direct text match fails, try to find any element containing "제어" or "control"
                        elements = await page.query_selector_all('a, button, .nav-link')
                        for element in elements:
                            text = await element.inner_text()
                            if '제어' in text or 'control' in text.lower():
                                await element.click()
                                break
            
            # Wait for control panel content to load
            await page.wait_for_timeout(2000)
            
            print("📊 프로세스 모니터 섹션 확인 중...")
            # Look for Process Monitor section
            process_monitor_selectors = [
                '.process-monitor',
                '#process-monitor', 
                '[data-section="process-monitor"]',
                'text=프로세스 모니터',
                '.card:has-text("프로세스")',
                '.section:has-text("모니터")'
            ]
            
            process_section = None
            for selector in process_monitor_selectors:
                try:
                    process_section = await page.wait_for_selector(selector, timeout=5000)
                    if process_section:
                        break
                except:
                    continue
            
            if process_section:
                print("📸 프로세스 모니터 섹션 스크린샷 촬영...")
                # Take screenshot of the process monitor section
                await process_section.screenshot(path='process_monitor_focused.png')
                print("✅ 프로세스 모니터 섹션 스크린샷 저장: process_monitor_focused.png")
                
                # Also take a full page screenshot for context
                await page.screenshot(path='process_monitor_full.png', full_page=True)
                print("✅ 전체 페이지 스크린샷 저장: process_monitor_full.png")
            else:
                print("⚠️ 프로세스 모니터 섹션을 찾을 수 없음. 전체 제어판 스크린샷 촬영...")
                # Take full page screenshot if we can't find the specific section
                await page.screenshot(path='control_panel_full.png', full_page=True)
                print("✅ 제어판 전체 스크린샷 저장: control_panel_full.png")
            
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            # Take error screenshot
            await page.screenshot(path='error_screenshot.png')
            print("📸 오류 스크린샷 저장: error_screenshot.png")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    print("🚀 프로세스 모니터 스크린샷 도구 시작...")
    asyncio.run(take_process_monitor_screenshot())
    print("🎯 작업 완료!")