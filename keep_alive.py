import os
import time
import urllib.parse
import urllib.request
import ddddocr
from playwright.sync_api import sync_playwright

# تنظیمات ربات تلگرام (می‌توانید توکن و چت‌آیدی را در os.environ یا مستقیم اینجا بگذارید)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

# لیست اکانت‌ها و سرورها
ACCOUNTS = [
    {
        "name": "Server 1",
        "username": os.environ.get("LEME_USERNAME", "YOUR_USERNAME"),
        "password": os.environ.get("LEME_PASSWORD", "YOUR_PASSWORD"),
        "server_url": "https://lemehost.com/server/10228912/free-plan",  # آدرس سرور اول
        "state_file": "state.json",
    },
    {
        "name": "Server 2",
        "username": os.environ.get("LEME_USERNAME_2", "YOUR_USERNAME_2"),
        "password": os.environ.get("LEME_PASSWORD_2", "YOUR_PASSWORD_2"),
        "server_url": "https://lemehost.com/server/10231954/free-plan",  # آدرس سرور دوم
        "state_file": "state2.json",
    },
]

LOGIN_URL = "https://lemehost.com/site/login"

# لود کردن مدل هوش مصنوعی کپچا
ocr = ddddocr.DdddOcr(show_ad=False)


def send_telegram_alert(message):
    """ارسال پیام هشدار به تلگرام"""
    if (
        not TELEGRAM_BOT_TOKEN
        or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN"
    ):
        print("⚠️ Telegram BOT_TOKEN is not set. Skipping alert.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode(
        {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    ).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload)
        with urllib.request.urlopen(req) as response:
            print("📩 Telegram notification sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send Telegram message: {e}")


def check_and_start_server(page):
    """چک کردن وضعیت آنلاین بودن و کلیک روی Start در صورت آنلاین نبودن"""
    try:
        status_locator = page.locator('[data-put="status"]')
        if status_locator.is_visible():
            status_text = status_locator.text_content().strip().lower()
            print(f"📊 Current Server Status: '{status_text}'")

            if status_text != "online":
                print("🔴 Server is NOT online. Attempting to click Start...")
                start_btn = page.locator('button[data-state="start"]')
                if start_btn.is_visible():
                    # استفاده از force=True برای کلیک حتی در صورت disabled بودن ظاهر دکمه
                    start_btn.click(force=True)
                    print("▶️ Clicked 'Start' button successfully.")
                    page.wait_for_timeout(3000)
                else:
                    print("⚠️ Start button not found.")
            else:
                print("🟢 Server is already online.")
        else:
            print("⚠️ Server status element not found.")
    except Exception as e:
        print(f"❌ Error checking server status: {e}")


def is_countdown_zero(page):
    """بررسی اینکه آیا تایمر معکوس صفر است یا خیر"""
    try:
        countdown_locator = page.locator("#countdown-free-plan")
        if not countdown_locator.is_visible():
            return True

        text = countdown_locator.text_content().strip()
        print(f"⏱️ Current Countdown Text: '{text}'")

        # حذف : و فضاها برای بررسی صفر بودن عدد
        clean_text = text.replace(":", "").strip()
        if clean_text.isdigit() and int(clean_text) == 0:
            return True
        return False
    except Exception as e:
        print(f"⚠️ Could not parse countdown timer: {e}")
        return True


def extend_time_with_retry(page, acc_name):
    """تلاش برای تمدید تایمر تا ۳ بار در صورت صفر بودن"""
    max_attempts = 3
    captcha_img_selector = "#extendfreeplanform-captcha-image"
    captcha_input_selector = "#extendfreeplanform-captcha"
    button_selector = 'button:has-text("Extend time")'

    for attempt in range(1, max_attempts + 1):
        print(f"\n🔄 Attempt {attempt}/{max_attempts} to extend time...")

        if not page.is_visible(button_selector):
            print(f"⚠️ 'Extend time' button not visible on attempt {attempt}.")
            page.reload(timeout=60000)
            page.wait_for_timeout(3000)
            continue

        # حل کپچا
        if page.is_visible(captcha_img_selector):
            print("⚠️ CAPTCHA detected! Attempting to solve with AI...")
            try:
                captcha_bytes = page.locator(captcha_img_selector).screenshot()
                captcha_text = ocr.classification(captcha_bytes)
                print(f"🧩 AI solved CAPTCHA as: '{captcha_text}'")

                page.fill(captcha_input_selector, "")  # پاک کردن ورودی قبلی
                page.fill(captcha_input_selector, captcha_text)
                page.wait_for_timeout(1000)
            except Exception as e:
                print(f"❌ Failed to solve captcha: {e}")

        # کلیک روی دکمه تمدید
        print("👉 Clicking Extend button...")
        page.click(button_selector)
        page.wait_for_timeout(5000)  # صبر برای اعمال تغییرات

        # چک کردن تایمر بعد از تمدید
        if not is_countdown_zero(page):
            print(
                f"✅ Success: Server time extended successfully for {acc_name} on attempt {attempt}!"
            )
            return True
        else:
            print(
                f"❌ Extension attempt {attempt} failed. Countdown is still 00:00:00."
            )
            if attempt < max_attempts:
                print("Refreshing page for next attempt...")
                page.reload(timeout=60000)
                page.wait_for_timeout(3000)

    # اگر بعد از ۳ بار تمدید نشد
    error_msg = f"🚨 **Alert for {acc_name}**:\nFailed to extend server plan after {max_attempts} attempts! Countdown remains at 00:00:00."
    print(f"\n{error_msg}")
    send_telegram_alert(error_msg)
    return False


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
            print(
                f"⚠️ Session expired for {acc['name']}. Removing {state_file} and re-logging in..."
            )
            os.remove(state_file)
            context.close()
            return process_account(browser, acc)
    else:
        print(f"🌐 No {state_file} found. Opening login page...")
        context = browser.new_context()
        page = context.new_page()

        page.goto(LOGIN_URL, timeout=60000)
        print("1. Filling login credentials...")
        page.fill(
            'input[name*="login"], input[name*="username"], input[type="text"], input[type="email"]',
            username,
        )
        page.fill('input[name*="password"], input[type="password"]', password)

        print("2. Clicking login button...")
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_timeout(5000)

        print(f"3. Navigating to server panel: {server_url}")
        page.goto(server_url, timeout=60000)
        page.wait_for_timeout(3000)

    # ۱. بررسی وضعیت آنلاین بودن سرور و زدن دکمه Start در صورت نیاز
    check_and_start_server(page)

    # ۲. تمدید زمان با متد ۳ بار تلاش و ارسال پیام تلگرام در صورت شکست
    extend_time_with_retry(page, acc["name"])

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
