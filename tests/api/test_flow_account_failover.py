from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import io
from pathlib import Path
import sqlite3
import uuid

from PIL import Image
import pytest

from backend.app.infrastructure import universal_image_adapter as uia
from backend.workers import flow_image_worker as fiw


def _tiny_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(120, 160, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _init_temp_flow_db(db_path: Path, profile_root: Path, account_statuses: dict[int, str] | None = None) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(
        """
        CREATE TABLE flow_accounts (
            id INTEGER PRIMARY KEY,
            label VARCHAR(64) NOT NULL,
            profile_dir VARCHAR(255) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            cooldown_until DATETIME,
            daily_count INTEGER NOT NULL DEFAULT 0,
            last_reset_date VARCHAR(10) NOT NULL,
            total_count INTEGER NOT NULL DEFAULT 0,
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            last_used_at DATETIME,
            updated_at DATETIME NOT NULL
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE flow_image_jobs (
            id CHAR(36) PRIMARY KEY,
            project_id CHAR(36),
            scene_id CHAR(36),
            shot_id CHAR(36),
            character_id CHAR(36),
            asset_slot VARCHAR(32),
            target_type VARCHAR(32),
            state_id CHAR(36),
            prompt TEXT NOT NULL,
            aspect_ratio VARCHAR(10) NOT NULL DEFAULT '16:9',
            reference_image_paths JSON,
            preferred_account_id INTEGER,
            assigned_account_id INTEGER,
            status VARCHAR(20) NOT NULL DEFAULT 'queued',
            output_filename VARCHAR(255),
            image_url VARCHAR(512),
            debug_screenshot_url VARCHAR(512),
            error_message TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3,
            created_at DATETIME NOT NULL,
            started_at DATETIME,
            completed_at DATETIME
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE flow_settings (
            key VARCHAR(64) PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    statuses = account_statuses or {1: "active", 2: "active", 3: "active", 4: "active", 5: "active", 6: "need_relogin"}
    for acc_id in range(1, 7):
        prof_dir = profile_root / f"akun_{acc_id}"
        prof_dir.mkdir(parents=True, exist_ok=True)
        # Stagger initial last_used_at so LRU deterministically starts at #1 -> #2 -> #3 -> #4 -> #5
        last_used = (now - timedelta(hours=10 - acc_id)).isoformat()
        conn.execute(
            """
            INSERT INTO flow_accounts (
                id, label, profile_dir, status, daily_count, last_reset_date,
                total_count, consecutive_failures, last_used_at, updated_at
            ) VALUES (?, ?, ?, ?, 0, ?, 0, 0, ?, ?)
            """,
            (
                acc_id,
                f"Akun Pro {acc_id}",
                str(prof_dir),
                statuses.get(acc_id, "active"),
                today_str,
                last_used,
                now.isoformat(),
            ),
        )

    settings_rows = [
        ("socks5_proxy", "socks5://127.0.0.1:10808"),
        ("batch_size_per_account", "4"),
        ("cooldown_minutes", "15"),
        ("worker_enabled", "true"),
    ]
    conn.executemany("INSERT INTO flow_settings (key, value) VALUES (?, ?)", settings_rows)
    conn.commit()
    conn.close()


def _insert_job(
    db_path: Path,
    prompt: str = "Test cinematic frame",
    character_id: str | None = None,
    max_retries: int = 3,
) -> str:
    job_id = str(uuid.uuid4())
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT INTO flow_image_jobs (
            id, character_id, prompt, aspect_ratio, status, retry_count, max_retries, created_at
        ) VALUES (?, ?, ?, '16:9', 'queued', 0, ?, ?)
        """,
        (job_id, character_id, prompt, max_retries, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()
    return job_id


@pytest.fixture(autouse=True)
def _isolated_flow_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolate worker globals, paths, and per-job failure state from production DB/files."""
    with fiw._FAILED_ACCOUNTS_LOCK:
        fiw._FAILED_ACCOUNTS_BY_JOB.clear()
        fiw._FAILED_ACCOUNT_ORDER_BY_JOB.clear()

    db_path = tmp_path / "test_movieai.db"
    media_dir = tmp_path / "media_images"
    debug_dir = tmp_path / "media_debug"
    profiles_dir = tmp_path / "profiles"
    _init_temp_flow_db(db_path, profiles_dir)

    monkeypatch.setattr(fiw, "DB_PATH", db_path)
    monkeypatch.setattr(fiw, "MEDIA_DIR", media_dir)
    monkeypatch.setattr(fiw, "DEBUG_DIR", debug_dir)
    monkeypatch.setattr(fiw, "LOCK_FILE_PATH", tmp_path / "flow_worker.lock")

    # Redirect /tmp/flow_account_<id>.lock away from production locks
    orig_lock_init = fiw.AccountProfileLock.__init__

    def _tmp_lock_init(self, account_id: int):
        orig_lock_init(self, account_id)
        self.lock_path = tmp_path / f"flow_account_{account_id}.lock"

    monkeypatch.setattr(fiw.AccountProfileLock, "__init__", _tmp_lock_init)
    yield db_path

    with fiw._FAILED_ACCOUNTS_LOCK:
        fiw._FAILED_ACCOUNTS_BY_JOB.clear()
        fiw._FAILED_ACCOUNT_ORDER_BY_JOB.clear()


def _install_worker_loop_fakes(monkeypatch: pytest.MonkeyPatch, on_execute):
    """Patch Playwright, sleep, proxy check, and 9Router spy for deterministic worker_thread_loop tests."""
    nine_router_calls = []

    async def _forbidden_9router(*args, **kwargs):
        nine_router_calls.append((args, kwargs))
        raise AssertionError("9Router fallback must NEVER be called on Google Flow failure!")

    monkeypatch.setattr(uia.UniversalImageAdapter, "_execute_9router_fallback", _forbidden_9router)
    monkeypatch.setattr(fiw, "get_effective_concurrency", lambda: 1)
    monkeypatch.setattr(fiw, "get_cached_socks5_health", lambda *a, **kw: {"healthy": True, "detail": "ok"})
    monkeypatch.setattr(fiw, "load_selectors", lambda: {"entry_url": "https://flow.google.com/"})
    monkeypatch.setattr(fiw, "stagger_browser_launch", lambda: None)
    monkeypatch.setattr(fiw.time, "sleep", lambda _s: None)

    class _FakePage:
        def screenshot(self, *args, **kwargs):
            return None

    class _FakeContext:
        def __init__(self):
            self.pages = [_FakePage()]
            self.closed = False

        def new_page(self):
            return _FakePage()

        def close(self):
            self.closed = True

    class _FakeChromium:
        def launch_persistent_context(self, **kwargs):
            return _FakeContext()

    class _FakePlaywright:
        chromium = _FakeChromium()

    @contextmanager
    def _fake_sync_playwright():
        yield _FakePlaywright()

    monkeypatch.setattr(fiw, "sync_playwright", _fake_sync_playwright)
    monkeypatch.setattr(fiw, "execute_flow_generation", on_execute)
    return nine_router_calls


def test_failover_account1_timeout_updates_lru_and_succeeds_on_account2(
    _isolated_flow_state: Path, monkeypatch: pytest.MonkeyPatch
):
    """Scenario 1: Account #1 fails -> last_used_at updates (leaves LRU top), job requeues, Account #2 completes."""
    db_path = _isolated_flow_state
    job_id = _insert_job(db_path)

    conn = fiw.get_db_connection()
    before_row = conn.execute("SELECT last_used_at FROM flow_accounts WHERE id = 1").fetchone()
    before_lru_1 = before_row["last_used_at"]
    conn.close()

    attempts: list[int] = []
    png_bytes = _tiny_png_bytes()

    def _fake_exec(page, selectors, job, account, is_warm=False):
        acc_id = account["id"]
        attempts.append(acc_id)
        if acc_id == 1:
            raise RuntimeError("Gagal menangkap gambar hasil dari Google Flow dalam 90 detik.")
        fiw.running = False
        return png_bytes

    nine_router_calls = _install_worker_loop_fakes(monkeypatch, _fake_exec)
    monkeypatch.setattr(fiw, "running", True)

    fiw.worker_thread_loop(0)

    assert attempts == [1, 2]
    assert nine_router_calls == []

    conn = fiw.get_db_connection()
    job_row = conn.execute("SELECT * FROM flow_image_jobs WHERE id = ?", (job_id,)).fetchone()
    acc1 = conn.execute("SELECT * FROM flow_accounts WHERE id = 1").fetchone()
    acc2 = conn.execute("SELECT * FROM flow_accounts WHERE id = 2").fetchone()
    conn.close()

    assert job_row["status"] == "completed"
    assert job_row["retry_count"] == 1
    assert job_row["assigned_account_id"] == 2
    assert acc1["status"] == "active"
    assert acc1["consecutive_failures"] == 1
    assert acc1["last_used_at"] > before_lru_1  # Moved to back of LRU
    assert acc2["total_count"] == 1
    assert fiw.get_failed_accounts_for_job(job_id) == set()


def test_failover_exhausts_all_5_active_accounts_without_duplicates_or_9router(
    _isolated_flow_state: Path, monkeypatch: pytest.MonkeyPatch
):
    """Scenario 2: Consecutive failures across all 5 active accounts -> tries #1..#5 once each, then marks failed."""
    db_path = _isolated_flow_state
    job_id = _insert_job(db_path, max_retries=3)

    attempts: list[int] = []

    def _always_fail(page, selectors, job, account, is_warm=False):
        acc_id = account["id"]
        attempts.append(acc_id)
        if len(attempts) >= 5:
            # Allow current iteration to finish handling failure, then stop loop on next check
            fiw.running = False
        raise RuntimeError(f"Timeout render pada Akun #{acc_id}")

    nine_router_calls = _install_worker_loop_fakes(monkeypatch, _always_fail)
    monkeypatch.setattr(fiw, "running", True)

    fiw.worker_thread_loop(0)

    assert attempts == [1, 2, 3, 4, 5]
    assert len(set(attempts)) == 5
    assert 6 not in attempts  # Akun #6 is need_relogin
    assert nine_router_calls == []

    conn = fiw.get_db_connection()
    job_row = conn.execute("SELECT * FROM flow_image_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()

    assert job_row["status"] == "failed"
    assert job_row["retry_count"] == 4
    for acc_id in range(1, 6):
        assert f"Akun #{acc_id}" in (job_row["error_message"] or "")
    assert fiw.get_failed_accounts_for_job(job_id) == set()


def test_permission_error_marks_account_need_relogin_and_fails_over(
    _isolated_flow_state: Path, monkeypatch: pytest.MonkeyPatch
):
    """Scenario 3: PermissionError on Account #3 -> marks Akun #3 'need_relogin' & fails over to Account #4."""
    db_path = _isolated_flow_state
    # Set #1 and #2 as recently used so #3 is picked first by LRU
    conn = fiw.get_db_connection()
    now_iso = datetime.now(timezone.utc).isoformat()
    conn.execute("UPDATE flow_accounts SET last_used_at = ? WHERE id IN (1, 2)", (now_iso,))
    conn.commit()
    conn.close()

    job_id = _insert_job(db_path)
    attempts: list[int] = []
    png_bytes = _tiny_png_bytes()

    def _perm_then_ok(page, selectors, job, account, is_warm=False):
        acc_id = account["id"]
        attempts.append(acc_id)
        if acc_id == 3:
            raise PermissionError("Akun #3 terlempar ke URL login Google: https://accounts.google.com/v3/signin")
        fiw.running = False
        return png_bytes

    nine_router_calls = _install_worker_loop_fakes(monkeypatch, _perm_then_ok)
    monkeypatch.setattr(fiw, "running", True)

    fiw.worker_thread_loop(0)

    assert attempts == [3, 4]
    assert nine_router_calls == []

    conn = fiw.get_db_connection()
    acc3 = conn.execute("SELECT * FROM flow_accounts WHERE id = 3").fetchone()
    job_row = conn.execute("SELECT * FROM flow_image_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()

    assert acc3["status"] == "need_relogin"
    assert "accounts.google.com" in (acc3["last_error"] or "")
    assert job_row["status"] == "completed"
    assert job_row["assigned_account_id"] == 4
    assert job_row["retry_count"] == 1


def test_warm_session_failure_excludes_same_job_and_requeues_for_other_account(
    _isolated_flow_state: Path, monkeypatch: pytest.MonkeyPatch
):
    """Scenario 4: Warm session on Account #2 fails on job_2 -> cannot reclaim job_2, fails over to another account."""
    db_path = _isolated_flow_state
    char_id = str(uuid.uuid4())
    # Make Akun #2 oldest in LRU so it starts warm on job_1
    conn = fiw.get_db_connection()
    very_old = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    conn.execute("UPDATE flow_accounts SET last_used_at = ? WHERE id = 2", (very_old,))
    conn.commit()
    conn.close()

    job_1 = _insert_job(db_path, prompt="Job 1 warm starter", character_id=char_id)
    job_2 = _insert_job(db_path, prompt="Job 2 warm fail then failover", character_id=char_id)

    exec_log: list[tuple[str, int, bool]] = []
    png_bytes = _tiny_png_bytes()

    def _warm_fail_exec(page, selectors, job, account, is_warm=False):
        jid = str(job["id"])
        acc_id = account["id"]
        exec_log.append((jid, acc_id, is_warm))
        if jid == job_2 and acc_id == 2:
            raise RuntimeError("Warm timeout on Akun #2")
        if jid == job_2 and acc_id != 2:
            fiw.running = False
        return png_bytes

    nine_router_calls = _install_worker_loop_fakes(monkeypatch, _warm_fail_exec)
    monkeypatch.setattr(fiw, "running", True)

    fiw.worker_thread_loop(0)

    # First job_1 succeeds cold on #2, then job_2 runs warm on #2 and fails, then job_2 fails over to #1
    assert exec_log[0] == (job_1, 2, False)
    assert exec_log[1] == (job_2, 2, True)
    assert exec_log[2][0] == job_2
    assert exec_log[2][1] != 2
    assert exec_log[2][2] is False
    assert nine_router_calls == []

    # Direct verification of warm claim exclusion guard on a failed job
    conn = fiw.get_db_connection()
    job_3 = _insert_job(db_path, prompt="Job 3 exclusion check", character_id=char_id)
    fiw.record_failed_account_for_job(job_3, 2)
    claimed = fiw.claim_job_for_specific_account(conn, account_id=2, character_id=char_id)
    assert claimed is None
    assert fiw.has_queued_jobs_for_other_accounts(conn, current_account_id=2, current_character_id=char_id) is True

    job2_row = conn.execute("SELECT * FROM flow_image_jobs WHERE id = ?", (job_2,)).fetchone()
    conn.close()
    assert job2_row["status"] == "completed"
    assert job2_row["retry_count"] == 1
    assert job2_row["assigned_account_id"] != 2
