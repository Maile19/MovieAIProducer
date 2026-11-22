import os
from playwright.sync_api import sync_playwright

def test_all():
    os.environ["DISPLAY"] = ":99"
    results = {}
    with sync_playwright() as pw:
        for acc_id in range(1, 6):
            profile_dir = f"/opt/flow-profiles/akun_{acc_id}"
            if not os.path.exists(profile_dir):
                results[acc_id] = "DIR_NOT_FOUND"
                continue
            try:
                context = pw.chromium.launch_persistent_context(
                    user_data_dir=profile_dir,
                    executable_path="/usr/bin/google-chrome-stable",
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--window-size=1920,1080",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                    ],
                    viewport={"width": 1920, "height": 1080},
                )
                page = context.new_page() if not context.pages else context.pages[0]
                page.goto("https://flow.google.com/", timeout=40000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                url = page.url
                title = page.title()
                body = page.locator("body").inner_text()
                is_pro = "PRO" in body
                is_login = "signin" in url.lower() or "accounts.google.com" in url.lower()
                has_new_project = ("project" in body.lower()) or ("proyek" in body.lower())
                screenshot_path = f"/var/www/producer-media/debug/audit_akun_{acc_id}.png"
                page.screenshot(path=screenshot_path)
                results[acc_id] = {
                    "url": url,
                    "title": title[:50],
                    "is_pro": is_pro,
                    "is_login_redirect": is_login,
                    "has_new_project": has_new_project,
                    "screenshot": screenshot_path
                }
                context.close()
            except Exception as e:
                results[acc_id] = f"ERROR: {str(e)[:100]}"
    print("RESULTS:")
    for k, v in results.items():
        print(f"Akun #{k}: {v}")

if __name__ == "__main__":
    test_all()
