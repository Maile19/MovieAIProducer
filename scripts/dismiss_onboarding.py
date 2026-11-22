import os
from playwright.sync_api import sync_playwright

def dismiss_all():
    os.environ["DISPLAY"] = ":99"
    with sync_playwright() as pw:
        for acc_id in range(1, 6):
            profile_dir = f"/opt/flow-profiles/akun_{acc_id}"
            print(f"Checking onboarding on Akun #{acc_id}...")
            context = pw.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                executable_path="/usr/bin/google-chrome-stable",
                headless=False,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
                viewport={"width": 1920, "height": 1080},
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://flow.google.com/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)
            
            # Check for "Berikutnya" or "Lanjutkan" or "Setuju" or "Agree"
            btns = page.locator("button:has-text('Berikutnya'), button:has-text('Lanjutkan'), button:has-text('Setuju'), button:has-text('Next'), button:has-text('Agree'), button:has-text('Got it')").all()
            for b in btns:
                if b.is_visible():
                    txt = b.inner_text().strip()
                    print(f"  Akun #{acc_id}: Found button {txt!r}, clicking...")
                    b.click(force=True)
                    page.wait_for_timeout(2000)
            
            # Check if second step appeared
            btns2 = page.locator("button:has-text('Berikutnya'), button:has-text('Lanjutkan'), button:has-text('Setuju'), button:has-text('Next'), button:has-text('Agree'), button:has-text('Got it'), button:has-text('Selesai')").all()
            for b in btns2:
                if b.is_visible():
                    txt = b.inner_text().strip()
                    print(f"  Akun #{acc_id}: Found step 2 button {txt!r}, clicking...")
                    b.click(force=True)
                    page.wait_for_timeout(2000)
                    
            page.screenshot(path=f"/var/www/producer-media/debug/clean_akun_{acc_id}.png")
            print(f"  Akun #{acc_id} ready.")
            context.close()

if __name__ == "__main__":
    dismiss_all()
