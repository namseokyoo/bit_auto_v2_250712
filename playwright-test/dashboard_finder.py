import asyncio
from playwright.async_api import async_playwright
import os
from datetime import datetime

async def find_and_check_dashboard():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = await context.new_page()
        
        # Common dashboard ports to try
        ports_to_try = [5000, 8000, 8080, 3000, 5001, 8001]
        
        successful_url = None
        
        for port in ports_to_try:
            url = f"http://158.180.82.112:{port}/"
            try:
                print(f"Trying to connect to: {url}")
                await page.goto(url, timeout=10000)
                await page.wait_for_load_state('networkidle', timeout=5000)
                
                # Check if page loaded successfully
                title = await page.title()
                if title and title != "":
                    print(f"✓ Successfully connected to {url}")
                    print(f"Page title: {title}")
                    successful_url = url
                    break
                    
            except Exception as e:
                print(f"✗ Failed to connect to {url}: {str(e)}")
                continue
        
        if successful_url:
            try:
                print(f"\nNavigating dashboard at {successful_url}...")
                
                # Wait for page to fully load
                await asyncio.sleep(3)
                
                print("Looking for Control Panel tab...")
                # Look for the Control Panel tab (제어판)
                control_panel_selectors = [
                    'text=제어판',
                    'text=Control Panel',
                    '[data-testid="control-panel"]',
                    'a:has-text("제어판")',
                    'button:has-text("제어판")',
                    '.nav-link:has-text("제어판")',
                    '[href*="control"]',
                    '[role="tab"]:has-text("제어판")',
                    'li:has-text("제어판")',
                    '.tab:has-text("제어판")'
                ]
                
                control_panel_clicked = False
                for selector in control_panel_selectors:
                    try:
                        element = page.locator(selector)
                        if await element.count() > 0:
                            first_element = element.first
                            if await first_element.is_visible():
                                print(f"Found Control Panel tab with selector: {selector}")
                                await first_element.click()
                                control_panel_clicked = True
                                break
                    except Exception as e:
                        continue
                
                if not control_panel_clicked:
                    print("Direct selectors failed, searching for navigation elements...")
                    # Get all clickable navigation elements
                    clickable_selectors = [
                        'a', 'button', '.nav-link', '[role="tab"]', 'li', '.tab',
                        '.nav-item', '.menu-item', '.navbar-nav a'
                    ]
                    
                    for selector in clickable_selectors:
                        try:
                            elements = await page.locator(selector).all()
                            for element in elements:
                                try:
                                    text = await element.text_content()
                                    if text and ('제어' in text or 'control' in text.lower() or 'panel' in text.lower()):
                                        print(f"Found potential control panel element: {text}")
                                        if await element.is_visible():
                                            await element.click()
                                            control_panel_clicked = True
                                            break
                                except:
                                    continue
                            if control_panel_clicked:
                                break
                        except:
                            continue
                
                if control_panel_clicked:
                    print("Control Panel tab clicked, waiting for content to load...")
                    await asyncio.sleep(3)
                    await page.wait_for_load_state('networkidle')
                else:
                    print("Could not find Control Panel tab, taking screenshot of available content...")
                    # Get available tabs/navigation
                    try:
                        nav_text = await page.locator('nav, .nav, .navbar, .menu').text_content()
                        if nav_text:
                            print(f"Available navigation: {nav_text}")
                    except:
                        pass
                
                # Look for Process Monitor section or any process information
                print("Looking for Process Monitor section...")
                process_monitor_selectors = [
                    'text=프로세스 모니터',
                    'text=Process Monitor',
                    '[data-testid="process-monitor"]',
                    ':has-text("프로세스 모니터")',
                    ':has-text("Process Monitor")',
                    '.process-monitor',
                    '#process-monitor',
                    ':has-text("Quantum Trading")',
                    ':has-text("Multi-Coin")',
                    ':has-text("AI Feedback")'
                ]
                
                process_monitor_found = False
                for selector in process_monitor_selectors:
                    try:
                        element = page.locator(selector)
                        if await element.count() > 0:
                            print(f"Found Process Monitor content with selector: {selector}")
                            process_monitor_found = True
                            break
                    except Exception as e:
                        continue
                
                # Take screenshot
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = f"/Users/namseokyoo/project/bit_auto_v2_250712/dashboard_screenshot_{timestamp}.png"
                
                print(f"Taking screenshot: {screenshot_path}")
                await page.screenshot(path=screenshot_path, full_page=True)
                
                print(f"Screenshot saved: {screenshot_path}")
                
                # Analyze page content
                page_content = await page.content()
                
                # Look for specific process names in the content
                processes_to_check = [
                    'Quantum Trading',
                    'Multi-Coin Trading', 
                    'AI Feedback',
                    'quantum_trading',
                    'multi_coin',
                    'ai_feedback',
                    'quantum.py',
                    'dashboard.py'
                ]
                
                print("\nAnalyzing page content for process information...")
                found_processes = []
                for process_name in processes_to_check:
                    if process_name.lower() in page_content.lower():
                        print(f"✓ Found reference to: {process_name}")
                        found_processes.append(process_name)
                    else:
                        print(f"✗ No reference found for: {process_name}")
                
                # Check for status indicators
                status_keywords = ['running', 'stopped', '실행', '중지', 'active', 'inactive', 'status', '상태']
                print("\nStatus indicators found:")
                status_found = []
                for keyword in status_keywords:
                    if keyword.lower() in page_content.lower():
                        print(f"- Status keyword found: {keyword}")
                        status_found.append(keyword)
                
                # Get page title and URL for reference
                title = await page.title()
                current_url = page.url
                print(f"\nDashboard details:")
                print(f"- URL: {current_url}")
                print(f"- Title: {title}")
                print(f"- Found processes: {', '.join(found_processes) if found_processes else 'None'}")
                print(f"- Status indicators: {', '.join(status_found) if status_found else 'None'}")
                
                return screenshot_path
                
            except Exception as e:
                print(f"Error during dashboard navigation: {str(e)}")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                error_screenshot_path = f"/Users/namseokyoo/project/bit_auto_v2_250712/dashboard_error_{timestamp}.png"
                await page.screenshot(path=error_screenshot_path, full_page=True)
                return error_screenshot_path
        else:
            print("Could not connect to any dashboard port. The dashboard service might not be running.")
            return None
            
        await browser.close()

if __name__ == "__main__":
    screenshot_path = asyncio.run(find_and_check_dashboard())
    if screenshot_path:
        print(f"\nFinal screenshot: {screenshot_path}")
    else:
        print("\nNo dashboard found - service may be down.")