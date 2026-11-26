from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import io
import os
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


def _noisy_png_bytes(width: int, height: int) -> bytes:
    """Create a >50KB valid PNG image for Phase 1 capture tests."""
    raw_pixels = os.urandom(width * height * 3)
    img = Image.frombytes("RGB", (width, height), raw_pixels)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_worker_saves_jpg_and_records_2k_output(
    _isolated_flow_state: Path, monkeypatch: pytest.MonkeyPatch
):
    """Scenario 5: Successful 2K output is saved as .jpg (Q95) with 2K dimensions on Account #1."""
    db_path = _isolated_flow_state
    job_id = _insert_job(db_path)

    buf_2k = io.BytesIO()
    Image.new("RGB", (2048, 1152), color=(40, 80, 120)).save(buf_2k, format="JPEG", quality=92)
    bytes_2k = buf_2k.getvalue()

    def _exec_2k(page, selectors, job, account, is_warm=False):
        assert selectors.get("target_resolution") == "2k"
        fiw.running = False
        return bytes_2k

    _install_worker_loop_fakes(monkeypatch, _exec_2k)
    monkeypatch.setattr(fiw, "running", True)
    fiw.worker_thread_loop(0)

    conn = fiw.get_db_connection()
    job_row = conn.execute("SELECT * FROM flow_image_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()

    assert job_row["status"] == "completed"
    assert job_row["output_filename"] == f"{job_id}.jpg"
    assert job_row["image_url"] == f"/media/images/{job_id}.jpg"
    saved_path = fiw.MEDIA_DIR / f"{job_id}.jpg"
    assert saved_path.exists()
    with Image.open(saved_path) as im:
        assert im.format == "JPEG"
        assert im.size == (2048, 1152)


def test_phase2_failure_falls_back_to_1k_without_account_failover(
    _isolated_flow_state: Path, monkeypatch: pytest.MonkeyPatch
):
    """Scenario 6: Phase 1 succeeds (1K), Phase 2 fails -> saves 1K .jpg on Account #1 without failing over."""
    db_path = _isolated_flow_state
    job_id = _insert_job(db_path)
    png_1k = _noisy_png_bytes(1024, 1024)
    assert len(png_1k) > 50_000

    class _FakeElement:
        def __init__(self, visible: bool = False):
            self._visible = visible

        def is_visible(self, timeout=None):
            return self._visible

        def is_disabled(self):
            return False

        def scroll_into_view_if_needed(self):
            pass

        def click(self, *args, **kwargs):
            pass

        def focus(self):
            pass

        def inner_text(self):
            return "ok"

        def element_handle(self):
            return object()

    class _FakeLocator:
        def __init__(self, visible: bool = False):
            self.first = _FakeElement(visible=visible)

        def is_visible(self, timeout=None):
            return self.first.is_visible(timeout=timeout)

        def inner_text(self):
            return ""

    class _FakeKeyboard:
        def press(self, key):
            pass

    class _FakeResponse:
        ok = True

        def body(self):
            return png_1k

    class _FakeRequest:
        def get(self, url, timeout=30000):
            return _FakeResponse()

    fake_clock = [1000.0]

    class _FakePage:
        url = "https://flow.google.com/project/test-proj"
        keyboard = _FakeKeyboard()
        request = _FakeRequest()

        def goto(self, *args, **kwargs):
            pass

        def wait_for_timeout(self, ms):
            fake_clock[0] += ms / 1000.0

        def screenshot(self, *args, **kwargs):
            pass

        def locator(self, sel):
            return _FakeLocator(visible=("ProseMirror" in sel))

        def evaluate(self, script, arg=None):
            if isinstance(arg, dict) and "blacklistedSrcs" in arg:
                return {
                    "is_loading": False,
                    "reason": None,
                    "candidates": [
                        {
                            "src": "https://flow.google.com/asb/fake_token_123=s512",
                            "naturalWidth": 512,
                            "naturalHeight": 512,
                            "isNew": True,
                        }
                    ],
                }
            if "execCommand" in script:
                return True
            return []

    attempts: list[int] = []

    def _boom_phase2(page, selectors, cand_src, target_resolution, timeout_ms=75000):
        raise RuntimeError("Simulated 2K download timeout")

    orig_exec = fiw.execute_flow_generation

    def _wrapped_exec(page, selectors, job, account, is_warm=False):
        attempts.append(account["id"])
        fiw.running = False
        return orig_exec(_FakePage(), selectors, job, account, is_warm=is_warm)

    _install_worker_loop_fakes(monkeypatch, _wrapped_exec)
    monkeypatch.setattr(fiw, "_download_upscaled_from_tile", _boom_phase2)
    monkeypatch.setattr(fiw.time, "time", lambda: fake_clock[0])
    monkeypatch.setattr(
        fiw,
        "load_selectors",
        lambda: {
            "entry_url": "https://flow.google.com/",
            "prompt_input": ["div.ProseMirror"],
            "generate_button": [".generate-icon-button"],
        },
    )
    monkeypatch.setattr(fiw, "running", True)
    fiw.worker_thread_loop(0)

    assert attempts == [1]
    conn = fiw.get_db_connection()
    job_row = conn.execute("SELECT * FROM flow_image_jobs WHERE id = ?", (job_id,)).fetchone()
    acc1 = conn.execute("SELECT * FROM flow_accounts WHERE id = 1").fetchone()
    conn.close()

    assert job_row["status"] == "completed"
    assert job_row["retry_count"] == 0
    assert job_row["assigned_account_id"] == 1
    assert acc1["consecutive_failures"] == 0
    with Image.open(fiw.MEDIA_DIR / f"{job_id}.jpg") as im:
        assert im.size == (1024, 1024)


def test_download_upscaled_4k_disabled_cascades_to_2k_and_cleans_overlays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Scenario 7: 4K locked/disabled cascades to 2K download, and dismisses .cdk-overlay-pane in finally."""
    dl_2k_file = tmp_path / "flow_2k.jpg"
    Image.new("RGB", (2048, 2048), color=(30, 120, 180)).save(dl_2k_file, format="JPEG", quality=92)

    class _FakeDownload:
        def path(self):
            return str(dl_2k_file)

    class _FakeDownloadCM:
        def __init__(self):
            self.value = _FakeDownload()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _MenuBtn:
        def __init__(self, *, disabled: bool = False, on_click=None):
            self._disabled = disabled
            self._on_click = on_click

        def is_visible(self):
            return True

        def is_disabled(self):
            return self._disabled

        def get_attribute(self, name):
            if name == "aria-disabled":
                return "true" if self._disabled else "false"
            return ""

        def hover(self):
            pass

        def click(self, *args, **kwargs):
            if self._on_click:
                self._on_click()

    class _FakeTile:
        def __init__(self):
            self.first = self

        def scroll_into_view_if_needed(self):
            pass

        def hover(self):
            pass

        def locator(self, sel):
            return self

        def is_visible(self):
            return True

        def click(self, *args, **kwargs):
            pass

    class _OverlayPane:
        def __init__(self, page):
            self._page = page

        def is_visible(self):
            return self._page.overlay_open

    class _FakeKeyboard:
        def __init__(self, page):
            self._page = page

        def press(self, key):
            if key == "Escape":
                self._page.escape_presses += 1
                self._page.overlay_open = False

    class _FakePage:
        def __init__(self, *, fail_2k: bool = False):
            self.overlay_open = False
            self.escape_presses = 0
            self.fail_2k = fail_2k
            self.keyboard = _FakeKeyboard(self)
            self.cleared_tags = 0

        def wait_for_timeout(self, ms):
            pass

        def evaluate(self, script, arg=None):
            if "removeAttribute('data-flow-target-tile')" in script and arg is None:
                self.cleared_tags += 1
            return True

        def locator(self, sel):
            if sel == "[data-flow-target-tile='1']":
                return _FakeTile()
            if sel == ".cdk-overlay-pane":
                class _Wrap:
                    def __init__(self, p):
                        self.first = _OverlayPane(p)
                return _Wrap(self)
            return self

        def expect_download(self, timeout=75000):
            if self.fail_2k:
                raise RuntimeError("2K download failed")
            return _FakeDownloadCM()

    selectors = {
        "tile_container_selectors": ["flow-image-tile"],
        "tile_more_options_button": ["button[aria-label*='Opsi lainnya']"],
        "menu_download_item": [".cdk-overlay-pane button[role='menuitem']:has-text('Download')"],
        "download_resolution_items": {
            "4k": [".cdk-overlay-pane button[role='menuitem']:has-text('4K')"],
            "2k": [".cdk-overlay-pane button[role='menuitem']:has-text('2K')"],
        },
    }

    page = _FakePage(fail_2k=False)

    def _fake_find_in_scope(scope, sels, timeout_ms=3000):
        page.overlay_open = True
        return _MenuBtn(disabled=False)

    def _fake_find(p, sels, timeout_ms=3000):
        s0 = sels[0] if sels else ""
        if "4K" in s0:
            return _MenuBtn(disabled=True)  # 4K locked behind AI Ultra Upgrade
        if "2K" in s0:
            return _MenuBtn(disabled=False)
        return _MenuBtn(disabled=False)

    monkeypatch.setattr(fiw, "_find_matching_in_scope", _fake_find_in_scope)
    monkeypatch.setattr(fiw, "find_matching_locator", _fake_find)

    raw_bytes, tier = fiw._download_upscaled_from_tile(
        page, selectors, "https://flow.google.com/asb/test=s512", "4k", timeout_ms=15000
    )
    assert tier == "2k"
    assert raw_bytes is not None
    with Image.open(io.BytesIO(raw_bytes)) as im:
        assert im.size == (2048, 2048)
    assert page.escape_presses >= 1
    assert page.overlay_open is False
    assert page.cleared_tags >= 1

    # Also verify full cascade 4K disabled -> 2K failure -> (None, "1k_fallback")
    page_fail = _FakePage(fail_2k=True)
    raw_fail, tier_fail = fiw._download_upscaled_from_tile(
        page_fail, selectors, "https://flow.google.com/asb/test=s512", "4k", timeout_ms=15000
    )
    assert raw_fail is None
    assert tier_fail == "1k_fallback"
    assert page_fail.overlay_open is False
