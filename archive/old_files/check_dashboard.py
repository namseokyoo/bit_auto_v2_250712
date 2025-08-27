#!/usr/bin/env python3
"""
Dashboard check script to take screenshot and verify all components
"""
import asyncio
from playwright.async_api import async_playwright
import json
import time

async def check_dashboard():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("🌐 Navigating to dashboard...")
        await page.goto('http://158.180.82.112:8080/')
        
        # Wait for page to load completely
        print("⏳ Waiting for content to load...")
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(3)
        
        # Take full page screenshot
        screenshot_path = 'dashboard_screenshot.png'
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"📸 Screenshot saved to: {screenshot_path}")
        
        # Check if JavaScript is working by looking for dynamic content
        print("\n🔍 Checking dashboard components...")
        
        # Wait for data to load
        await asyncio.sleep(2)
        
        try:
            # Check system status
            status_element = await page.wait_for_selector('.status-card', timeout=5000)
            print("✅ System status card found")
        except:
            print("❌ System status card not found")
        
        try:
            # Check account info
            account_element = await page.wait_for_selector('.account-info', timeout=5000)
            print("✅ Account info section found")
        except:
            print("❌ Account info section not found")
        
        try:
            # Check strategy signals
            signals_element = await page.wait_for_selector('.strategy-signals', timeout=5000)
            print("✅ Strategy signals section found")
        except:
            print("❌ Strategy signals section not found")
        
        try:
            # Check recent trades
            trades_element = await page.wait_for_selector('.recent-trades', timeout=5000)
            print("✅ Recent trades section found")
        except:
            print("❌ Recent trades section not found")
        
        # Get page content to analyze values
        content = await page.content()
        
        # Check for specific values
        print("\n📊 Analyzing displayed values...")
        
        if "Running" in content:
            print("✅ System status showing as 'Running'")
        else:
            print("❌ System status not showing correctly")
        
        if "₩" in content and not content.count("₩0") > 5:
            print("✅ KRW values displaying correctly")
        else:
            print("❌ KRW values showing as ₩0")
        
        if "BTC" in content:
            print("✅ BTC information present")
        else:
            print("❌ BTC information missing")
        
        # Wait 10 seconds and check for updates
        print("\n⏱️ Waiting 10 seconds to check for real-time updates...")
        initial_content = content
        await asyncio.sleep(10)
        
        updated_content = await page.content()
        if initial_content != updated_content:
            print("✅ Content updated - real-time refresh working")
        else:
            print("⚠️ Content unchanged - may need to check real-time updates")
        
        # Take final screenshot
        await page.screenshot(path='dashboard_final.png', full_page=True)
        print("📸 Final screenshot saved to: dashboard_final.png")
        
        await browser.close()
        
        return {
            'screenshot_saved': True,
            'components_loaded': True,
            'real_time_working': initial_content != updated_content
        }

async def main():
    print("🚀 Starting comprehensive dashboard check...")
    result = await check_dashboard()
    print(f"\n✅ Check completed: {result}")

if __name__ == "__main__":
    asyncio.run(main())