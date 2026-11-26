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
import uuid
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

# Thread-safe per-job failed account tracking for multi-account failover
_FAILED_ACCOUNTS_LOCK = threading.Lock()
_FAILED_ACCOUNTS_BY_JOB: dict[str, set[int]] = {}
_FAILED_ACCOUNT_ORDER_BY_JOB: dict[str, list[int]] = {}


def record_failed_account_for_job(job_id: str, account_id: int) -> list[int]:
    """Record an account_id that failed for job_id and return ordered tried account IDs."""
    key = str(job_id)
    with _FAILED_ACCOUNTS_LOCK:
        failed_set = _FAILED_ACCOUNTS_BY_JOB.setdefault(key, set())
        order_list = _FAILED_ACCOUNT_ORDER_BY_JOB.setdefault(key, [])
        if account_id not in failed_set:
            failed_set.add(account_id)
            order_list.append(account_id)
        return list(order_list)


def get_failed_accounts_for_job(job_id: str) -> set[int]:
    """Return a snapshot copy of account IDs that already failed for job_id."""
    key = str(job_id)
    with _FAILED_ACCOUNTS_LOCK:
        return set(_FAILED_ACCOUNTS_BY_JOB.get(key, ()))


def clear_failed_accounts_for_job(job_id: str) -> None:
    """Remove per-job failover tracking entry once job reaches terminal state."""
    key = str(job_id)
    with _FAILED_ACCOUNTS_LOCK:
        _FAILED_ACCOUNTS_BY_JOB.pop(key, None)
        _FAILED_ACCOUNT_ORDER_BY_JOB.pop(key, None)

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


def touch_account_busy_timestamp(conn: sqlite3.Connection, account_id: int) -> None:
    """Refresh flow_accounts.updated_at between Phase 1 and Phase 2 to prevent stale-busy reclamation."""
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            conn.execute(
                """
                UPDATE flow_accounts
                SET updated_at = ?
                WHERE id = ? AND status = 'busy'
                """,
                (now_iso, account_id),
            )
    except Exception:
        pass


def _finalize_unrecoverable_queued_job(
    conn: sqlite3.Connection,
    job: sqlite3.Row,
    failed_accounts: set[int],
) -> None:
    """Mark a queued retry job as failed if no viable untried active/busy accounts remain."""
    job_id = str(job["id"])
    pref_id = job["preferred_account_id"] if "preferred_account_id" in job.keys() else None
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM flow_accounts WHERE status IN ('active', 'busy')")
    viable_ids = [
        r["id"] for r in cursor.fetchall()
        if r["id"] not in failed_accounts and (not pref_id or r["id"] == pref_id)
    ]
    if viable_ids:
        return

    with _FAILED_ACCOUNTS_LOCK:
        order_list = list(_FAILED_ACCOUNT_ORDER_BY_JOB.get(job_id, sorted(failed_accounts)))
    tried_str = ", ".join(f"Akun #{aid}" for aid in order_list) if order_list else "tidak ada akun aktif"
    prev_err = (job["error_message"] if "error_message" in job.keys() else None) or "Tidak ada akun Google Flow aktif yang tersisa."
    final_err = f"Gagal di semua akun Google Flow yang dicoba ({tried_str}): {prev_err}"
    update_job_status(conn, job_id, "failed", error_message=final_err)
    clear_failed_accounts_for_job(job_id)
    logger.error(f"[FailoverExhausted] Job {job_id} tidak memiliki sisa akun aktif; ditandai failed ({tried_str}).")


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
        LIMIT 20
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

    for job in jobs:
        job_id = str(job["id"])
        failed_accounts = get_failed_accounts_for_job(job_id)
        pref_id = job["preferred_account_id"] if "preferred_account_id" in job.keys() else None
        candidate_accounts = [
            a for a in active_accounts
            if a["id"] not in failed_accounts and (not pref_id or a["id"] == pref_id)
        ]

        if not candidate_accounts:
            retry_count = int(job["retry_count"] or 0) if "retry_count" in job.keys() else 0
            if failed_accounts or retry_count > 0:
                _finalize_unrecoverable_queued_job(conn, job, failed_accounts)
            continue

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


def claim_job_for_specific_account(
    conn: sqlite3.Connection,
    account_id: int,
    character_id: str | None = None,
) -> sqlite3.Row | None:
    """Atomically claim the next queued job eligible for a currently held warm account.
    Enforces strict character isolation and excludes jobs that already failed on account_id.
    """
    cursor = conn.cursor()
    with conn:
        if character_id:
            cursor.execute(
                """
                SELECT * FROM flow_image_jobs
                WHERE status = 'queued'
                  AND (preferred_account_id IS NULL OR preferred_account_id = ?)
                  AND character_id = ?
                ORDER BY created_at ASC
                LIMIT 10
                """,
                (account_id, character_id),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM flow_image_jobs
                WHERE status = 'queued'
                  AND (preferred_account_id IS NULL OR preferred_account_id = ?)
                ORDER BY created_at ASC
                LIMIT 10
                """,
                (account_id,),
            )
        jobs = cursor.fetchall()
        for job in jobs:
            job_id = str(job["id"])
            if account_id in get_failed_accounts_for_job(job_id):
                continue

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
                logger.info(
                    f"[WarmClaim] Job {job['id']} (char={job['character_id']}) claimed by warm Akun #{account_id}."
                )
                return job
    return None


def has_queued_jobs_for_other_accounts(
    conn: sqlite3.Connection,
    current_account_id: int,
    current_character_id: str | None = None,
) -> bool:
    """Check if queued jobs exist that could run on other accounts, for other characters, or failed on current account."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, preferred_account_id, character_id FROM flow_image_jobs
        WHERE status = 'queued'
        LIMIT 20
        """
    )
    for row in cursor.fetchall():
        job_id = str(row["id"])
        pref_id = row["preferred_account_id"]
        job_char = str(row["character_id"]) if row["character_id"] else None
        if pref_id is not None and pref_id != current_account_id:
            return True
        if current_character_id and job_char != current_character_id:
            return True
        if current_account_id in get_failed_accounts_for_job(job_id):
            return True
        if not current_character_id and pref_id is None:
            return True
    return False


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


def _resolve_image_disk_path(image_url: str | None) -> Path | None:
    """Resolve /media/images/<file> or local filesystem path to an existing file on disk."""
    if not image_url:
        return None
    clean = image_url.split("?")[0].strip()
    if clean.startswith("/media/images/"):
        rel_name = Path(clean.replace("/media/images/", "", 1)).name
        cand = MEDIA_DIR / rel_name
        if cand.exists() and cand.is_file():
            return cand
    p = Path(clean)
    if p.exists() and p.is_file():
        return p
    return None


def _read_local_image_dimensions(image_url: str | None) -> tuple[int, int] | None:
    """Inspect saved output image dimensions (width, height) via Pillow."""
    disk_path = _resolve_image_disk_path(image_url)
    if not disk_path:
        return None
    try:
        with Image.open(disk_path) as im:
            return im.size
    except Exception:
        return None


def save_flow_image_jpeg(raw_image: bytes, dest_path: Path, quality: int = 95) -> tuple[int, int]:
    """Convert raw image bytes to RGB and save as high-quality JPEG (Q95, optimize=True)."""
    with Image.open(io.BytesIO(raw_image)) as opened:
        rgb_img = opened.convert("RGB")
        dims = rgb_img.size
        rgb_img.save(dest_path, format="JPEG", quality=quality, optimize=True)
    return dims


def auto_attach_job_result(conn: sqlite3.Connection, job_id: str, image_url: str):
    """Atomically auto-attach completed Google Flow image result to character, state, or scene shot in SQLite."""
    try:
        # Introspect columns to support both full production schema and isolated test schemas
        cols = [c[1] for c in conn.execute("PRAGMA table_info(flow_image_jobs)").fetchall()]
        has_scene_id = "scene_id" in cols
        has_shot_id = "shot_id" in cols
        select_clause = "character_id, asset_slot, target_type, state_id, prompt, reference_image_paths, aspect_ratio"
        if has_scene_id:
            select_clause += ", scene_id"
        if has_shot_id:
            select_clause += ", shot_id"

        row = conn.execute(
            f"SELECT {select_clause} FROM flow_image_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()

        if not row:
            return

        dims = _read_local_image_dimensions(image_url)
        actual_w, actual_h = dims if dims else (None, None)
        is_2k_flag = bool(actual_w and actual_h and max(actual_w, actual_h) >= 1920)
        now_iso = datetime.now(timezone.utc).isoformat()

        char_id = str(row[0]) if row[0] else None
        asset_slot = row[1]
        target_type = row[2]
        state_id = str(row[3]) if row[3] else None
        prompt = row[4]
        ref_paths_raw = row[5]
        ref_paths = json.loads(ref_paths_raw) if (ref_paths_raw and isinstance(ref_paths_raw, str)) else (ref_paths_raw or [])
        aspect_ratio = row[6] or "16:9"
        idx = 7
        scene_id = str(row[idx]) if has_scene_id and len(row) > idx and row[idx] else None
        if has_scene_id:
            idx += 1
        direct_shot_id = str(row[idx]) if has_shot_id and len(row) > idx and row[idx] else None

        if target_type == "state" and state_id:
            cur = conn.execute(
                "UPDATE character_states SET image_url = ? WHERE id = ?",
                (image_url, state_id),
            )
            parent_char_id = char_id
            if not parent_char_id:
                try:
                    st_row = conn.execute(
                        "SELECT character_id FROM character_states WHERE id = ?",
                        (state_id,),
                    ).fetchone()
                    if st_row and st_row[0]:
                        parent_char_id = str(st_row[0])
                except Exception:
                    parent_char_id = None

            if parent_char_id:
                try:
                    char_row = conn.execute(
                        "SELECT sheet_metadata, dna_seed FROM characters WHERE id = ?",
                        (parent_char_id,),
                    ).fetchone()
                    if char_row:
                        existing_meta = {}
                        if char_row[0]:
                            try:
                                existing_meta = json.loads(char_row[0]) if isinstance(char_row[0], str) else dict(char_row[0])
                            except Exception:
                                existing_meta = {}
                        existing_meta[f"state_{state_id}"] = {
                            "image_url": image_url,
                            "prompt": prompt,
                            "anchors_used": ref_paths,
                            "provider": "google_flow",
                            "seed": char_row[1],
                            "aspect_ratio": aspect_ratio,
                            "width": actual_w,
                            "height": actual_h,
                            "resolution_width": actual_w,
                            "resolution_height": actual_h,
                            "is_2k": is_2k_flag,
                            "rendered_at": now_iso,
                            "status": "completed",
                        }
                        conn.execute(
                            "UPDATE characters SET sheet_metadata = ? WHERE id = ?",
                            (json.dumps(existing_meta), parent_char_id),
                        )
                except Exception as meta_exc:
                    logger.warning(f"[AutoAttach] State sheet_metadata merge warning for state={state_id}: {meta_exc}")

            if cur.rowcount > 0:
                logger.info(f"[AutoAttach] Attached {job_id} -> character_state={state_id} (is_2k={is_2k_flag})")
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
                "width": actual_w,
                "height": actual_h,
                "resolution_width": actual_w,
                "resolution_height": actual_h,
                "is_2k": is_2k_flag,
                "rendered_at": now_iso,
                "status": "completed",
            }

            cur = conn.execute(
                f"UPDATE characters SET {target_col} = ?, sheet_metadata = ? WHERE id = ?",
                (image_url, json.dumps(existing_meta), char_id),
            )
            if cur.rowcount > 0:
                logger.info(f"[AutoAttach] Attached {job_id} -> character={char_id} slot={slot_key} (col={target_col}, is_2k={is_2k_flag})")
            else:
                logger.warning(f"[AutoAttach] Zero rows updated for character {char_id}")
            return

        if direct_shot_id:
            shot_row = conn.execute(
                "SELECT id, fg_bg_layers FROM shots WHERE id = ?",
                (direct_shot_id,),
            ).fetchone()
            if shot_row:
                s_id = str(shot_row[0])
                raw_layers = shot_row[1]
                existing_layers = {}
                if raw_layers:
                    try:
                        existing_layers = json.loads(raw_layers) if isinstance(raw_layers, str) else dict(raw_layers)
                    except Exception:
                        existing_layers = {}
                existing_layers["preview_url"] = image_url
                existing_layers["preview_provider"] = "google_flow"
                existing_layers["job_id"] = job_id
                existing_layers["preview_width"] = actual_w
                existing_layers["preview_height"] = actual_h
                existing_layers["is_2k"] = is_2k_flag
                existing_layers["updated_at"] = now_iso
                conn.execute(
                    "UPDATE shots SET fg_bg_layers = ? WHERE id = ?",
                    (json.dumps(existing_layers), s_id),
                )
                logger.info(f"[AutoAttach] Attached {job_id} -> direct shot={s_id} (is_2k={is_2k_flag})")
                return

        if scene_id:
            shot_row = conn.execute(
                "SELECT id, fg_bg_layers FROM shots WHERE scene_id = ? ORDER BY shot_number ASC LIMIT 1",
                (scene_id,),
            ).fetchone()

            if shot_row:
                shot_id = str(shot_row[0])
                raw_layers = shot_row[1]
                existing_layers = {}
                if raw_layers:
                    try:
                        existing_layers = json.loads(raw_layers) if isinstance(raw_layers, str) else dict(raw_layers)
                    except Exception:
                        existing_layers = {}

                # Non-destructive JSON merge: retain old keys, only add/update preview fields
                existing_layers["preview_url"] = image_url
                existing_layers["preview_provider"] = "google_flow"
                existing_layers["job_id"] = job_id
                existing_layers["preview_width"] = actual_w
                existing_layers["preview_height"] = actual_h
                existing_layers["is_2k"] = is_2k_flag
                existing_layers["updated_at"] = now_iso

                cur = conn.execute(
                    "UPDATE shots SET fg_bg_layers = ? WHERE id = ?",
                    (json.dumps(existing_layers), shot_id),
                )
                if cur.rowcount > 0:
                    logger.info(f"[AutoAttach] Attached {job_id} -> scene={scene_id} shot={shot_id} (is_2k={is_2k_flag})")
                else:
                    logger.warning(f"[AutoAttach] Zero rows updated for shot {shot_id} in scene {scene_id}")
            else:
                # If scene has no shots yet, create shot #1
                s_row = conn.execute("SELECT duration_target FROM scenes WHERE id = ?", (scene_id,)).fetchone()
                dur = float(s_row[0]) if (s_row and s_row[0]) else 5.0
                new_shot_id = str(uuid.uuid4())
                layers = {
                    "preview_url": image_url,
                    "preview_provider": "google_flow",
                    "job_id": job_id,
                    "preview_width": actual_w,
                    "preview_height": actual_h,
                    "is_2k": is_2k_flag,
                    "updated_at": now_iso,
                }
                conn.execute(
                    """
                    INSERT INTO shots (
                        id, scene_id, shot_number, duration_seconds, camera_code, lens_code,
                        comp_code, light_code, act_code, speed_code, fg_bg_layers, status, created_at
                    ) VALUES (?, ?, 1, ?, '#Cam 01', '#Lens 01', '#Comp 01', '#Light 01', '#Act 01', '#Speed 01', ?, 'PLANNED', ?)
                    """,
                    (new_shot_id, scene_id, dur, json.dumps(layers), now_iso),
                )
                logger.info(f"[AutoAttach] Created shot #1 and attached {job_id} -> scene={scene_id} shot={new_shot_id} (is_2k={is_2k_flag})")
            return
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
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM flow_image_jobs WHERE id = ?", (job_id,))
        curr = cursor.fetchone()
        if curr and curr["status"] == "cancelled":
            logger.info(f"Job {job_id} already marked 'cancelled'. Skipping status update to '{status}'.")
            return

        if status == "completed":
            conn.execute(
                """
                UPDATE flow_image_jobs
                SET status = ?, output_filename = ?, image_url = ?, completed_at = ?
                WHERE id = ? AND status != 'cancelled'
                """,
                (status, output_filename, image_url, now_utc, job_id),
            )
            auto_attach_job_result(conn, job_id, image_url)
        elif status == "failed":
            conn.execute(
                """
                UPDATE flow_image_jobs
                SET status = ?, error_message = ?, debug_screenshot_url = ?, completed_at = ?
                WHERE id = ? AND status != 'cancelled'
                """,
                (status, error_message, debug_screenshot_url, now_utc, job_id),
            )
        elif status == "processing":
            conn.execute(
                """
                UPDATE flow_image_jobs
                SET status = ?, assigned_account_id = ?, started_at = ?
                WHERE id = ? AND status != 'cancelled'
                """,
                (status, assigned_account_id, now_utc, job_id),
            )
        elif status == "queued" and increment_retry:
            conn.execute(
                """
                UPDATE flow_image_jobs
                SET status = 'queued',
                    assigned_account_id = NULL,
                    started_at = NULL,
                    retry_count = retry_count + 1,
                    error_message = ?,
                    debug_screenshot_url = ?
                WHERE id = ? AND status != 'cancelled'
                """,
                (error_message, debug_screenshot_url, job_id),
            )


def record_account_success(conn: sqlite3.Connection, account_id: int):
    now_utc = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            """
            UPDATE flow_accounts
            SET status = 'active',
                daily_count = daily_count + 1,
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
        if row is not None:
            fails = (row["consecutive_failures"] if isinstance(row, sqlite3.Row) else row[0]) + 1
        else:
            fails = 1

        if fails >= 3:
            cooldown_until = (datetime.now(timezone.utc) + timedelta(minutes=cooldown_minutes)).isoformat()
            cursor.execute(
                """
                UPDATE flow_accounts
                SET status = 'cooldown', cooldown_until = ?, consecutive_failures = ?, last_error = ?, last_used_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (cooldown_until, fails, error_msg, now_utc, now_utc, account_id),
            )
            logger.warning(f"Akun #{account_id} mengalami {fails} kegagalan berturut-turut. Cooldown {cooldown_minutes}m.")
        else:
            # Explicitly reset status back to 'active' and advance last_used_at so failed account moves to back of LRU
            cursor.execute(
                """
                UPDATE flow_accounts
                SET status = 'active', consecutive_failures = ?, last_error = ?, last_used_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (fails, error_msg, now_utc, now_utc, account_id),
            )
            logger.info(f"Akun #{account_id} kegagalan {fails}/3 dicatat. Status di-reset ke 'active' (LRU updated).")


def handle_job_failure_and_failover(
    conn: sqlite3.Connection,
    job_id: str,
    account_id: int,
    error_msg: str,
    *,
    is_permission_error: bool = False,
    is_proxy_offline: bool = False,
    debug_screenshot_url: str | None = None,
    cooldown_minutes: int = 15,
) -> str:
    """Update account state and either requeue job for another active Flow account or mark final failed."""
    if is_proxy_offline or "SOCKS5_PROXY_OFFLINE" in error_msg:
        mark_account_status(conn, account_id, "active")
        update_job_status(conn, job_id, "failed", error_message="SOCKS5_PROXY_OFFLINE")
        clear_failed_accounts_for_job(job_id)
        return "failed"

    if is_permission_error:
        mark_account_status(conn, account_id, "need_relogin", last_error=error_msg)
        logger.warning(f"[AuthExpired] Akun #{account_id} butuh relogin -> status diubah ke 'need_relogin'.")
    else:
        record_account_failure(conn, account_id, error_msg, cooldown_minutes=cooldown_minutes)

    tried_accounts = record_failed_account_for_job(job_id, account_id)
    failed_set = set(tried_accounts)

    cursor = conn.cursor()
    cursor.execute(
        "SELECT status, retry_count, max_retries, preferred_account_id FROM flow_image_jobs WHERE id = ?",
        (job_id,),
    )
    job_row = cursor.fetchone()
    if not job_row or job_row["status"] == "cancelled":
        clear_failed_accounts_for_job(job_id)
        return "cancelled"

    current_retry = int(job_row["retry_count"] or 0)
    effective_max_retries = max(int(job_row["max_retries"] or 3), 4)
    pref_id = job_row["preferred_account_id"]

    cursor.execute("SELECT id FROM flow_accounts WHERE status = 'active' ORDER BY id ASC")
    remaining_active_ids = [
        r["id"] for r in cursor.fetchall()
        if r["id"] not in failed_set and (not pref_id or r["id"] == pref_id)
    ]

    if remaining_active_ids and current_retry < effective_max_retries:
        update_job_status(
            conn,
            job_id,
            "queued",
            debug_screenshot_url=debug_screenshot_url,
            error_message=error_msg,
            increment_retry=True,
        )
        logger.warning(
            f"[Failover] Job {job_id} gagal di Akun #{account_id} ({error_msg}) -> "
            f"requeued ke antrean untuk akun Google Flow berikutnya "
            f"(retry {current_retry + 1}/{effective_max_retries}; tried={tried_accounts})"
        )
        return "requeued"

    tried_str = ", ".join(f"Akun #{aid}" for aid in tried_accounts)
    final_err = f"Gagal di semua akun Google Flow yang dicoba ({tried_str}): {error_msg}"
    update_job_status(
        conn,
        job_id,
        "failed",
        error_message=final_err,
        debug_screenshot_url=debug_screenshot_url,
    )
    clear_failed_accounts_for_job(job_id)
    logger.error(f"[FailoverExhausted] Job {job_id} gagal permanen setelah mencoba [{tried_str}]: {error_msg}")
    return "failed"


def find_matching_locator(page: Page, selectors: list[str], timeout_ms: int = 3000):
    """Return first visible locator matching any selector, polling up to timeout_ms.

    Playwright's Locator.is_visible() ignores timeout and checks instantaneously;
    we poll until deadline so dynamic UI controls (settings trigger, upload modal,
    add-to-prompt button, prompt input) are reliably awaited.
    """
    if not selectors:
        return None
    deadline = time.monotonic() + max(0.0, timeout_ms / 1000.0)
    while True:
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible():
                    return loc
            except Exception:
                continue
        if time.monotonic() >= deadline:
            return None
        page.wait_for_timeout(150)


def _is_perceptual_clone_of_refs(raw_bytes: bytes, candidate_paths: list[str]) -> bool:
    """Detect exact OR re-encoded/resized clones of uploaded anchor images."""
    if not raw_bytes or not candidate_paths:
        return False
    try:
        with Image.open(io.BytesIO(raw_bytes)) as cand_im:
            cand_thumb = cand_im.convert("RGB").resize((64, 64), Image.Resampling.BILINEAR)
    except Exception:
        return False

    for rp in candidate_paths:
        if not rp or not os.path.exists(rp) or os.path.getsize(rp) <= 1024:
            continue
        try:
            with open(rp, "rb") as rf:
                ref_bytes = rf.read()
            if raw_bytes == ref_bytes:
                return True
            with Image.open(io.BytesIO(ref_bytes)) as ref_im:
                ref_thumb = ref_im.convert("RGB").resize((64, 64), Image.Resampling.BILINEAR)
            diff = ImageChops.difference(cand_thumb, ref_thumb)
            mean_diff = sum(ImageStat.Stat(diff).mean) / 3.0
            if mean_diff < 4.5:
                return True
        except Exception:
            continue
    return False


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


def normalize_target_resolution(value: str | None) -> str:
    """Normalize target resolution setting ('1k', '2k', or '4k'), defaulting to '2k'."""
    norm = (value or "2k").strip().lower()
    return norm if norm in ("1k", "2k", "4k") else "2k"


def _dismiss_cdk_overlays(page: Page) -> None:
    """Dismiss any open Angular Material overlay panes so warm sessions remain clean."""
    for _ in range(2):
        try:
            pane = page.locator(".cdk-overlay-pane").first
            if not pane.is_visible():
                break
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
        except Exception:
            break


def _is_locator_disabled(loc) -> bool:
    """Check whether a menu item locator is disabled or locked."""
    try:
        if loc.is_disabled():
            return True
    except Exception:
        pass
    try:
        if (loc.get_attribute("aria-disabled") or "").lower() == "true":
            return True
        cls = (loc.get_attribute("class") or "").lower()
        if "disabled" in cls:
            return True
    except Exception:
        pass
    return False


def _find_matching_in_scope(scope, selectors: list[str], timeout_ms: int = 3000):
    """Poll selectors inside a Playwright Locator scope until one is visible."""
    if not selectors:
        return None
    deadline = time.monotonic() + max(0.0, timeout_ms / 1000.0)
    while True:
        for sel in selectors:
            try:
                loc = scope.locator(sel).first
                if loc.is_visible():
                    return loc
            except Exception:
                continue
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.15)


def _tag_target_tile(page: Page, cand_src: str, tile_selectors: list[str]) -> bool:
    """Mark the closest tile container owning cand_src with data-flow-target-tile='1'."""
    base_src = re.sub(r"=[^/]+$", "", cand_src or "")
    try:
        return bool(
            page.evaluate(
                """(data) => {
                    for (const old of document.querySelectorAll('[data-flow-target-tile]')) {
                        old.removeAttribute('data-flow-target-tile');
                    }
                    const candSrc = data.candSrc || '';
                    const baseSrc = data.baseSrc || '';
                    const tileSels = data.tileSels || [];
                    const imgs = Array.from(document.querySelectorAll('img'));
                    const match = imgs.find(img => {
                        const s = img.currentSrc || img.src || '';
                        return (candSrc && s === candSrc) || (baseSrc && s.startsWith(baseSrc));
                    });
                    if (!match) return false;
                    let target = null;
                    for (const sel of tileSels) {
                        const found = match.closest(sel);
                        if (found) { target = found; break; }
                    }
                    if (!target) {
                        let cur = match.parentElement;
                        for (let d = 0; d < 6 && cur; d++) {
                            const btns = cur.querySelectorAll('button');
                            if (btns.length >= 1 && btns.length <= 6) {
                                target = cur;
                                break;
                            }
                            cur = cur.parentElement;
                        }
                    }
                    if (!target) target = match.parentElement;
                    if (!target) return false;
                    target.setAttribute('data-flow-target-tile', '1');
                    return true;
                }""",
                {"candSrc": cand_src, "baseSrc": base_src, "tileSels": tile_selectors},
            )
        )
    except Exception:
        return False


def _clear_target_tile_tag(page: Page) -> None:
    try:
        page.evaluate(
            """() => {
                for (const el of document.querySelectorAll('[data-flow-target-tile]')) {
                    el.removeAttribute('data-flow-target-tile');
                }
            }"""
        )
    except Exception:
        pass


def _download_upscaled_from_tile(
    page: Page,
    selectors: dict[str, Any],
    cand_src: str,
    target_resolution: str,
    timeout_ms: int = 75000,
) -> tuple[bytes | None, str]:
    """Trigger Google Flow's post-generation 2K/4K export with 4K->2K->1K cascade."""
    eff_res = normalize_target_resolution(target_resolution)
    if eff_res == "1k" or not cand_src:
        return None, "1k"

    tiers = ["4k", "2k"] if eff_res == "4k" else ["2k"]
    tile_selectors = selectors.get("tile_container_selectors") or [
        "flow-image-tile",
        "flow-tile-container",
        "flow-grid-tile-container",
    ]
    more_selectors = selectors.get("tile_more_options_button") or [
        "button[aria-label*='Opsi lainnya' i]",
        "button[aria-label*='More options' i]",
        "button.mat-mdc-menu-trigger:has(mat-icon:has-text('more_vert'))",
    ]
    dl_menu_selectors = selectors.get("menu_download_item") or [
        ".cdk-overlay-pane button[role='menuitem']:has-text('Download')",
        ".cdk-overlay-pane button[role='menuitem']:has-text('Unduh')",
        ".cdk-overlay-pane [role='menuitem']:has(mat-icon:has-text('download'))",
    ]
    res_map = selectors.get("download_resolution_items") or {}

    for tier in tiers:
        min_long_edge = 3840 if tier == "4k" else 1920
        tier_selectors = res_map.get(tier) or [
            f".cdk-overlay-pane button[role='menuitem']:has-text('{tier.upper()}')",
            f".cdk-overlay-pane [role='menuitem']:has-text('{tier.upper()}')",
        ]

        for attempt in range(2):
            try:
                _dismiss_cdk_overlays(page)
                if not _tag_target_tile(page, cand_src, tile_selectors):
                    raise RuntimeError("Tile container untuk kandidat gambar tidak ditemukan.")

                tile = page.locator("[data-flow-target-tile='1']").first
                tile.scroll_into_view_if_needed()
                tile.hover()
                page.wait_for_timeout(250)

                more_btn = _find_matching_in_scope(tile, more_selectors, timeout_ms=2500)
                if not more_btn:
                    raise RuntimeError("Tombol 'Opsi lainnya' pada tile tidak ditemukan.")
                more_btn.click(force=True)
                page.wait_for_timeout(450)

                dl_item = find_matching_locator(page, dl_menu_selectors, timeout_ms=3000)
                if not dl_item:
                    raise RuntimeError("Menu item 'Download' tidak ditemukan di overlay.")

                dl_item.hover()
                page.wait_for_timeout(550)
                res_btn = find_matching_locator(page, tier_selectors, timeout_ms=1200)
                if not res_btn:
                    dl_item.click(force=True)
                    page.wait_for_timeout(550)
                    res_btn = find_matching_locator(page, tier_selectors, timeout_ms=2000)

                if not res_btn:
                    logger.info(f"[Cascade] Opsi resolusi {tier.upper()} tidak ditemukan di submenu.")
                    break

                if _is_locator_disabled(res_btn):
                    logger.info(f"[Cascade] Opsi resolusi {tier.upper()} terkunci/disabled (butuh Upgrade), cascade ke tier berikutnya...")
                    break

                logger.info(f"[Phase2] Memicu download native {tier.upper()} dari Google Flow (timeout={timeout_ms // 1000}s)...")
                with page.expect_download(timeout=timeout_ms) as dl_info:
                    res_btn.click()
                dl = dl_info.value
                dl_path = dl.path()
                if not dl_path or not os.path.exists(dl_path):
                    raise RuntimeError(f"File hasil download {tier.upper()} tidak ditemukan.")

                raw_bytes = Path(dl_path).read_bytes()
                with Image.open(io.BytesIO(raw_bytes)) as im:
                    w, h = im.size
                if max(w, h) < min_long_edge:
                    raise RuntimeError(
                        f"Dimensi download {tier.upper()} ({w}x{h}) di bawah ambang {min_long_edge}px."
                    )
                logger.info(
                    f"[Phase2] Download {tier.upper()} SUKSES: {w}x{h}, {len(raw_bytes) / 1024.0:.1f} KB"
                )
                return raw_bytes, tier

            except Exception as exc:
                logger.warning(f"[Phase2] Percobaan {attempt + 1}/2 untuk {tier.upper()} gagal: {exc}")
                if attempt == 0:
                    page.wait_for_timeout(500)
            finally:
                _dismiss_cdk_overlays(page)
                _clear_target_tile_tag(page)

    return None, "1k_fallback"


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
    target_resolution: str | None = None,
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

    # 1. Navigasi / Reset Proyek Bersih (selalu mulai dari entry_url agar warm session bebas leftover anchor & aspect ratio)
    if is_warm:
        logger.info(f"[{card_label}] Sesi warm aktif. Reset navigasi ke kanvas baru agar bebas anchor & rasio lama...")
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

    page.wait_for_timeout(1500 if is_warm else 2000)
    dismiss_onboarding_dialogs(page)

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

    # Bersihkan sisa media-chip lama SEBELUM upload anchor baru (jangan pernah dijalankan setelah upload!)
    try:
        page.evaluate("""() => {
            const chips = document.querySelectorAll('.media-chip, .reference-chip, [role="button"][aria-label*="delete" i], [role="button"][aria-label*="remove" i], .attachment-chip, button.media-chip-remove');
            for (const c of chips) {
                try { c.click(); } catch(e) {}
            }
        }""")
    except Exception:
        pass

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
    valid_paths: list[str] = []
    optimized_paths: list[str] = []
    if ref_paths:
        valid_paths = [
            p for p in ref_paths
            if os.path.exists(p) and os.path.getsize(p) > 2048 and "mock_" not in os.path.basename(p)
        ][:4]

        if len(valid_paths) != len(ref_paths):
            logger.warning(
                f"[{card_label}] Beberapa anchor tidak valid/ditemukan: expected={len(ref_paths)}, valid={len(valid_paths)} ({ref_paths})"
            )

        if valid_paths:
            # Optimasi anchor image ke JPEG 1024px quality 93 (reduksi ~88% ukuran transfer)
            optimized_paths = [get_optimized_anchor_path(p) for p in valid_paths]
            anchor_summary = [
                f"Image {idx + 1}={os.path.basename(orig)}->{os.path.basename(opt)}({os.path.getsize(opt) // 1024}KB)"
                for idx, (orig, opt) in enumerate(zip(valid_paths, optimized_paths))
            ]
            logger.info(
                f"[{card_label}] Mengunggah {len(optimized_paths)} anchor gambar (JPEG Q93 cache) ke Flow: {anchor_summary}"
            )

            uploaded = False
            try:
                add_btn = find_matching_locator(page, selectors.get("add_media_button", [
                    ".add-menu-trigger",
                    "button[aria-label*='Tambahkan bahan' i]",
                    "button:has-text('add')",
                ]), timeout_ms=4000)

                if add_btn:
                    add_btn.click()
                    page.wait_for_timeout(600)
                    upload_btn = find_matching_locator(page, selectors.get("upload_media_menu_item", [
                        "button:has-text('Upload media')",
                        "[role='menuitem']:has-text('Upload media')",
                        "button:has-text('Upload')",
                    ]), timeout_ms=4000)

                    if upload_btn:
                        with page.expect_file_chooser(timeout=8000) as fc_info:
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
                        ], timeout_ms=3500)
                        if agree_btn:
                            logger.info(f"[{card_label}] Modal persetujuan hak cipta gambar ('Saya setuju') terdeteksi, mengklik...")
                            agree_btn.click(force=True)
                            page.wait_for_timeout(1200)

                        # Klik 'Tambahkan ke perintah' (tunggu hingga upload multi-anchor selesai diproses UI)
                        add_to_prompt = find_matching_locator(page, selectors.get("add_to_prompt_button", [
                            "button:has-text('Tambahkan ke perintah')",
                            "button:has-text('Add to prompt')",
                        ]), timeout_ms=8000)
                        if add_to_prompt:
                            add_to_prompt.click()
                            page.wait_for_timeout(1500 if len(optimized_paths) > 1 else 1000)
                        uploaded = True

                if not uploaded:
                    ref_input_loc = find_matching_locator(page, selectors.get("reference_image_input", []), timeout_ms=4000)
                    if ref_input_loc:
                        ref_input_loc.set_input_files(optimized_paths)
                        page.wait_for_timeout(2000)
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
        if page.locator(".cdk-overlay-backdrop").is_visible():
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

    # Bersihkan teks prompt input (tanpa menyentuh media-chip anchor yang baru di-upload!)
    try:
        page.evaluate("""(el) => {
            el.focus();
            const sel = window.getSelection();
            const range = document.createRange();
            range.selectNodeContents(el);
            sel.removeAllRanges();
            sel.addRange(range);
            document.execCommand('delete', false, null);
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

    # Karantina ulang semua <img> yang sudah ada tepat sebelum klik Generate agar upload thumbnail async tidak ter-claim sebagai hasil!
    try:
        pre_gen_imgs = set(page.evaluate("""() => {
            return Array.from(document.querySelectorAll('img'))
                .map(i => i.currentSrc || i.src || '')
                .filter(Boolean);
        }"""))
        blacklisted_ref_srcs.update(pre_gen_imgs)
    except Exception:
        pass

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
    accepted_cand_src: str | None = None
    accepted_dims: tuple[int, int] = (0, 0)

    while time.time() - start_wait < 90:
        elapsed = time.time() - start_wait

        # Cek apakah job dibatalkan oleh klien / timeout
        try:
            c_conn = get_db_connection()
            try:
                c_cur = c_conn.cursor()
                c_cur.execute("SELECT status FROM flow_image_jobs WHERE id = ?", (job_id,))
                c_row = c_cur.fetchone()
                if c_row and c_row["status"] == "cancelled":
                    logger.info(f"[{card_label}] Job {job_id} dibatalkan oleh klien/timeout. Menghentikan render...")
                    raise RuntimeError(f"Job {job_id} dibatalkan oleh klien/timeout.")
            finally:
                c_conn.close()
        except RuntimeError:
            raise
        except Exception:
            pass

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
                for (let d = 0; d < 8 && cur; d++) {
                    const cls = (cur.className || '').toString().toLowerCase();
                    const tag = (cur.tagName || '').toLowerCase();
                    const aria = ((cur.getAttribute && cur.getAttribute('aria-label')) || '').toLowerCase();
                    const tid = ((cur.getAttribute && cur.getAttribute('data-testid')) || '').toLowerCase();
                    if (
                        tag === 'flow-prompt-box' ||
                        cls.includes('prompt') ||
                        cls.includes('media-chip') ||
                        cls.includes('reference') ||
                        cls.includes('attachment') ||
                        cls.includes('cdk-overlay') ||
                        aria.includes('reference') ||
                        aria.includes('bahan') ||
                        tid.includes('reference')
                    ) {
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

                # Cek clone eksak maupun perseptual terhadap semua anchor (original + JPEG cache)
                all_clone_candidates = list(dict.fromkeys([*(ref_paths or []), *(optimized_paths or [])]))
                if _is_perceptual_clone_of_refs(raw_bytes, all_clone_candidates):
                    logger.warning(f"[{card_label}] Kandidat <img> terdeteksi sebagai clone anchor referensi ({cand_src[:80]}...), mengabaikan dan melanjutkan polling...")
                    blacklisted_ref_srcs.add(cand_src)
                    continue

            except Exception:
                continue

            file_size_kb = len(raw_bytes) / 1024.0
            logger.info(
                f"[DIAGNOSTIK] Gambar base 1K berhasil ditangkap: "
                f"PIL={pil_w}x{pil_h}, Ukuran={file_size_kb:.2f} KB ({len(raw_bytes)} bytes)"
            )
            result_bytes = raw_bytes
            accepted_cand_src = cand_src
            accepted_dims = (pil_w, pil_h)
            candidate_accepted = True
            break

        if candidate_accepted and result_bytes:
            break

        page.wait_for_timeout(1500)

    if not result_bytes:
        raise RuntimeError("Gagal menangkap gambar hasil dari Google Flow dalam 90 detik.")

    generate_wait_ms = round((time.perf_counter() - t_gen_start - (download_ms / 1000.0)) * 1000, 2)

    # Phase 2: Post-generation native 2K/4K download with guaranteed 1K fallback
    eff_target_res = normalize_target_resolution(target_resolution or selectors.get("target_resolution"))
    phase2_download_ms = 0.0
    captured_tier = "1k"
    cap_w, cap_h = accepted_dims

    if eff_target_res in ("2k", "4k") and accepted_cand_src:
        try:
            touch_conn = get_db_connection()
            try:
                touch_account_busy_timestamp(touch_conn, account["id"])
            finally:
                touch_conn.close()
        except Exception:
            pass

        t_p2_start = time.perf_counter()
        p2_timeout_ms = 120000 if eff_target_res == "4k" else 75000
        try:
            upscaled_bytes, resolved_tier = _download_upscaled_from_tile(
                page,
                selectors,
                accepted_cand_src,
                eff_target_res,
                timeout_ms=p2_timeout_ms,
            )
            if upscaled_bytes:
                with Image.open(io.BytesIO(upscaled_bytes)) as up_im:
                    cap_w, cap_h = up_im.size
                result_bytes = upscaled_bytes
                captured_tier = resolved_tier
            else:
                logger.warning(
                    f"[Fallback1K] [{card_label}] Download {eff_target_res.upper()} gagal/terkunci; "
                    f"menyimpan gambar 1K ({cap_w}x{cap_h}) tanpa failover akun."
                )
        except Exception as p2_exc:
            logger.warning(
                f"[Fallback1K] [{card_label}] Phase 2 error ({p2_exc}); "
                f"menyimpan gambar 1K ({cap_w}x{cap_h}) tanpa failover akun."
            )
        phase2_download_ms = round((time.perf_counter() - t_p2_start) * 1000, 2)

    total_ms = round((time.perf_counter() - t_start) * 1000, 2)

    logger.info(
        f"[FlowTimer] [{job_id}] [{card_label}] "
        f"browser_init_ms={browser_init_ms:.0f} "
        f"upload_ms={upload_ms:.0f} "
        f"generate_wait_ms={generate_wait_ms:.0f} "
        f"download_ms={download_ms:.0f} "
        f"phase2_download_ms={phase2_download_ms:.0f} "
        f"captured_dims={cap_w}x{cap_h} "
        f"tier={captured_tier} "
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
        warm_character_id: str | None = None
        last_activity_time: float = time.time()

        def close_warm_context(reset_status_to_active: bool = True):
            nonlocal warm_context, warm_page, warm_account, warm_lock, warm_batch_count, warm_character_id
            if warm_context:
                try:
                    warm_context.close()
                except Exception:
                    pass
                warm_context = None
                warm_page = None

            if warm_account and warm_lock:
                if reset_status_to_active:
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
            warm_character_id = None

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
            target_resolution = normalize_target_resolution(settings.get("target_resolution"))

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
                    subsequent_job = claim_job_for_specific_account(conn, warm_account["id"], character_id=warm_character_id)
                    other_queued = has_queued_jobs_for_other_accounts(conn, warm_account["id"], current_character_id=warm_character_id)
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
                    selectors["target_resolution"] = target_resolution
                    try:
                        raw_image = execute_flow_generation(
                            warm_page, selectors, subsequent_job, warm_account, is_warm=True
                        )
                        img_filename = f"{job_id}.jpg"
                        img_disk_path = MEDIA_DIR / img_filename
                        save_flow_image_jpeg(raw_image, img_disk_path, quality=95)
                        image_url = f"/media/images/{img_filename}"

                        conn = get_db_connection()
                        try:
                            update_job_status(
                                conn, job_id, "completed", output_filename=img_filename, image_url=image_url
                            )
                            record_account_success(conn, warm_account["id"])
                        finally:
                            conn.close()
                        clear_failed_accounts_for_job(job_id)

                        warm_batch_count += 1
                        last_activity_time = time.time()
                        logger.info(f"[WorkerSlot-{worker_slot_id}] Job {job_id} SUKSES! ({image_url})")
                        time.sleep(1.0)
                        continue

                    except PermissionError as e:
                        err_str = str(e)
                        failed_acc_id = warm_account["id"]
                        logger.error(
                            f"[WorkerSlot-{worker_slot_id}] PermissionError (login expired) pada warm job {job_id} "
                            f"Akun #{failed_acc_id}: {err_str}"
                        )
                        close_warm_context(reset_status_to_active=False)
                        conn = get_db_connection()
                        try:
                            handle_job_failure_and_failover(
                                conn,
                                job_id,
                                failed_acc_id,
                                err_str,
                                is_permission_error=True,
                                cooldown_minutes=cooldown_minutes,
                            )
                        finally:
                            conn.close()
                        time.sleep(1.5)
                        continue

                    except Exception as e:
                        err_str = str(e)
                        failed_acc_id = warm_account["id"]
                        logger.error(f"[WorkerSlot-{worker_slot_id}] Error pada warm job {job_id}: {err_str}")
                        close_warm_context(reset_status_to_active=False)
                        conn = get_db_connection()
                        try:
                            handle_job_failure_and_failover(
                                conn,
                                job_id,
                                failed_acc_id,
                                err_str,
                                is_proxy_offline=isinstance(e, ProxyOfflineError) or ("SOCKS5_PROXY_OFFLINE" in err_str),
                                cooldown_minutes=cooldown_minutes,
                            )
                        finally:
                            conn.close()
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
            selectors["target_resolution"] = target_resolution
            context = None
            page = None

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

                img_filename = f"{job_id}.jpg"
                img_disk_path = MEDIA_DIR / img_filename
                save_flow_image_jpeg(raw_image, img_disk_path, quality=95)
                image_url = f"/media/images/{img_filename}"

                conn = get_db_connection()
                try:
                    update_job_status(
                        conn, job_id, "completed", output_filename=img_filename, image_url=image_url
                    )
                    record_account_success(conn, account_id)
                finally:
                    conn.close()
                clear_failed_accounts_for_job(job_id)

                # Simpan context sebagai warm session
                warm_context = context
                warm_page = page
                warm_account = account
                warm_lock = profile_lock
                warm_batch_count = 1
                warm_character_id = str(job["character_id"]) if job["character_id"] else None
                last_activity_time = time.time()
                logger.info(
                    f"[WorkerSlot-{worker_slot_id}] Job {job_id} SUKSES! Browser tetap warm untuk job berikutnya (char={warm_character_id})."
                )

            except PermissionError as e:
                err_str = str(e)
                logger.error(
                    f"[WorkerSlot-{worker_slot_id}] PermissionError (login expired) pada Job {job_id} "
                    f"Akun #{account_id}: {err_str}"
                )
                debug_fn = f"{job_id}_err.png"
                debug_path = DEBUG_DIR / debug_fn
                try:
                    if page:
                        page.screenshot(path=str(debug_path), full_page=True)
                        debug_url = f"/media/debug/{debug_fn}"
                    else:
                        debug_url = None
                except Exception:
                    debug_url = None

                if context:
                    try:
                        context.close()
                    except Exception:
                        pass

                conn = get_db_connection()
                try:
                    handle_job_failure_and_failover(
                        conn,
                        job_id,
                        account_id,
                        err_str,
                        is_permission_error=True,
                        debug_screenshot_url=debug_url,
                        cooldown_minutes=cooldown_minutes,
                    )
                finally:
                    conn.close()

                profile_lock.release()
                warm_context = None
                warm_page = None
                warm_account = None
                warm_lock = None
                warm_batch_count = 0
                warm_character_id = None
                time.sleep(1.5)

            except Exception as e:
                err_str = str(e)
                logger.error(f"[WorkerSlot-{worker_slot_id}] Gagal memproses Job {job_id} pada Akun #{account_id}: {err_str}")
                debug_fn = f"{job_id}_err.png"
                debug_path = DEBUG_DIR / debug_fn
                try:
                    if page:
                        page.screenshot(path=str(debug_path), full_page=True)
                        debug_url = f"/media/debug/{debug_fn}"
                    else:
                        debug_url = None
                except Exception:
                    debug_url = None

                if context:
                    try:
                        context.close()
                    except Exception:
                        pass

                conn = get_db_connection()
                try:
                    handle_job_failure_and_failover(
                        conn,
                        job_id,
                        account_id,
                        err_str,
                        is_proxy_offline=isinstance(e, ProxyOfflineError) or ("SOCKS5_PROXY_OFFLINE" in err_str),
                        debug_screenshot_url=debug_url,
                        cooldown_minutes=cooldown_minutes,
                    )
                finally:
                    conn.close()

                profile_lock.release()
                warm_context = None
                warm_page = None
                warm_account = None
                warm_lock = None
                warm_batch_count = 0
                warm_character_id = None
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
