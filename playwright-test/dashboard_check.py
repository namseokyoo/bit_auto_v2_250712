#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright
import os

async def check_dashboard():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        try:
            print("Navigating to dashboard...")
            # Try different ports for the dashboard
            dashboard_urls = [
                'http://158.180.82.112:8080/',  # Default dashboard port
                'http://158.180.82.112:5000/',  # Web app port
                'http://158.180.82.112:8081/',  # Alternative port
            ]
            
            dashboard_url = None
            for url in dashboard_urls:
                try:
                    print(f"Trying to connect to {url}...")
                    await page.goto(url, timeout=10000)
                    dashboard_url = url
                    print(f"Successfully connected to {url}")
                    break
                except Exception as e:
                    print(f"Failed to connect to {url}: {e}")
                    continue
            
            if not dashboard_url:
                raise Exception("Could not connect to any dashboard port")
            
            # Wait for page to load
            await page.wait_for_load_state('networkidle', timeout=30000)
            
            # Take a full page screenshot first
            await page.screenshot(path='dashboard_full.png', full_page=True)
            print("Full dashboard screenshot saved as dashboard_full.png")
            
            # Try to find and focus on process monitor section
            process_monitor_selectors = [
                '[class*="process"]',
                '[id*="process"]', 
                'h2:has-text("Process")',
                'h3:has-text("Process")',
                '.monitor',
                '#monitor',
                '.status',
                '#status'
            ]
            
            process_section = None
            for selector in process_monitor_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        print(f"Found process monitor section with selector: {selector}")
                        process_section = element
                        break
                except:
                    continue
            
            if process_section:
                # Scroll to the process monitor section
                await process_section.scroll_into_view_if_needed()
                await page.wait_for_timeout(2000)  # Wait for scroll
                
                # Take screenshot of the process monitor section
                await process_section.screenshot(path='process_monitor.png')
                print("Process monitor section screenshot saved as process_monitor.png")
            else:
                print("Could not locate specific process monitor section, using full page screenshot")
            
            # Get page title and basic info
            title = await page.title()
            print(f"Page title: {title}")
            
            # Check if page loaded successfully
            content = await page.content()
            if 'error' in content.lower() or 'not found' in content.lower():
                print("Warning: Page may contain error messages")
            else:
                print("Dashboard appears to be loading normally")
                
        except Exception as e:
            print(f"Error accessing dashboard: {e}")
            # Still try to take a screenshot of whatever loaded
            try:
                await page.screenshot(path='dashboard_error.png')
                print("Error screenshot saved as dashboard_error.png")
            except:
                pass
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(check_dashboard())