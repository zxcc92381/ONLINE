import io
import os
import time
import uuid
import urllib.parse
import urllib.request
import ddddocr
from PIL import Image
from playwright.sync_api import sync_playwright

# تنظیمات ربات تلگرام
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

# لیست اکانت‌ها و سرورها
ACCOUNTS = [
    {
        "name": "Server 1",
        "username": os.environ.get("LEME_USERNAME", "YOUR_USERNAME"),
        "password": os.environ.get("LEME_PASSWORD", "YOUR_PASSWORD"),
        "server_url": "https://lemehost.com/server/10228912/free-plan",
        "state_file": "state.json",
    },
    {
        "name": "Server 2",
        "username": os.environ.get("LEME_USERNAME_2", "YOUR_USERNAME_2"),
        "password": os.environ.get("LEME_PASSWORD_2", "YOUR_PASSWORD_2"),
        "server_url": "https://lemehost.com/server/10231954/free-plan",
        "state_file": "state2.json",
    },
]

LOGIN_URL = "https://lemehost.com/site/login"

# لود کردن مدل ddddocr
ocr = ddddocr.DdddOcr(show_ad=False)


def log_and_notify(message):
    """چاپ پیام در ترمینال و ارسال همزمان لاگ به تلگرام"""
    print(message)
    
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload)
        with urllib.request.urlopen(req) as response:
            pass
    except Exception as e:
        print(f"❌ Failed to send log to Telegram: {e}")


def make_background_white(image_bytes):
    """جلوگیری از سیاه شدن تصاویر شفاف (Transparent PNG)"""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        # ساخت یک تصویر سفید با همان ابعاد
        white_bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        # قرار دادن تصویر کپچا روی پس‌زمینه سفید
        combined = Image.alpha_composite(white_bg, img).convert("RGB")
        
        output = io.BytesIO()
        combined.save(output, format="PNG")
        return output.getvalue()
    except Exception:
        return image_bytes


def send_telegram_photo(image_bytes, caption=""):
    """ارسال عکس کپچا به همراه توضیحات به تلگرام"""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    boundary = uuid.uuid4().hex
    
    # اصلاح پس‌زمینه شفاف برای نمایش تمیز در تلگرام
    display_bytes = make_background_white(image_bytes)

    body = bytearray()
    
    body.extend(f"--{boundary}\r\n".encode('utf-8'))
    body.extend(f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{TELEGRAM_CHAT_ID}\r\n'.encode('utf-8'))
    
    if caption:
        body.extend(f"--{boundary}\r\n".encode('utf-8'))
        body.extend(f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode('utf-8'))
        
    body.extend(f"--{boundary}\r\n".encode('utf-8'))
    body.extend(f'Content-Disposition: form-data; name="photo"; filename="captcha.png"\r\n'.encode('utf-8'))
    body.extend(b'Content-Type: image/png\r\n\r\n')
    body.extend(display_bytes)
    body.extend(b'\r\n')
    
    body.extend(f"--{boundary}--\r\n".encode('utf-8'))

    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(body))
    }

    try:
        req = urllib.request.Request(url, data=bytes(body), headers=headers)
        with urllib.request.urlopen(req) as response:
            pass
    except Exception as e:
        print(f"❌ Failed to send Telegram photo: {e}")


def check_and_start_server(page, acc_name):
    """چک کردن وضعیت آنلاین بودن و کلیک روی Start"""
    try:
        status_locator = page.locator('[data-put="status"]')
        if status_locator.is_visible():
            status_text = status_locator.text_content().strip().lower()
            log_and_notify(f"📊 [{acc_name}] Current Server Status: '{status_text}'")

            if status_text != "online":
                log_and_notify(f"🔴 [{acc_name}] Server is NOT online. Attempting to click Start...")
                start_btn = page.locator('button[data-state="start"]')
                if start_btn.is_visible():
                    start_btn.click(force=True)
                    log_and_notify(f"▶️ [{acc_name}] Clicked 'Start' button successfully.")
                    page.wait_for_timeout(3000)
                else:
                    log_and_notify(f"⚠️ [{acc_name}] Start button not found.")
            else:
                log_and_notify(f"🟢 [{acc_name}] Server is already online.")
        else:
            log_and_notify(f"⚠️ [{acc_name}] Server status element not found.")
    except Exception as e:
        log_and_notify(f"❌ [{acc_name}] Error checking server status: {e}")


def is_countdown_zero(page):
    """بررسی اینکه آیا تایمر معکوس صفر است یا خیر"""
    try:
        countdown_locator = page.locator("#countdown-free-plan")
        if not countdown_locator.is_visible():
            return True

        text = countdown_locator.text_content().strip()
        clean_text = text.replace(":", "").strip()
        if clean_text.isdigit() and int(clean_text) == 0:
            return True
        return False
    except Exception as e:
        print(f"⚠️ Could not parse countdown timer: {e}")
        return True


def extend_time_with_retry(page, acc_name):
    """تلاش برای حل کپچا، ارسال تصویر به تلگرام و تمدید زمان"""
    max_attempts = 5
    captcha_img_selector = "#extendfreeplanform-captcha-image"
    captcha_input_selector = "#extendfreeplanform-captcha"
    button_selector = 'button:has-text("Extend time")'

    if not is_countdown_zero(page):
        log_and_notify(f"🟢 [{acc_name}] Time is already extended. No action needed.")
        return True

    for attempt in range(1, max_attempts + 1):
        log_and_notify(f"🔄 [{acc_name}] Attempt {attempt}/{max_attempts} to solve CAPTCHA & extend time...")

        if not page.is_visible(button_selector):
            log_and_notify(f"⚠️ [{acc_name}] 'Extend time' button not visible. Reloading page...")
            page.reload(timeout=60000)
            page.wait_for_timeout(3000)
            continue

        # حل کپچا
        if page.is_visible(captcha_img_selector):
            try:
                # گرفتن عکس خام مستقیم از عنصر بدون هیچ دستکاری
                raw_captcha_bytes = page.locator(captcha_img_selector).screenshot()
                
                # خواندن مستقیم توسط ddddocr
                captcha_text = ocr.classification(raw_captcha_bytes).strip()
                
                # ارسال به تلگرام همراه با عکس صحیح
                caption = f"🧩 [{acc_name}] CAPTCHA Attempt #{attempt}\nAI Result: '{captcha_text}'"
                send_telegram_photo(raw_captcha_bytes, caption=caption)

                # پر کردن اینپوت کپچا
                page.fill(captcha_input_selector, "")
                page.fill(captcha_input_selector, captcha_text)
                page.wait_for_timeout(500)

            except Exception as e:
                log_and_notify(f"❌ [{acc_name}] Error solving captcha: {e}")

        # کلیک روی دکمه Extend time
        log_and_notify(f"👉 [{acc_name}] Clicking Extend button...")
        page.click(button_selector)
        page.wait_for_timeout(4000)

        # چک کردن تایمر
        if not is_countdown_zero(page):
            log_and_notify(f"✅ [{acc_name}] SUCCESS! Server time extended on attempt {attempt}.")
            return True
        else:
            log_and_notify(f"❌ [{acc_name}] Attempt {attempt} failed. Countdown is still 00:00:00.")
            if attempt < max_attempts:
                if page.is_visible(captcha_img_selector):
                    log_and_notify(f"🔄 [{acc_name}] Refreshing CAPTCHA image for next try...")
                    page.click(captcha_img_selector)
                    page.wait_for_timeout(2000)

    error_msg = f"🚨 **ALERT [{acc_name}]**:\nFailed to extend plan after {max_attempts} attempts!"
    log_and_notify(error_msg)
    return False


def process_account(browser, acc):
    acc_name = acc["name"]
    log_and_notify(f"\n==========================================\n🚀 Processing: {acc_name}\n==========================================")

    state_file = acc["state_file"]
    server_url = acc["server_url"]
    username = acc["username"]
    password = acc["password"]

    if os.path.exists(state_file):
        log_and_notify(f"🔑 [{acc_name}] Found session state. Navigating to panel...")
        context = browser.new_context(storage_state=state_file)
        page = context.new_page()

        page.goto(server_url, timeout=60000)
        page.wait_for_timeout(3000)

        if "login" in page.url.lower():
            log_and_notify(f"⚠️ [{acc_name}] Session expired. Re-logging in...")
            os.remove(state_file)
            context.close()
            return process_account(browser, acc)
    else:
        log_and_notify(f"🌐 [{acc_name}] No session found. Logging in...")
        context = browser.new_context()
        page = context.new_page()

        page.goto(LOGIN_URL, timeout=60000)
        page.fill('input[name*="login"], input[name*="username"], input[type="text"], input[type="email"]', username)
        page.fill('input[name*="password"], input[type="password"]', password)
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_timeout(5000)

        page.goto(server_url, timeout=60000)
        page.wait_for_timeout(3000)

    # ۱. استارت سرور
    check_and_start_server(page, acc_name)

    # ۲. تمدید زمان
    extend_time_with_retry(page, acc_name)

    try:
        context.storage_state(path=state_file)
    except Exception:
        pass

    context.close()


def main():
    log_and_notify("🤖 **Bot Script Execution Started**")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for acc in ACCOUNTS:
            try:
                process_account(browser, acc)
            except Exception as e:
                log_and_notify(f"❌ Error processing {acc['name']}: {e}")

        log_and_notify("\n🏁 **All accounts processed. Execution finished.**")
        browser.close()


if __name__ == "__main__":
    main()
