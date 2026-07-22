import os
import time
from playwright.sync_api import sync_playwright

# لیست اکانت‌ها و سرورها
ACCOUNTS = [
    {
        "name": "Server 1",
        "username": os.environ.get("LEME_USERNAME", "YOUR_USERNAME"),
        "password": os.environ.get("LEME_PASSWORD", "YOUR_PASSWORD"),
        "server_url": "https://lemehost.com/server/10228912/free-plan", # آدرس سرور اول
        "state_file": "state.json"
    },
    {
        "name": "Server 2",
        "username": os.environ.get("LEME_USERNAME_2", "YOUR_USERNAME_2"),
        "password": os.environ.get("LEME_PASSWORD_2", "YOUR_PASSWORD_2"),
        "server_url": "https://lemehost.com/server/10231954/free-plan", # آدرس سرور دوم
        "state_file": "state2.json"
    }
    # می‌توانید اکانت سوم یا بیشتر را هم به همین شکل اضافه کنید
]

LOGIN_URL = "https://lemehost.com/site/login"

def process_account(browser, acc):
    print(f"\n==========================================")
    print(f"🚀 Processing: {acc['name']}")
    print(f"==========================================")
    
    state_file = acc["state_file"]
    server_url = acc["server_url"]
    username = acc["username"]
    password = acc["password"]

    # بررسی وجود فایل کوکی ذخیره‌شده
    if os.path.exists(state_file):
        print(f"🔑 Found {state_file}. Using stored session...")
        context = browser.new_context(storage_state=state_file)
        page = context.new_page()

        print(f"1. Navigating directly to server panel: {server_url}")
        page.goto(server_url, timeout=60000)
        page.wait_for_timeout(3000)

        # اگر کوکی منقضی شده باشد
        if "login" in page.url.lower():
            print(f"⚠️ Session expired for {acc['name']}. Removing {state_file} and re-logging in...")
            os.remove(state_file)
            context.close()
            return process_account(browser, acc)

    else:
        print(f"🌐 No {state_file} found. Opening login page...")
        context = browser.new_context()
        page = context.new_page()

        page.goto(LOGIN_URL, timeout=60000)
        print("1. Filling login credentials...")
        page.fill('input[name*="login"], input[name*="username"], input[type="text"], input[type="email"]', username)
        page.fill('input[name*="password"], input[type="password"]', password)

        print("2. Clicking login button...")
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_timeout(5000)

        print(f"3. Navigating to server panel: {server_url}")
        page.goto(server_url, timeout=60000)
        page.wait_for_timeout(3000)

    # پیدا کردن دکمه Extend time و کلیک روی آن
    button_selector = 'button:has-text("Extend time")'

    if page.is_visible(button_selector):
        print("4. 'Extend time' button found! Clicking button...")
        page.click(button_selector)
        page.wait_for_timeout(5000)
        print(f"✅ Success: Server time extended successfully for {acc['name']}.")
    else:
        print(f"⚠️ 'Extend time' button not found for {acc['name']}.")

    # ذخیره و به‌روزرسانی کوکی اکانت
    try:
        context.storage_state(path=state_file)
    except Exception:
        pass

    context.close()

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for acc in ACCOUNTS:
            try:
                process_account(browser, acc)
            except Exception as e:
                print(f"❌ Error processing {acc['name']}: {e}")

        print("\n==========================================")
        print("All accounts processed. Execution finished.")
        print("==========================================")
        browser.close()

if __name__ == "__main__":
    main()
