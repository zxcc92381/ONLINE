import os
import time
from playwright.sync_api import sync_playwright

USERNAME = os.environ.get("LEME_USERNAME", "YOUR_USERNAME")
PASSWORD = os.environ.get("LEME_PASSWORD", "YOUR_PASSWORD")

LOGIN_URL = "https://lemehost.com/site/login"
SERVER_URL = "https://lemehost.com/server/10228912/free-plan"
STATE_FILE = "state.json"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Check if saved state.json exists
        if os.path.exists(STATE_FILE):
            print("🔑 Found state.json file. Using stored session...")
            context = browser.new_context(storage_state=STATE_FILE)
            page = context.new_page()

            print(f"1. Navigating directly to server panel: {SERVER_URL}")
            page.goto(SERVER_URL, timeout=60000)
            page.wait_for_timeout(3000)

            # Check if redirected to login page due to expired session
            if "login" in page.url.lower():
                print("⚠️ Stored session expired. Removing state.json and re-logging in...")
                os.remove(STATE_FILE)
                browser.close()
                return main()

        else:
            print("🌐 No state.json found. Opening login page...")
            context = browser.new_context()
            page = context.new_page()

            page.goto(LOGIN_URL, timeout=60000)
            print("1. Filling login credentials...")
            page.fill('input[name*="login"], input[name*="username"], input[type="text"], input[type="email"]', USERNAME)
            page.fill('input[name*="password"], input[type="password"]', PASSWORD)

            print("2. Clicking login button...")
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_timeout(5000)

            print(f"3. Navigating to server panel: {SERVER_URL}")
            page.goto(SERVER_URL, timeout=60000)
            page.wait_for_timeout(3000)

        # Look for the Extend time button and click
        button_selector = 'button:has-text("Extend time")'

        if page.is_visible(button_selector):
            print("4. 'Extend time' button found! Clicking button...")
            page.click(button_selector)
            page.wait_for_timeout(5000)
            print("✅ Success: Server time extended successfully.")
        else:
            print("⚠️ 'Extend time' button not found (it might not be ready yet).")

        # Update saved state
        try:
            context.storage_state(path=STATE_FILE)
        except Exception:
            pass

        print("Execution finished.")
        browser.close()

if __name__ == "__main__":
    main()
