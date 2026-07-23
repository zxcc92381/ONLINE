import os
import time
from playwright.sync_api import sync_playwright
import ddddocr

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

# لود کردن مدل هوش مصنوعی کپچا (show_ad=False برای عدم نمایش تبلیغ کتابخانه)
ocr = ddddocr.DdddOcr(show_ad=False)

def process_account(browser, acc):
    print(f"\n==========================================")
    print(f"🚀 Processing: {acc['name']}")
    print(f"==========================================")
    
    state_file = acc["state_file"]
    server_url = acc["server_url"]
    username = acc["username"]
    password = acc["password"]

    if os.path.exists(state_file):
        print(f"🔑 Found {state_file}. Using stored session...")
        context = browser.new_context(storage_state=state_file)
        page = context.new_page()

        print(f"1. Navigating directly to server panel: {server_url}")
        page.goto(server_url, timeout=60000)
        page.wait_for_timeout(3000)

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

    # پیدا کردن المان‌های کپچا و دکمه
    captcha_img_selector = '#extendfreeplanform-captcha-image'
    captcha_input_selector = '#extendfreeplanform-captcha'
    button_selector = 'button:has-text("Extend time")'

    if page.is_visible(button_selector):
        print("4. 'Extend time' button found!")
        
        # 🤖 بررسی وجود کپچا در صفحه
        if page.is_visible(captcha_img_selector):
            print("⚠️ CAPTCHA detected on extend form! Attempting to solve...")
            try:
                # گرفتن اسکرین‌شات فقط از خود عکس کپچا
                captcha_bytes = page.locator(captcha_img_selector).screenshot()
                
                # ارسال عکس به هوش مصنوعی برای خواندن متن
                captcha_text = ocr.classification(captcha_bytes)
                print(f"🧩 AI solved CAPTCHA as: '{captcha_text}'")
                
                # پر کردن فیلد کپچا
                page.fill(captcha_input_selector, captcha_text)
                page.wait_for_timeout(1000)
            except Exception as e:
                print(f"❌ Failed to solve captcha: {e}")

        # کلیک روی دکمه تمدید
        print("5. Clicking Extend button...")
        page.click(button_selector)
        page.wait_for_timeout(5000)
        print(f"✅ Success: Server time extended (or attempted) for {acc['name']}.")
    else:
        print(f"⚠️ 'Extend time' button not found for {acc['name']}.")

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
