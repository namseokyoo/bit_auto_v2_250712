import asyncio
from playwright.async_api import async_playwright
import os
from datetime import datetime

async def check_control_panel():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = await context.new_page()
        
        try:
            print("Navigating to dashboard...")
            await page.goto("http://158.180.82.112:5000/")
            
            # Wait for page to load
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(3)
            
            print("Looking for Control Panel tab...")
            # Look for the Control Panel tab (제어판)
            control_panel_selectors = [
                'text=제어판',
                '[data-testid="control-panel"]',
                'a:has-text("제어판")',
                'button:has-text("제어판")',
                '.nav-link:has-text("제어판")',
                '[href*="control"]',
                '[role="tab"]:has-text("제어판")'
            ]
            
            control_panel_clicked = False
            for selector in control_panel_selectors:
                try:
                    element = page.locator(selector)
                    if await element.count() > 0 and await element.first.is_visible():
                        print(f"Found Control Panel tab with selector: {selector}")
                        await element.first.click()
                        control_panel_clicked = True
                        break
                except Exception as e:
                    continue
            
            if not control_panel_clicked:
                print("Could not find Control Panel tab, checking available tabs...")
                # Get all visible navigation elements
                nav_elements = await page.locator('a, button, .nav-link, [role="tab"]').all()
                for element in nav_elements:
                    try:
                        text = await element.text_content()
                        if text and ('제어' in text or 'control' in text.lower() or 'panel' in text.lower()):
                            print(f"Found potential control panel tab: {text}")
                            await element.click()
                            control_panel_clicked = True
                            break
                    except:
                        continue
            
            if control_panel_clicked:
                print("Control Panel tab clicked, waiting for content to load...")
                await asyncio.sleep(3)
                await page.wait_for_load_state('networkidle')
            else:
                print("Could not find Control Panel tab, taking screenshot of current page...")
            
            # Look for Process Monitor section
            print("Looking for Process Monitor section...")
            process_monitor_selectors = [
                'text=프로세스 모니터',
                '[data-testid="process-monitor"]',
                ':has-text("프로세스 모니터")',
                ':has-text("Process Monitor")',
                '.process-monitor',
                '#process-monitor'
            ]
            
            process_monitor_found = False
            for selector in process_monitor_selectors:
                try:
                    element = page.locator(selector)
                    if await element.count() > 0:
                        print(f"Found Process Monitor section with selector: {selector}")
                        process_monitor_found = True
                        break
                except Exception as e:
                    continue
            
            if not process_monitor_found:
                print("Process Monitor section not found, looking for process-related content...")
                # Look for any process-related content
                process_keywords = ['프로세스', 'process', '모니터', 'monitor', 'Quantum Trading', 'Multi-Coin', 'AI Feedback']
                for keyword in process_keywords:
                    try:
                        elements = page.locator(f':has-text("{keyword}")')
                        if await elements.count() > 0:
                            print(f"Found process-related content with keyword: {keyword}")
                            process_monitor_found = True
                            break
                    except:
                        continue
            
            # Take screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"/Users/namseokyoo/project/bit_auto_v2_250712/control_panel_process_monitor_{timestamp}.png"
            
            print(f"Taking screenshot: {screenshot_path}")
            await page.screenshot(path=screenshot_path, full_page=True)
            
            print(f"Screenshot saved: {screenshot_path}")
            
            # Get page content for analysis
            page_content = await page.content()
            
            # Look for specific process names in the content
            processes_to_check = [
                'Quantum Trading',
                'Multi-Coin Trading', 
                'AI Feedback',
                'quantum_trading',
                'multi_coin',
                'ai_feedback'
            ]
            
            print("\nChecking for process status in page content...")
            for process_name in processes_to_check:
                if process_name.lower() in page_content.lower():
                    print(f"✓ Found reference to: {process_name}")
                else:
                    print(f"✗ No reference found for: {process_name}")
            
            # Check for status indicators
            status_keywords = ['running', 'stopped', '실행', '중지', 'active', 'inactive']
            print("\nStatus indicators found:")
            for keyword in status_keywords:
                if keyword.lower() in page_content.lower():
                    print(f"- Status keyword found: {keyword}")
            
            return screenshot_path
            
        except Exception as e:
            print(f"Error during navigation: {str(e)}")
            # Take screenshot anyway for debugging
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_screenshot_path = f"/Users/namseokyoo/project/bit_auto_v2_250712/error_screenshot_{timestamp}.png"
            await page.screenshot(path=error_screenshot_path, full_page=True)
            print(f"Error screenshot saved: {error_screenshot_path}")
            return error_screenshot_path
            
        finally:
            await browser.close()

if __name__ == "__main__":
    screenshot_path = asyncio.run(check_control_panel())
    print(f"\nScreenshot captured: {screenshot_path}")