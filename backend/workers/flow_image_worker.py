"""Google Flow Image Automation Worker Pool for MovieAIProducer.

Automates image generation across a pool of up to 5 Google Flow PRO accounts using Playwright Chromium.
Features:
- Multi-browser concurrency (configurable via MAX_CONCURRENT_FLOW_BROWSERS, default 2)
- Strict per-account profile file locking (/tmp/flow_account_<id>.lock)
- Safe warm browser session reuse (up to 4 jobs per batch) with 75-second idle auto-close
- Zero anchor bleed / leftover prompt isolation between cards
- 88% network payload optimization via high-quality JPEG anchor caching (quality 93, 1024px max)
- 4.0s staggered launch & RAM availability guard (> 1800 MB required for concurrency > 1)
- Structured [FlowTimer] phase logging (browser_init_ms, upload_ms, generate_wait_ms, download_ms)
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import fcntl
import io
import json
import logging
from math import gcd
import os
from pathlib import Path
import random
import re
import signal
import sqlite3
import sys
import threading
import time
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import BrowserContext, Page, sync_playwright

from backend.app.core.anchor_optimizer import get_optimized_anchor_path
from backend.app.core.proxy_health import (
    DEFAULT_SOCKS5_URL,
    check_socks5_health,
    get_cached_socks5_health,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [FlowWorker] %(message)s",
)
logger = logging.getLogger("flow_image_worker")

# Timezone & Directories
WIB_TZ = ZoneInfo("Asia/Jakarta")
BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_DIR = Path("/var/www/producer-media/images")
DEBUG_DIR = Path("/var/www/producer-media/debug")
CONFIG_PATH = BASE_DIR / "backend" / "config" / "flow_selectors.json"
DB_PATH = BASE_DIR / "data" / "movieai.db"
LOCK_FILE_PATH = Path("/tmp/flow_worker.lock")

# Concurrency & Stagger
DEFAULT_MAX_CONCURRENT_BROWSERS = 2
_LAUNCH_LOCK = threading.Lock()
_LAST_LAUNCH_TIME = 0.0

running = True


def signal_handler(signum, frame):
    global running
    logger.info(f"Signal {signum} diterima, bersiap mematikan worker pool...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def get_available_memory_mb() -> float:
    """Return available system RAM in MB."""
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    parts = line.split()
                    return float(parts[1]) / 1024.0
    except Exception:
        pass
    return 4000.0


def get_effective_concurrency() -> int:
    """Determine effective concurrency based on env config and available system RAM."""
    try:
        env_val = int(os.environ.get("MAX_CONCURRENT_FLOW_BROWSERS", DEFAULT_MAX_CONCURRENT_BROWSERS))
    except ValueError:
        env_val = DEFAULT_MAX_CONCURRENT_BROWSERS

    avail_mb = get_available_memory_mb()
    if avail_mb < 1800.0 and env_val > 1:
        logger.warning(
            f"[ResourceGuard] Memori tersedia rendah ({avail_mb:.1f} MB < 1800 MB). "
            f"Membatasi concurrency ke 1 browser."
        )
        return 1
    return max(1, min(env_val, 4))


def stagger_browser_launch():
    """Ensure at least 4.0s gap between browser launches to avoid SOCKS5 / tunnel port congestion."""
    global _LAST_LAUNCH_TIME
    with _LAUNCH_LOCK:
        now = time.time()
        elapsed = now - _LAST_LAUNCH_TIME
        if elapsed < 4.0:
            sleep_time = 4.0 - elapsed
            logger.info(f"[LaunchStagger] Menunggu {sleep_time:.2f}s sebelum launch browser berikutnya...")
            time.sleep(sleep_time)
        _LAST_LAUNCH_TIME = time.time()


class AccountProfileLock:
    """Strict per-account profile directory lock to guarantee no two workers touch the same profile."""

    def __init__(self, account_id: int):
        self.account_id = account_id
        self.lock_path = Path(f"/tmp/flow_account_{account_id}.lock")
        self._fp = None

    def acquire(self) -> bool:
        try:
            self._fp = open(self.lock_path, "w")
            fcntl.flock(self._fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (BlockingIOError, OSError):
            if self._fp:
                try:
                    self._fp.close()
                except Exception:
                    pass
                self._fp = None
            return False

    def release(self):
        if self._fp:
            try:
                fcntl.flock(self._fp, fcntl.LOCK_UN)
                self._fp.close()
            except Exception:
                pass
            self._fp = None


class ProxyOfflineError(Exception):
    """Raised when SOCKS5 Android proxy connection fails or drops."""
    pass


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=10000;")
    return conn


def load_selectors() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        logger.error(f"Selectors config not found at {CONFIG_PATH}")
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_flow_settings(conn: sqlite3.Connection) -> dict[str, str]:
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM flow_settings")
    rows = cursor.fetchall()
    return {row["key"]: row["value"] for row in rows}


def reset_daily_counts_if_needed(conn: sqlite3.Connection):
    today_wib = datetime.now(WIB_TZ).strftime("%Y-%m-%d")
    with conn:
        conn.execute(
            """
            UPDATE flow_accounts
            SET daily_count = 0, last_reset_date = ?
            WHERE last_reset_date != ?
            """,
            (today_wib, today_wib),
        )


def auto_recover_cooldown_accounts(conn: sqlite3.Connection):
    now_utc = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            """
            UPDATE flow_accounts
            SET status = 'active', cooldown_until = NULL, consecutive_failures = 0
            WHERE status = 'cooldown'
              AND cooldown_until IS NOT NULL
              AND cooldown_until <= ?
            """,
            (now_utc,),
        )


def recover_all_busy_accounts_on_startup(conn: sqlite3.Connection):
    """Reset all accounts marked 'busy' to 'active' on worker startup (no active browser)."""
    now_utc = datetime.now(timezone.utc).isoformat()
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE flow_accounts
            SET status = 'active', updated_at = ?
            WHERE status = 'busy'
            """,
            (now_utc,),
        )
        acc_count = cursor.rowcount
        cursor.execute(
            """
            UPDATE flow_image_jobs
            SET status = 'queued'
            WHERE status = 'processing'
            """
        )
        job_count = cursor.rowcount
    logger.info(
        f"Startup Recovery: {acc_count} akun 'busy' di-reset ke 'active', "
        f"{job_count} job 'processing' dikembalikan ke 'queued'."
    )


def cleanup_stale_busy_accounts(conn: sqlite3.Connection, stale_threshold_minutes: int = 6):
    """Recover accounts stuck in 'busy' status for longer than threshold without active progress."""
    now_utc = datetime.now(timezone.utc)
    cutoff = (now_utc - timedelta(minutes=stale_threshold_minutes)).isoformat()
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE flow_accounts
            SET status = 'active', updated_at = ?
            WHERE status = 'busy'
              AND updated_at <= ?
            """,
            (now_utc.isoformat(), cutoff),
        )
        if cursor.rowcount > 0:
            logger.warning(
                f"Cleanup Stale Busy: Membebaskan {cursor.rowcount} akun 'busy' stale (> {stale_threshold_minutes}m)."
            )


def claim_next_job_and_lock_account(
    conn: sqlite3.Connection,
) -> tuple[sqlite3.Row | None, sqlite3.Row | None, AccountProfileLock | None]:
    """Atomically claim the next queued job and acquire exclusive profile flock for an eligible active account."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM flow_image_jobs
        WHERE status = 'queued'
        ORDER BY created_at ASC
        LIMIT 10
        """
    )
    jobs = cursor.fetchall()
    if not jobs:
        return None, None, None

    cursor.execute(
        """
        SELECT * FROM flow_accounts
        WHERE status = 'active'
        ORDER BY
            CASE WHEN last_used_at IS NULL THEN 0 ELSE 1 END ASC,
            last_used_at ASC,
            id ASC
        """
    )
    active_accounts = cursor.fetchall()
    if not active_accounts:
        return None, None, None

    for job in jobs:
        pref_id = job["preferred_account_id"]
        candidate_accounts = (
            [a for a in active_accounts if a["id"] == pref_id]
            if pref_id
            else active_accounts
        )

        for acc in candidate_accounts:
            acc_id = acc["id"]
            lock = AccountProfileLock(acc_id)
            if not lock.acquire():
                # Profile directory is currently locked by another worker
                continue

            try:
                with conn:
                    cursor.execute("SELECT status FROM flow_accounts WHERE id = ?", (acc_id,))
                    row = cursor.fetchone()
                    if not row or row["status"] != "active":
                        lock.release()
                        continue

                    now_iso = datetime.now(timezone.utc).isoformat()
                    cursor.execute(
                        """
                        UPDATE flow_image_jobs
                        SET status = 'processing', assigned_account_id = ?, started_at = ?
                        WHERE id = ? AND status = 'queued'
                        """,
                        (acc_id, now_iso, job["id"]),
                    )
                    if cursor.rowcount == 0:
                        lock.release()
                        continue

                    cursor.execute(
                        """
                        UPDATE flow_accounts
                        SET status = 'busy', updated_at = ?
                        WHERE id = ?
                        """,
                        (now_iso, acc_id),
                    )

                logger.info(
                    f"[AtomicClaim] Job {job['id']} assigned to Akun #{acc_id} "
                    f"({acc['label']}) with exclusive profile lock."
                )
                return job, acc, lock

            except Exception as e:
                lock.release()
                logger.warning(f"Atomic claim exception: {e}")
                continue

    return None, None, None


def claim_job_for_specific_account(conn: sqlite3.Connection, account_id: int) -> sqlite3.Row | None:
    """Atomically claim the next queued job eligible for a currently held warm account."""
    cursor = conn.cursor()
    with conn:
        cursor.execute(
            """
            SELECT * FROM flow_image_jobs
            WHERE status = 'queued'
              AND (preferred_account_id IS NULL OR preferred_account_id = ?)
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (account_id,),
        )
        job = cursor.fetchone()
        if not job:
            return None

        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            UPDATE flow_image_jobs
            SET status = 'processing', assigned_account_id = ?, started_at = ?
            WHERE id = ? AND status = 'queued'
            """,
            (account_id, now_iso, job["id"]),
        )
        if cursor.rowcount > 0:
            cursor.execute(
                """
                UPDATE flow_accounts
                SET status = 'busy', updated_at = ?
                WHERE id = ?
                """,
                (now_iso, account_id),
            )
            logger.info(f"[WarmClaim] Job {job['id']} claimed by warm Akun #{account_id}.")
            return job
    return None


def has_queued_jobs_for_other_accounts(conn: sqlite3.Connection, current_account_id: int) -> bool:
    """Check if queued jobs exist that could run on other accounts."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 1 FROM flow_image_jobs
        WHERE status = 'queued'
          AND (preferred_account_id IS NULL OR preferred_account_id != ?)
        LIMIT 1
        """,
        (current_account_id,),
    )
    return cursor.fetchone() is not None


def mark_account_status(
    conn: sqlite3.Connection,
    account_id: int,
    status: str,
    last_error: str | None = None,
    cooldown_minutes: int = 15,
):
    now_utc = datetime.now(timezone.utc)
    cooldown_until = None
    if status == "cooldown":
        cooldown_until = (now_utc + timedelta(minutes=cooldown_minutes)).isoformat()

    with conn:
        if status == "cooldown":
            conn.execute(
                """
                UPDATE flow_accounts
                SET status = ?, cooldown_until = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, cooldown_until, last_error, now_utc.isoformat(), account_id),
            )
        elif status == "need_relogin":
            conn.execute(
                """
                UPDATE flow_accounts
                SET status = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, last_error, now_utc.isoformat(), account_id),
            )
        else:
            conn.execute(
                """
                UPDATE flow_accounts
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, now_utc.isoformat(), account_id),
            )


def normalize_asset_slot(slot: str | None) -> str:
    norm = (slot or "closeup").lower().strip()
    if norm in ("closeup", "close_up", "headshot", "portrait", "master_closeup", "slot_1"):
        return "closeup"
    if norm in ("three_quarter", "3/4", "threequarter"):
        return "three_quarter"
    if norm in ("tpose", "sheet_tpose", "t_pose"):
        return "tpose"
    if norm in ("action", "sheet_action"):
        return "action"
    if norm in ("expression", "sheet_expression"):
        return "expression"
    if norm in ("back", "turnaround_back"):
        return "back"
    if norm == "side":
        return "side"
    return "front"


def auto_attach_job_result(conn: sqlite3.Connection, job_id: str, image_url: str):
    """Atomically auto-attach completed Google Flow image result to character or state in SQLite."""
    try:
        row = conn.execute(
            """
            SELECT character_id, asset_slot, target_type, state_id, prompt, reference_image_paths, aspect_ratio
            FROM flow_image_jobs WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

        if not row:
            return

        char_id = str(row[0]) if row[0] else None
        asset_slot = row[1]
        target_type = row[2]
        state_id = str(row[3]) if row[3] else None
        prompt = row[4]
        ref_paths_raw = row[5]
        ref_paths = json.loads(ref_paths_raw) if (ref_paths_raw and isinstance(ref_paths_raw, str)) else (ref_paths_raw or [])
        aspect_ratio = row[6] or "16:9"

        if target_type == "state" and state_id:
            cur = conn.execute(
                "UPDATE character_states SET image_url = ? WHERE id = ?",
                (image_url, state_id),
            )
            if cur.rowcount > 0:
                logger.info(f"[AutoAttach] Attached {job_id} -> character_state={state_id}")
            else:
                logger.warning(f"[AutoAttach] CharacterState {state_id} not found for job {job_id}")
            return

        if char_id and asset_slot:
            slot_key = normalize_asset_slot(asset_slot)
            col_map = {
                "closeup": "closeup_image_url",
                "front": "front_image_url",
                "side": "side_image_url",
                "three_quarter": "three_quarter_image_url",
                "back": "back_image_url",
                "tpose": "tpose_image_url",
                "action": "action_image_url",
                "expression": "expression_image_url",
            }
            target_col = col_map.get(slot_key, "front_image_url")

            char_row = conn.execute(
                "SELECT sheet_metadata, dna_seed FROM characters WHERE id = ?",
                (char_id,),
            ).fetchone()

            if not char_row:
                logger.warning(f"[AutoAttach] Character {char_id} not found for job {job_id}")
                return

            existing_meta = {}
            if char_row[0]:
                try:
                    existing_meta = json.loads(char_row[0]) if isinstance(char_row[0], str) else dict(char_row[0])
                except Exception:
                    existing_meta = {}
            dna_seed = char_row[1]

            existing_meta[slot_key] = {
                "image_url": image_url,
                "prompt": prompt,
                "anchors_used": ref_paths,
                "provider": "google_flow",
                "seed": dna_seed,
                "aspect_ratio": aspect_ratio,
                "rendered_at": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
            }

            cur = conn.execute(
                f"UPDATE characters SET {target_col} = ?, sheet_metadata = ? WHERE id = ?",
                (image_url, json.dumps(existing_meta), char_id),
            )
            if cur.rowcount > 0:
                logger.info(f"[AutoAttach] Attached {job_id} -> character={char_id} slot={slot_key} (col={target_col})")
            else:
                logger.warning(f"[AutoAttach] Zero rows updated for character {char_id}")
    except Exception as exc:
        logger.error(f"[AutoAttach] Failed to auto-attach job {job_id}: {exc}", exc_info=True)


def update_job_status(
    conn: sqlite3.Connection,
    job_id: str,
    status: str,
    assigned_account_id: int | None = None,
    output_filename: str | None = None,
    image_url: str | None = None,
    debug_screenshot_url: str | None = None,
    error_message: str | None = None,
    increment_retry: bool = False,
):
    now_utc = datetime.now(timezone.utc).isoformat()
    with conn:
        if status == "completed":
            conn.execute(
                """
                UPDATE flow_image_jobs
                SET status = ?, output_filename = ?, image_url = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, output_filename, image_url, now_utc, job_id),
            )
            auto_attach_job_result(conn, job_id, image_url)
        elif status == "failed":
            conn.execute(
                """
                UPDATE flow_image_jobs
                SET status = ?, error_message = ?, debug_screenshot_url = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, error_message, debug_screenshot_url, now_utc, job_id),
            )
        elif status == "processing":
            conn.execute(
                """
                UPDATE flow_image_jobs
                SET status = ?, assigned_account_id = ?, started_at = ?
                WHERE id = ?
                """,
                (status, assigned_account_id, now_utc, job_id),
            )
        elif status == "queued" and increment_retry:
            conn.execute(
                """
                UPDATE flow_image_jobs
                SET status = 'queued', retry_count = retry_count + 1, error_message = ?, debug_screenshot_url = ?
                WHERE id = ?
                """,
                (error_message, debug_screenshot_url, job_id),
            )


def record_account_success(conn: sqlite3.Connection, account_id: int):
    now_utc = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            """
            UPDATE flow_accounts
            SET daily_count = daily_count + 1,
                total_count = total_count + 1,
                consecutive_failures = 0,
                last_used_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (now_utc, now_utc, account_id),
        )


def record_account_failure(
    conn: sqlite3.Connection,
    account_id: int,
    error_msg: str,
    cooldown_minutes: int = 15,
):
    now_utc = datetime.now(timezone.utc).isoformat()
    with conn:
        cursor = conn.cursor()
        cursor.execute("SELECT consecutive_failures FROM flow_accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        fails = (row["consecutive_failures"] if row else 0) + 1

        if fails >= 3:
            cooldown_until = (datetime.now(timezone.utc) + timedelta(minutes=cooldown_minutes)).isoformat()
            cursor.execute(
                """
                UPDATE flow_accounts
                SET status = 'cooldown', cooldown_until = ?, consecutive_failures = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (cooldown_until, fails, error_msg, now_utc, account_id),
            )
            logger.warning(f"Akun #{account_id} mengalami {fails} kegagalan berturut-turut. Cooldown {cooldown_minutes}m.")
        else:
            cursor.execute(
                """
                UPDATE flow_accounts
                SET consecutive_failures = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (fails, error_msg, now_utc, account_id),
            )


def find_matching_locator(page: Page, selectors: list[str], timeout_ms: int = 3000):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=timeout_ms):
                return loc
        except Exception:
            continue
    return None


def get_full_resolution_url(src: str) -> str:
    """Normalize Google Flow asset URL to ensure 100% uncompressed native full-resolution download (=s0)."""
    if not src:
        return src
    if "flow.google.com/asb/" in src or "googleusercontent.com" in src or "/asb/" in src:
        base_url = re.sub(r"=[^/]+$", "", src)
        return f"{base_url}=s0"
    return src


def download_image_from_src(page: Page, src: str) -> bytes | None:
    """Unduh data biner gambar resolusi penuh asli dari src."""
    if not src:
        return None

    if src.startswith("/"):
        try:
            src = page.evaluate("(s) => new URL(s, window.location.href).href", src)
        except Exception:
            pass

    # 1. Base64 Data URL
    if src.startswith("data:image"):
        try:
            _, b64_data = src.split(",", 1)
            return base64.b64decode(b64_data)
        except Exception as e:
            logger.warning(f"Gagal decode base64 data URL: {e}")
            return None

    # 2. HTTP / HTTPS URL - Download full-res via page.request (=s0)
    if src.startswith("http://") or src.startswith("https://"):
        full_res_url = get_full_resolution_url(src)
        try:
            logger.info(f"Mengunduh gambar resolusi penuh dari: {full_res_url[:100]}...")
            resp = page.request.get(full_res_url, timeout=30000)
            if resp.ok:
                body = resp.body()
                if body and len(body) > 50000:
                    return body
        except Exception as e:
            logger.debug(f"Direct request ke full_res_url gagal ({e}), mencoba fallback...")

        # Fallback via in-page fetch()
        try:
            b64_res = page.evaluate("""async (url) => {
                const response = await fetch(url);
                const blob = await response.blob();
                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result);
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
            }""", full_res_url)
            if b64_res and "," in b64_res:
                _, data = b64_res.split(",", 1)
                b = base64.b64decode(data)
                if len(b) > 50000:
                    return b
        except Exception as fe:
            logger.debug(f"In-page fetch fallback ke full_res_url gagal ({fe})...")

        # Fallback ke src original
        try:
            resp = page.request.get(src, timeout=20000)
            if resp.ok:
                body = resp.body()
                if body and len(body) > 50000:
                    return body
        except Exception:
            pass

        try:
            b64_orig = page.evaluate("""async (url) => {
                const response = await fetch(url);
                const blob = await response.blob();
                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result);
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
            }""", src)
            if b64_orig and "," in b64_orig:
                _, data = b64_orig.split(",", 1)
                b = base64.b64decode(data)
                if len(b) > 50000:
                    return b
        except Exception as e:
            logger.warning(f"Gagal mengunduh gambar via in-page fetch fallback: {e}")

    return None


def dismiss_onboarding_dialogs(page: Page, max_attempts: int = 4) -> None:
    """Otomatis mendeteksi dan menyelesaikan onboarding terms, modal dialog, dan banner pengumuman."""
    for attempt in range(max_attempts):
        try:
            dialog = page.locator("mat-dialog-container, [role='dialog'], .mat-mdc-dialog-container").first
            if not dialog.is_visible(timeout=1200):
                break

            logger.info(f"[Onboarding] Modal dialog terdeteksi (tahap {attempt + 1}), memproses penutupan otomatis...")

            # 1. Centang seluruh checkbox persetujuan yang belum aktif
            checkboxes = page.locator(
                "mat-dialog-container input[type='checkbox'], [role='dialog'] input[type='checkbox']"
            ).all()
            for cb in checkboxes:
                try:
                    if not cb.is_checked():
                        cb.click(force=True)
                        page.wait_for_timeout(300)
                except Exception:
                    pass

            # 2. Klik tombol 'Berikutnya' / 'Next' jika ada
            next_btn = page.locator(
                "mat-dialog-container button:has-text('Berikutnya'), "
                "[role='dialog'] button:has-text('Berikutnya'), "
                "button:has-text('Berikutnya'), "
                "button:has-text('Next')"
            ).first
            if next_btn.is_visible(timeout=600):
                next_btn.click(force=True)
                page.wait_for_timeout(1500)

            # 3. Scroll seluruh kontainer scrollable ke paling bawah
            page.evaluate("""() => {
                const targets = [
                    '.privacy-content',
                    '.terms-body-content',
                    '.mat-mdc-dialog-content',
                    '[mat-dialog-content]',
                    '.dialog-content'
                ];
                for (const sel of targets) {
                    const el = document.querySelector(sel);
                    if (el && el.scrollHeight > el.clientHeight) {
                        el.scrollTop = el.scrollHeight;
                        el.dispatchEvent(new Event('scroll'));
                    }
                }
            }""")
            page.wait_for_timeout(600)

            # 4. Klik tombol 'Saya setuju' / 'Lanjutkan' / 'Setuju' / 'Agree' / 'Got it'
            continue_btn = page.locator(
                "mat-dialog-container button:has-text('Saya setuju'), "
                "[role='dialog'] button:has-text('Saya setuju'), "
                "button:has-text('Saya setuju'), "
                "mat-dialog-container button:has-text('Lanjutkan'), "
                "[role='dialog'] button:has-text('Lanjutkan'), "
                "button:has-text('Lanjutkan'), "
                "button:has-text('Setuju'), "
                "button:has-text('Agree'), "
                "button:has-text('Got it'), "
                "button:has-text('Selesai')"
            ).first
            if continue_btn.is_visible(timeout=800) and not continue_btn.is_disabled():
                continue_btn.click(force=True)
                page.wait_for_timeout(1500)
            else:
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
                close_btn = page.locator(
                    "button:has-text('close'), button[aria-label*='Tutup' i], button[aria-label*='Close' i]"
                ).first
                if close_btn.is_visible(timeout=500):
                    close_btn.click(force=True)
                    page.wait_for_timeout(400)
        except Exception as e:
            logger.debug(f"[Onboarding] Pengecualian saat dismiss dialog: {e}")
            break

    try:
        if page.locator(".cdk-overlay-backdrop").is_visible(timeout=400):
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
    except Exception:
        pass


def execute_flow_generation(
    page: Page,
    selectors: dict[str, Any],
    job: sqlite3.Row,
    account: sqlite3.Row,
    is_warm: bool = False,
) -> bytes:
    """Execute single Google Flow image generation job with warm session reuse & telemetry."""
    t_start = time.perf_counter()
    browser_init_ms = 0.0
    upload_ms = 0.0
    generate_wait_ms = 0.0
    download_ms = 0.0

    job_id = str(job["id"])
    prompt = job["prompt"]
    aspect_ratio = job["aspect_ratio"] or "16:9"
    ref_paths = json.loads(job["reference_image_paths"]) if job["reference_image_paths"] else []

    # Identifikasi jenis Card untuk logging diagnostik
    card_label = "Universal Asset"
    prompt_upper = prompt.upper()
    if "[DYNAMIC STATE PROGRESSION:" in prompt_upper:
        m = re.search(r"\[DYNAMIC STATE PROGRESSION:\s*([^\]]+)\]", prompt, re.IGNORECASE)
        if m:
            card_label = m.group(1).strip()
    elif "SIDE PROFILE" in prompt_upper or "90-DEGREE LATERAL" in prompt_upper or "LATERAL SIDE-PROFILE" in prompt_upper or "CARD 4" in prompt_upper or "SIDE-PROFILE" in prompt_upper:
        card_label = "Card 4: Side Profile 90°"
    elif "3/4 HERO ANGLE" in prompt_upper or "THREE-QUARTER" in prompt_upper or "OBLIQUE STANDING" in prompt_upper or "CARD 5" in prompt_upper:
        card_label = "Card 5: 3/4 Hero Angle"
    elif "BACK VIEW" in prompt_upper or "REAR TURNAROUND" in prompt_upper or "180-DEGREE REAR" in prompt_upper or "CARD 6" in prompt_upper:
        card_label = "Card 6: Back View 180°"
    elif "T-POSE" in prompt_upper or "RIGGING SHEET" in prompt_upper or "RIGGING BASELINE" in prompt_upper or "CARD 7" in prompt_upper:
        card_label = "Card 7: T-Pose / Rigging Sheet"
    elif "DYNAMIC ACTION" in prompt_upper or "KINETIC MOTION" in prompt_upper or "OPERATIONAL STANCE" in prompt_upper or "CARD 8" in prompt_upper:
        card_label = "Card 8: Dynamic Action Pose"
    elif "EXPRESSION" in prompt_upper and ("3X2" in prompt_upper or "GRID" in prompt_upper or "MICRO-EXPRESSIONS" in prompt_upper):
        card_label = "Card 2: Expression Sheet 3x2"
    elif "FRONT VIEW" in prompt_upper or "ORTHOGONAL 0" in prompt_upper or "FRONTAL STANDING" in prompt_upper or "PRIMARY BODY ANCHOR" in prompt_upper or "CARD 3" in prompt_upper:
        card_label = "Card 3: Full Body Front"
    elif "CLOSEUP" in prompt_upper or "CLOSE-UP" in prompt_upper or "MASTER ANCHOR" in prompt_upper or ("PORTRAIT" in prompt_upper and "EXPRESSION" not in prompt_upper):
        card_label = "Card 1: Character Close-Up (Master Anchor)"

    logger.info(
        f"Memulai proses generate job {job_id} [{card_label}] pada Akun #{account['id']} "
        f"({account['label']}, is_warm={is_warm})..."
    )

    t_init_start = time.perf_counter()
    entry_url = selectors.get("entry_url", "https://flow.google.com/")

    # 1. Navigasi / Reset Proyek Bersih
    if not is_warm or "/project/" not in page.url:
        try:
            page.goto(entry_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as ne:
            err_str = str(ne)
            if any(term in err_str for term in [
                "ERR_PROXY_CONNECTION_FAILED",
                "ERR_SOCKS_CONNECTION_FAILED",
                "ERR_TUNNEL_CONNECTION_FAILED",
                "ERR_CONNECTION_RESET",
                "ERR_NAME_NOT_RESOLVED",
            ]):
                raise ProxyOfflineError(f"SOCKS5_PROXY_OFFLINE: {ne}")
            logger.info(f"Navigasi goto({entry_url}) warning: {ne}")

        if page.url.startswith("chrome-error://"):
            raise ProxyOfflineError(f"SOCKS5_PROXY_OFFLINE: Chrome navigasi ke {page.url}")

        page.wait_for_timeout(2000)
        dismiss_onboarding_dialogs(page)
    else:
        # Warm context reset: Klik 'New Project' agar kanvas & prompt bersih tanpa leftover anchor bleed
        logger.info(f"[{card_label}] Sesi warm aktif. Memastikan kanvas bersih & bebas dari anchor lama...")
        try:
            dismiss_onboarding_dialogs(page)
            new_btn = find_matching_locator(page, selectors.get("new_project_button", []), timeout_ms=3000)
            if new_btn:
                new_btn.click(force=True)
                page.wait_for_timeout(2000)
        except Exception as e:
            logger.debug(f"Warm project reset click: {e}")

    # Deteksi URL Login Google
    current_url = page.url
    login_cfg = selectors.get("login_detectors") or {}
    url_keywords = login_cfg.get("url_keywords", [
        "accounts.google.com/v3/signin",
        "accounts.google.com/signin",
        "accounts.google.com/ServiceLogin",
    ])
    for kw in url_keywords:
        if kw in current_url and "SignOutOptions" not in current_url:
            raise PermissionError(f"Akun #{account['id']} terlempar ke URL login Google: {current_url}")

    # Deteksi rate limit
    body_text = page.locator("body").inner_text()
    for rl_msg in selectors.get("rate_limit_indicators", []):
        if rl_msg.lower() in body_text.lower():
            raise TimeoutError(f"Rate limit terdeteksi pada Akun #{account['id']}: {rl_msg}")

    # Buka Project Canvas jika belum
    if "/project/" not in page.url:
        dismiss_onboarding_dialogs(page)
        new_proj_loc = find_matching_locator(page, selectors.get("new_project_button", []), timeout_ms=5000)
        if new_proj_loc:
            try:
                new_proj_loc.click(timeout=8000, force=True)
                page.wait_for_timeout(2000)
            except Exception as e:
                logger.info(f"Tombol new project click notice: {e}")

        if "/project/" not in page.url:
            try:
                page.wait_for_url("**/project/**", timeout=12000)
                page.wait_for_timeout(1500)
            except Exception:
                pass

    # Tutup panel kanan jika terbuka
    try:
        dismiss_onboarding_dialogs(page)
        close_panel = find_matching_locator(page, selectors.get("agent_panel_close", [
            ".agent-panel-header button:has-text('right_panel_close')",
            "button:has-text('right_panel_close')",
            "button[aria-label*='Tutup' i]",
            "button[aria-label*='Close' i]",
        ]), timeout_ms=1200)
        if close_panel:
            close_panel.click(force=True)
            page.wait_for_timeout(500)
    except Exception:
        pass

    # Pastikan mode Image & Aspect Ratio sesuai
    settings_btn = find_matching_locator(page, selectors.get("settings_trigger_button", [
        "button[aria-label*='Pemicu setelan']",
        ".settings-trigger-button",
        "button.settings-trigger-button",
        "button[aria-label*='Settings']",
    ]), timeout_ms=3000)

    if settings_btn:
        try:
            btn_txt = settings_btn.inner_text().strip().replace("\n", " ")
            logger.info(f"[{card_label}] Pemicu setelan ditemukan ('{btn_txt}'). Target Aspect Ratio: '{aspect_ratio}'.")
            settings_btn.click()
            try:
                page.wait_for_selector(".cdk-overlay-pane", timeout=2500)
            except Exception:
                page.wait_for_timeout(800)

            # Switch mode Gambar
            img_toggle = find_matching_locator(page, selectors.get("image_mode_switcher", [
                ".cdk-overlay-pane mat-button-toggle:has-text('Gambar')",
                ".cdk-overlay-pane mat-button-toggle:has-text('Image')",
                ".cdk-overlay-pane button:has-text('Gambar')",
                ".cdk-overlay-pane button:has-text('Image')",
            ]), timeout_ms=1500)
            if img_toggle:
                is_checked = page.evaluate("""(el) => {
                    return el.classList.contains('mat-button-toggle-checked') ||
                           el.getAttribute('aria-checked') === 'true';
                }""", img_toggle.element_handle())
                if not is_checked:
                    img_toggle.click(force=True)
                    page.wait_for_timeout(500)

            # Klik aspect ratio
            aspect_map = selectors.get("aspect_ratio", {})
            extra_aspect_sels = []
            if aspect_ratio == "3:4":
                extra_aspect_sels = [
                    ".cdk-overlay-pane mat-button-toggle:has-text('crop_portrait')",
                    ".cdk-overlay-pane button:has-text('crop_portrait')",
                    ".cdk-overlay-pane button[aria-label*='3:4']",
                ]
            elif aspect_ratio == "16:9":
                extra_aspect_sels = [
                    ".cdk-overlay-pane mat-button-toggle:has-text('crop_16_9')",
                    ".cdk-overlay-pane button:has-text('crop_16_9')",
                    ".cdk-overlay-pane button[aria-label*='16:9']",
                ]

            target_aspect_sels = (aspect_map.get(aspect_ratio) or []) + extra_aspect_sels + [
                f".cdk-overlay-pane mat-button-toggle:has-text('{aspect_ratio}')",
                f".cdk-overlay-pane button:has-text('{aspect_ratio}')",
            ]

            ar_btn = find_matching_locator(page, target_aspect_sels, timeout_ms=2500)
            if ar_btn:
                ar_btn.click(force=True)
                page.wait_for_timeout(500)

            page.keyboard.press("Escape")
            page.wait_for_timeout(500)

        except Exception as e:
            logger.warning(f"[{card_label}] Pengaturan aspect ratio notice: {e}")

    browser_init_ms = round((time.perf_counter() - t_init_start) * 1000, 2)

    # Snapshot awal elemen <img> sebelum upload / prompt untuk mencegah false claim
    blacklisted_ref_srcs: set[str] = set()
    try:
        blacklisted_ref_srcs = set(page.evaluate("""() => {
            return Array.from(document.querySelectorAll('img'))
                .map(i => i.currentSrc || i.src || '')
                .filter(Boolean);
        }"""))
    except Exception:
        pass

    # 6. Upload Reference Images (Optimized JPEG 1024px quality 93)
    t_upload_start = time.perf_counter()
    if ref_paths:
        valid_paths = [
            p for p in ref_paths
            if os.path.exists(p) and os.path.getsize(p) > 2048 and "mock_" not in os.path.basename(p)
        ][:4]

        if valid_paths:
            # Optimasi anchor image ke JPEG 1024px quality 93 (reduksi ~88% ukuran transfer)
            optimized_paths = [get_optimized_anchor_path(p) for p in valid_paths]
            logger.info(
                f"[{card_label}] Mengunggah {len(optimized_paths)} anchor gambar (JPEG Q93 cache) ke Flow: "
                f"{[os.path.basename(p) for p in optimized_paths]}"
            )

            uploaded = False
            try:
                add_btn = find_matching_locator(page, selectors.get("add_media_button", [
                    ".add-menu-trigger",
                    "button[aria-label*='Tambahkan bahan' i]",
                    "button:has-text('add')",
                ]), timeout_ms=2000)

                if add_btn:
                    add_btn.click()
                    page.wait_for_timeout(800)
                    upload_btn = find_matching_locator(page, selectors.get("upload_media_menu_item", [
                        "button:has-text('Upload media')",
                        "[role='menuitem']:has-text('Upload media')",
                        "button:has-text('Upload')",
                    ]), timeout_ms=2000)

                    if upload_btn:
                        with page.expect_file_chooser(timeout=7000) as fc_info:
                            upload_btn.click()
                        file_chooser = fc_info.value
                        file_chooser.set_files(optimized_paths)
                        page.wait_for_timeout(2000)

                        # Modal persetujuan hak cipta gambar ("Saya setuju")
                        agree_btn = find_matching_locator(page, [
                            "button:has-text('Saya setuju')",
                            "button:has-text('Setuju')",
                            "button:has-text('I agree')",
                            "button:has-text('Agree')",
                        ], timeout_ms=3000)
                        if agree_btn:
                            logger.info(f"[{card_label}] Modal persetujuan hak cipta gambar ('Saya setuju') terdeteksi, mengklik...")
                            agree_btn.click(force=True)
                            page.wait_for_timeout(1000)

                        # Klik 'Tambahkan ke perintah'
                        add_to_prompt = find_matching_locator(page, selectors.get("add_to_prompt_button", [
                            "button:has-text('Tambahkan ke perintah')",
                            "button:has-text('Add to prompt')",
                        ]), timeout_ms=3000)
                        if add_to_prompt:
                            add_to_prompt.click()
                            page.wait_for_timeout(1000)
                        uploaded = True

                if not uploaded:
                    ref_input_loc = find_matching_locator(page, selectors.get("reference_image_input", []), timeout_ms=2000)
                    if ref_input_loc:
                        ref_input_loc.set_input_files(optimized_paths)
                        page.wait_for_timeout(1500)
                        uploaded = True

                # Karantina URL elemen media referensi yang baru terpasang di DOM
                try:
                    current_imgs = set(page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('img'))
                            .map(i => i.currentSrc || i.src || '')
                            .filter(Boolean);
                    }"""))
                    blacklisted_ref_srcs.update(current_imgs)
                except Exception:
                    pass

            except Exception as ue:
                logger.warning(f"Upload reference exception: {ue}")

    upload_ms = round((time.perf_counter() - t_upload_start) * 1000, 2)

    # 7. Masukkan Prompt
    try:
        if page.locator(".cdk-overlay-backdrop").is_visible(timeout=400):
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
    except Exception:
        pass

    prompt_loc = find_matching_locator(page, selectors.get("prompt_input", []), timeout_ms=10000)
    if not prompt_loc:
        raise RuntimeError(f"[{card_label}] Input prompt Google Flow tidak ditemukan.")

    prompt_loc.scroll_into_view_if_needed()
    prompt_loc.click(force=True)
    page.wait_for_timeout(200)

    # Bersihkan prompt: normalisasi whitespace & hilangkan newline mentah
    clean_prompt = " ".join(prompt.split())

    # Bersihkan teks prompt input
    try:
        page.evaluate("""(el) => {
            el.focus();
            const sel = window.getSelection();
            const range = document.createRange();
            range.selectNodeContents(el);
            sel.removeAllRanges();
            sel.addRange(range);
        }""", prompt_loc.element_handle())
        page.keyboard.press("Backspace")
        page.wait_for_timeout(100)
    except Exception:
        pass

    # Masukkan prompt ke ProseMirror
    exec_ok = False
    try:
        exec_ok = page.evaluate("""(data) => {
            const el = data.el;
            const text = data.text;
            el.focus();
            const sel = window.getSelection();
            const range = document.createRange();
            range.selectNodeContents(el);
            sel.removeAllRanges();
            sel.addRange(range);
            const ok = document.execCommand('insertText', false, text);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return ok && (el.innerText || '').trim().length > 0;
        }""", {"el": prompt_loc.element_handle(), "text": clean_prompt})
    except Exception:
        pass

    val = (prompt_loc.inner_text() or "").strip()
    if not val:
        prompt_loc.press_sequentially(clean_prompt, delay=random.randint(4, 10))

    try:
        prompt_loc.focus()
        page.keyboard.press("Space")
        page.keyboard.press("Backspace")
        page.evaluate("""(el) => {
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""", prompt_loc.element_handle())
    except Exception:
        pass
    page.wait_for_timeout(600)

    # 8. Klik Generate
    gen_loc = find_matching_locator(page, selectors.get("generate_button", []), timeout_ms=5000)
    if gen_loc:
        try:
            if gen_loc.is_disabled():
                prompt_loc.focus()
                page.keyboard.press("Space")
                page.keyboard.press("Backspace")
                page.wait_for_timeout(600)
        except Exception:
            pass
        gen_loc.click()
        logger.info(f"[{card_label}] Tombol Generate berhasil diklik. Menunggu hasil gambar final...")

    page.wait_for_timeout(2000)

    # 10. Polling dan tangkap hasil gambar final (Timeout 90s)
    t_gen_start = time.perf_counter()
    start_wait = time.time()
    result_bytes: bytes | None = None

    while time.time() - start_wait < 90:
        elapsed = time.time() - start_wait

        page_text = page.locator("body").inner_text()
        for rl_msg in selectors.get("rate_limit_indicators", []):
            if rl_msg.lower() in page_text.lower():
                raise TimeoutError(f"Rate limit terdeteksi setelah generate: {rl_msg}")

        # Guard awal: 4.0s (diturunkan dari 8.0s untuk memangkas latency)
        if elapsed < 4.0:
            logger.info(f"[{card_label}] Menunggu inisiasi render Google Flow [{elapsed:.1f}s/90s]...")
            page.wait_for_timeout(1000)
            continue

        eval_result = page.evaluate("""(data) => {
            const blacklistedSet = new Set((data && data.blacklistedSrcs) || []);

            const loadingSelectors = [
                "[role='progressbar']", "progress", ".spinner", ".loading",
                "[aria-busy='true']", "mat-progress-spinner", "mat-progress-bar",
                ".circular-progress", "svg.animate-spin"
            ];
            for (const sel of loadingSelectors) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    if (rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden') {
                        return { is_loading: true, reason: `Spinner aktif (${sel})`, candidates: [] };
                    }
                }
            }

            const images = Array.from(document.querySelectorAll('img'));
            const candidates = [];

            for (let i = 0; i < images.length; i++) {
                const img = images[i];
                const src = img.currentSrc || img.src || '';
                if (!src || blacklistedSet.has(src) || img.complete !== true) continue;

                let inPrompt = false;
                let cur = img;
                for (let d = 0; d < 5 && cur; d++) {
                    const cls = (cur.className || '').toString().toLowerCase();
                    if (cls.includes('prompt') || cls.includes('media-chip') || cls.includes('reference') || cls.includes('cdk-overlay')) {
                        inPrompt = true; break;
                    }
                    cur = cur.parentElement;
                }
                if (inPrompt) continue;

                const rect = img.getBoundingClientRect();
                const style = window.getComputedStyle(img);
                if (rect.width <= 30 || rect.height <= 30 || style.display === 'none' || style.visibility === 'hidden') continue;

                const nw = img.naturalWidth || 0;
                const nh = img.naturalHeight || 0;
                if (nw < 300 || nh < 300) continue;

                candidates.push({
                    src: src,
                    naturalWidth: nw,
                    naturalHeight: nh,
                    isNew: true
                });
            }

            candidates.sort((a, b) => (b.naturalWidth * b.naturalHeight) - (a.naturalWidth * a.naturalHeight));
            return { is_loading: false, reason: null, candidates: candidates };
        }""", {"blacklistedSrcs": list(blacklisted_ref_srcs)})

        is_loading = eval_result.get("is_loading", False)
        loading_reason = eval_result.get("reason")
        candidates = eval_result.get("candidates", [])

        if is_loading:
            logger.info(f"Menunggu render selesai ({loading_reason}) [{elapsed:.1f}s/90s]...")
            page.wait_for_timeout(1500)
            continue

        if not candidates:
            page.wait_for_timeout(1500)
            continue

        candidate_accepted = False
        for cand in candidates:
            cand_src = cand["src"]
            nw = cand["naturalWidth"]
            nh = cand["naturalHeight"]

            logger.info(f"Mengevaluasi kandidat <img> ({nw}x{nh}). Mengunduh dari src...")
            t_dl_start = time.perf_counter()
            raw_bytes = download_image_from_src(page, cand_src)
            download_ms = round((time.perf_counter() - t_dl_start) * 1000, 2)

            if not raw_bytes or len(raw_bytes) <= 50_000:
                continue

            try:
                with Image.open(io.BytesIO(raw_bytes)) as pil_img:
                    pil_w, pil_h = pil_img.size
                valid_pil = (pil_w >= 500 and pil_h >= 500) or (min(pil_w, pil_h) >= 400 and max(pil_w, pil_h) >= 700)
                if not valid_pil:
                    continue

                # Cek clone terhadap referensi
                is_clone = False
                if ref_paths:
                    for rp in ref_paths:
                        if os.path.exists(rp) and os.path.getsize(rp) > 1024:
                            with open(rp, "rb") as rf:
                                if raw_bytes == rf.read():
                                    is_clone = True
                                    break
                if is_clone:
                    continue

            except Exception:
                continue

            file_size_kb = len(raw_bytes) / 1024.0
            logger.info(
                f"[DIAGNOSTIK] Gambar resolusi penuh berhasil ditangkap: "
                f"PIL={pil_w}x{pil_h}, Ukuran={file_size_kb:.2f} KB ({len(raw_bytes)} bytes)"
            )
            result_bytes = raw_bytes
            candidate_accepted = True
            break

        if candidate_accepted and result_bytes:
            break

        page.wait_for_timeout(1500)

    if not result_bytes:
        raise RuntimeError("Gagal menangkap gambar hasil dari Google Flow dalam 90 detik.")

    generate_wait_ms = round((time.perf_counter() - t_gen_start - (download_ms / 1000.0)) * 1000, 2)
    total_ms = round((time.perf_counter() - t_start) * 1000, 2)

    logger.info(
        f"[FlowTimer] [{job_id}] [{card_label}] "
        f"browser_init_ms={browser_init_ms:.0f} "
        f"upload_ms={upload_ms:.0f} "
        f"generate_wait_ms={generate_wait_ms:.0f} "
        f"download_ms={download_ms:.0f} "
        f"total_ms={total_ms:.0f}"
    )

    return result_bytes


def worker_thread_loop(worker_slot_id: int):
    """Independent worker thread loop managing warm Chromium context with idle auto-close and atomic claims."""
    logger.info(f"=== Worker Slot #{worker_slot_id} aktif ===")
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        warm_context: BrowserContext | None = None
        warm_page: Page | None = None
        warm_account: sqlite3.Row | None = None
        warm_lock: AccountProfileLock | None = None
        warm_batch_count: int = 0
        last_activity_time: float = time.time()

        def close_warm_context():
            nonlocal warm_context, warm_page, warm_account, warm_lock, warm_batch_count
            if warm_context:
                try:
                    warm_context.close()
                except Exception:
                    pass
                warm_context = None
                warm_page = None

            if warm_account and warm_lock:
                conn = get_db_connection()
                try:
                    mark_account_status(conn, warm_account["id"], "active")
                finally:
                    conn.close()
                warm_lock.release()
                logger.info(f"[WorkerSlot-{worker_slot_id}] Profil Akun #{warm_account['id']} ditutup & lock dilepas.")

            warm_account = None
            warm_lock = None
            warm_batch_count = 0

        while running:
            # 1. Resource Guard: Jika RAM < 1800MB dan slot > 0, throttle slot sekunder
            if worker_slot_id >= get_effective_concurrency():
                if warm_context:
                    close_warm_context()
                time.sleep(3.0)
                continue

            conn = get_db_connection()
            try:
                settings = get_flow_settings(conn)
            finally:
                conn.close()

            worker_enabled = settings.get("worker_enabled", "true").lower() == "true"
            if not worker_enabled:
                if warm_context:
                    close_warm_context()
                time.sleep(5.0)
                continue

            socks5_proxy = (settings.get("socks5_proxy") or DEFAULT_SOCKS5_URL).strip()
            max_batch_size = 4
            cooldown_minutes = int(settings.get("cooldown_minutes", 15))

            # SOCKS5 Pre-Flight Check (with 5s in-memory TTL cache)
            proxy_health = get_cached_socks5_health(socks5_proxy, ttl_seconds=5.0)
            if not proxy_health["healthy"]:
                time.sleep(3.5)
                continue

            # 2. Case A: Worker sudah memiliki browser warm yang aktif
            if warm_context and warm_account and warm_lock:
                idle_duration = time.time() - last_activity_time

                conn = get_db_connection()
                try:
                    subsequent_job = claim_job_for_specific_account(conn, warm_account["id"])
                    other_queued = has_queued_jobs_for_other_accounts(conn, warm_account["id"])
                finally:
                    conn.close()

                if subsequent_job and warm_batch_count < max_batch_size:
                    # Jalankan job berikutnya dalam sesi warm
                    job_id = str(subsequent_job["id"])
                    logger.info(
                        f"[WorkerSlot-{worker_slot_id}] Menjalankan Job {job_id} dalam sesi warm "
                        f"Akun #{warm_account['id']} (Batch: {warm_batch_count + 1}/{max_batch_size})..."
                    )
                    selectors = load_selectors()
                    try:
                        raw_image = execute_flow_generation(
                            warm_page, selectors, subsequent_job, warm_account, is_warm=True
                        )
                        img_filename = f"{job_id}.png"
                        img_disk_path = MEDIA_DIR / img_filename
                        image = Image.open(io.BytesIO(raw_image)).convert("RGB")
                        image.save(img_disk_path, format="PNG", optimize=True)
                        image_url = f"/media/images/{img_filename}"

                        conn = get_db_connection()
                        try:
                            update_job_status(
                                conn, job_id, "completed", output_filename=img_filename, image_url=image_url
                            )
                            record_account_success(conn, warm_account["id"])
                        finally:
                            conn.close()

                        warm_batch_count += 1
                        last_activity_time = time.time()
                        logger.info(f"[WorkerSlot-{worker_slot_id}] Job {job_id} SUKSES! ({image_url})")
                        time.sleep(1.0)
                        continue

                    except Exception as e:
                        logger.error(f"[WorkerSlot-{worker_slot_id}] Error pada warm job {job_id}: {e}")
                        conn = get_db_connection()
                        try:
                            update_job_status(conn, job_id, "failed", error_message=str(e))
                            record_account_failure(conn, warm_account["id"], str(e), cooldown_minutes=cooldown_minutes)
                        finally:
                            conn.close()
                        close_warm_context()
                        time.sleep(2.0)
                        continue

                # Tidak ada job langsung untuk akun ini: cek idle timeout 75s atau antrean akun lain
                if idle_duration >= 75.0 or (other_queued and idle_duration >= 4.0) or warm_batch_count >= max_batch_size:
                    logger.info(
                        f"[WorkerSlot-{worker_slot_id}] Menutup sesi warm Akun #{warm_account['id']} "
                        f"(idle={idle_duration:.1f}s, batch={warm_batch_count}, other_queued={other_queued}). RAM dibebaskan."
                    )
                    close_warm_context()
                    continue

                time.sleep(1.0)
                continue

            # 3. Case B: Worker tidak memiliki browser warm (klaim job baru + akun aktif)
            conn = get_db_connection()
            try:
                job, account, profile_lock = claim_next_job_and_lock_account(conn)
            finally:
                conn.close()

            if not job or not account or not profile_lock:
                time.sleep(2.0)
                continue

            account_id = account["id"]
            job_id = str(job["id"])
            profile_dir = account["profile_dir"]
            os.makedirs(profile_dir, exist_ok=True)

            logger.info(
                f"[WorkerSlot-{worker_slot_id}] Menyiapkan browser baru untuk Akun #{account_id} "
                f"({account['label']}) -> Job {job_id}..."
            )

            # Stagger launch minimal 4.0s
            stagger_browser_launch()

            chrome_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--window-size=1920,1080",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ]
            if socks5_proxy:
                chrome_args.append(f"--proxy-server={socks5_proxy}")

            os.environ["DISPLAY"] = ":99"
            selectors = load_selectors()

            try:
                context = pw.chromium.launch_persistent_context(
                    user_data_dir=profile_dir,
                    executable_path="/usr/bin/google-chrome-stable",
                    headless=False,
                    args=chrome_args,
                    viewport={"width": 1920, "height": 1080},
                    accept_downloads=True,
                )
                page = context.pages[0] if context.pages else context.new_page()

                raw_image = execute_flow_generation(page, selectors, job, account, is_warm=False)

                img_filename = f"{job_id}.png"
                img_disk_path = MEDIA_DIR / img_filename
                image = Image.open(io.BytesIO(raw_image)).convert("RGB")
                image.save(img_disk_path, format="PNG", optimize=True)
                image_url = f"/media/images/{img_filename}"

                conn = get_db_connection()
                try:
                    update_job_status(
                        conn, job_id, "completed", output_filename=img_filename, image_url=image_url
                    )
                    record_account_success(conn, account_id)
                finally:
                    conn.close()

                # Simpan context sebagai warm session
                warm_context = context
                warm_page = page
                warm_account = account
                warm_lock = profile_lock
                warm_batch_count = 1
                last_activity_time = time.time()
                logger.info(
                    f"[WorkerSlot-{worker_slot_id}] Job {job_id} SUKSES! Browser tetap warm untuk job berikutnya."
                )

            except Exception as e:
                err_str = str(e)
                logger.error(f"[WorkerSlot-{worker_slot_id}] Gagal memproses Job {job_id} pada Akun #{account_id}: {err_str}")
                debug_fn = f"{job_id}_err.png"
                debug_path = DEBUG_DIR / debug_fn
                try:
                    if 'page' in locals() and page:
                        page.screenshot(path=str(debug_path), full_page=True)
                        debug_url = f"/media/debug/{debug_fn}"
                    else:
                        debug_url = None
                except Exception:
                    debug_url = None

                conn = get_db_connection()
                try:
                    if "SOCKS5_PROXY_OFFLINE" in err_str:
                        update_job_status(conn, job_id, "failed", error_message="SOCKS5_PROXY_OFFLINE")
                    else:
                        update_job_status(
                            conn, job_id, "failed", error_message=err_str, debug_screenshot_url=debug_url
                        )
                        record_account_failure(conn, account_id, err_str, cooldown_minutes=cooldown_minutes)
                finally:
                    conn.close()

                if 'context' in locals() and context:
                    try:
                        context.close()
                    except Exception:
                        pass
                profile_lock.release()
                warm_context = None
                warm_page = None
                warm_account = None
                warm_lock = None
                warm_batch_count = 0
                time.sleep(3.0)

        # On shutdown
        close_warm_context()
        logger.info(f"=== Worker Slot #{worker_slot_id} berhenti ===")


def main():
    logger.info("=== Flow Image Worker Pool dimulai ===")
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    # Single Master Service Guarantee
    lock_file = open(LOCK_FILE_PATH, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.error(f"Instance worker lain sedang berjalan (lock {LOCK_FILE_PATH} aktif). Keluar.")
        sys.exit(0)

    try:
        startup_conn = get_db_connection()
        try:
            recover_all_busy_accounts_on_startup(startup_conn)
        finally:
            startup_conn.close()

        num_workers = get_effective_concurrency()
        logger.info(f"[WorkerPool] Memulai {num_workers} thread worker konkuren...")

        threads: list[threading.Thread] = []
        for slot in range(num_workers):
            t = threading.Thread(target=worker_thread_loop, args=(slot,), name=f"FlowWorkerSlot-{slot}")
            t.daemon = True
            t.start()
            threads.append(t)

        while running:
            # Maintenance berkala setiap 10 detik
            time.sleep(10)
            conn = get_db_connection()
            try:
                reset_daily_counts_if_needed(conn)
                auto_recover_cooldown_accounts(conn)
                cleanup_stale_busy_accounts(conn, stale_threshold_minutes=6)
            finally:
                conn.close()

        for t in threads:
            t.join(timeout=10.0)

    finally:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
        except Exception:
            pass
        logger.info("=== Flow Image Worker Pool berhenti ===")


if __name__ == "__main__":
    main()
