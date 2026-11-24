#!/usr/bin/env python3
"""Safe Cleanup Script for MovieAIProducer SQLite Database.

Safely removes dummy / leftover pytest projects from data/movieai.db
while strictly preserving:
- All projects owned by real user 'nurkholisah2409@gmail.com'
- Master / manual projects on whitelist:
  - 'THE FINAL OBSERVER'
  - 'Racoon Vs Dog Backyard Chaos'
  - 'Gate Zero: The Last Ranker'
- Any other projects belonging to non-test users.

Cleans up associated foreign key cascades and unconstrained flow_image_jobs,
then runs VACUUM to reclaim disk space.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sqlite3
import sys

WHITELIST_TITLES = {
    "THE FINAL OBSERVER",
    "Racoon Vs Dog Backyard Chaos",
    "Gate Zero: The Last Ranker",
}

TEST_USER_EMAIL = "needgenius19@gmail.com"
DB_PATH = Path("data/movieai.db")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up dummy test projects from movieai.db")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute database modifications (without this flag, defaults to dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simulate cleanup without writing to database (default)",
    )
    args = parser.parse_args()

    # If --execute is supplied, set dry_run to False
    is_dry_run = not args.execute

    if not DB_PATH.exists():
        print(f"Error: Database file not found at {DB_PATH.resolve()}")
        sys.exit(1)

    initial_size_bytes = DB_PATH.stat().st_size
    initial_size_mb = initial_size_bytes / (1024 * 1024)

    print("=" * 70)
    print("MOVIEAIPRODUCER — PRODUCTION SLATE DATABASE CLEANUP")
    print(f"Mode: {'DRY-RUN (Simulasi - No Changes)' if is_dry_run else 'EXECUTE (Modifikasi Nyata)'}")
    print(f"Target DB: {DB_PATH.resolve()} ({initial_size_mb:.2f} MB)")
    print("=" * 70)

    # 1. Connect and perform wal_checkpoint(TRUNCATE) before anything else
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA busy_timeout = 10000;")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")

    c = conn.cursor()

    # Get test user ID
    c.execute("SELECT id FROM users WHERE email = ?;", (TEST_USER_EMAIL,))
    test_user_row = c.fetchone()
    test_user_id = test_user_row[0] if test_user_row else None

    # Fetch all projects
    c.execute("SELECT id, title, slug, owner_id, operational_stage, created_at FROM projects ORDER BY created_at ASC;")
    all_projects = c.fetchall()

    preserved_projects: list[tuple] = []
    projects_to_delete: list[tuple] = []

    for p in all_projects:
        pid, title, slug, owner_id, stage, created_at = p
        title_stripped = title.strip()

        # Rule 1: Always preserve whitelist titles
        if title_stripped in WHITELIST_TITLES:
            preserved_projects.append(p)
            continue

        # Rule 2: If owner is NOT the test user (e.g. Nur Kholisah or other accounts), PRESERVE
        if owner_id != test_user_id:
            preserved_projects.append(p)
            continue

        # Otherwise, this is a test project created by pytest / test user
        projects_to_delete.append(p)

    print(f"\n[1] TOTAL PROYEK DI DATABASE SEBELUM CLEANUP: {len(all_projects)}")
    print(f"    - Proyek yang akan DIPERTAHANKAN : {len(preserved_projects)}")
    print(f"    - Proyek dummy test DIHAPUS     : {len(projects_to_delete)}")

    print("\n[2] DAFTAR LENGKAP PROYEK YANG AKAN DIPERTAHANKAN:")
    print("-" * 70)
    for idx, p in enumerate(preserved_projects, 1):
        pid, title, slug, owner_id, stage, created_at = p
        c.execute("SELECT email FROM users WHERE id = ?;", (owner_id,))
        u_email = (c.fetchone() or ("Unknown",))[0]
        print(f"  {idx:2d}. [{title}] (Stage {stage}) | Owner: {u_email} | Slug: {slug}")
    print("-" * 70)

    # Check flow_image_jobs count
    delete_ids = [p[0] for p in projects_to_delete]
    delete_ids_set = set(delete_ids)

    c.execute("SELECT count(*) FROM flow_image_jobs;")
    total_flow_jobs = c.fetchone()[0]

    c.execute("SELECT count(*) FROM flow_image_jobs WHERE project_id IS NOT NULL;")
    flow_with_proj = c.fetchone()[0]

    print(f"\n[3] STATUS FLOW IMAGE JOBS:")
    print(f"    - Total Flow Image Jobs       : {total_flow_jobs}")
    print(f"    - Jobs dengan project_id      : {flow_with_proj}")

    if is_dry_run:
        print("\n" + "=" * 70)
        print("SIMULASI SELESAI (DRY-RUN). Tidak ada perubahan yang ditulis ke database.")
        print("Untuk mengeksekusi pembersihan nyata, jalankan:")
        print("    python scripts/cleanup_dummy_projects.py --execute")
        print("=" * 70)
        conn.close()
        return

    # 4. EXECUTION MODE
    print("\n[4] MEMULAI PROSES PEMBERSIHAN NYATA...")
    conn.close()

    # Step A: Timestamped Backup
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = Path(f"data/movieai.db.bak_{timestamp}")
    shutil.copy2(DB_PATH, backup_path)
    print(f"  -> Backup database aman berhasil dibuat di: {backup_path.resolve()} ({backup_path.stat().st_size / (1024*1024):.2f} MB)")

    # Step B: Reconnect with foreign keys enabled
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA busy_timeout = 30000;")

    # Ensure foreign key indexes exist to prevent O(N^2) table scans during cascade delete
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_scenes_project_id ON scenes (project_id);",
        "CREATE INDEX IF NOT EXISTS idx_shots_scene_id ON shots (scene_id);",
        "CREATE INDEX IF NOT EXISTS idx_characters_project_id ON characters (project_id);",
        "CREATE INDEX IF NOT EXISTS idx_character_states_char_id ON character_states (character_id);",
        "CREATE INDEX IF NOT EXISTS idx_assets_project_id ON assets (project_id);",
        "CREATE INDEX IF NOT EXISTS idx_bibles_project_id ON master_production_bibles (project_id);",
        "CREATE INDEX IF NOT EXISTS idx_members_project_id ON project_members (project_id);",
        "CREATE INDEX IF NOT EXISTS idx_prompt_specs_shot_id ON prompt_specifications (shot_id);",
        "CREATE INDEX IF NOT EXISTS idx_prod_jobs_shot_id ON production_jobs (shot_id);",
        "CREATE INDEX IF NOT EXISTS idx_qc_reports_shot_id ON qc_reports (shot_id);",
    ]
    for idx_sql in indexes:
        conn.execute(idx_sql)
    conn.commit()

    conn.execute("PRAGMA foreign_keys = ON;")
    c = conn.cursor()

    # Step C: Clean orphan flow_image_jobs
    if delete_ids:
        placeholders = ",".join("?" for _ in delete_ids)
        c.execute(f"DELETE FROM flow_image_jobs WHERE project_id IN ({placeholders});", delete_ids)
        deleted_flow = c.rowcount
        print(f"  -> Berhasil menghapus {deleted_flow} baris flow_image_jobs milik proyek dummy.")

        # Clean any remaining orphan flow_image_jobs where project_id does not exist
        c.execute("DELETE FROM flow_image_jobs WHERE project_id IS NOT NULL AND project_id NOT IN (SELECT id FROM projects);")
        deleted_orphan = c.rowcount
        if deleted_orphan > 0:
            print(f"  -> Berhasil membersihkan {deleted_orphan} baris flow_image_jobs orphan tambahan.")

    # Step D: Delete test projects (foreign keys cascade will automatically clean scenes, bibles, shots, assets, characters)
    if delete_ids:
        placeholders = ",".join("?" for _ in delete_ids)
        c.execute(f"DELETE FROM projects WHERE id IN ({placeholders});", delete_ids)
        deleted_projects_count = c.rowcount
        print(f"  -> Berhasil menghapus {deleted_projects_count} baris tabel projects beserta relasi cascaded-nya.")

    conn.commit()

    # Step E: WAL checkpoint and VACUUM
    print("  -> Menjalankan PRAGMA wal_checkpoint(TRUNCATE) dan VACUUM...")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    conn.execute("VACUUM;")
    conn.close()

    # Step F: Verify final state
    final_conn = sqlite3.connect(DB_PATH)
    final_c = final_conn.cursor()
    final_c.execute("SELECT count(*) FROM projects;")
    final_count = final_c.fetchone()[0]

    final_c.execute("SELECT id, title, operational_stage, owner_id FROM projects ORDER BY created_at ASC;")
    remaining_rows = final_c.fetchall()

    final_conn.close()

    final_size_bytes = DB_PATH.stat().st_size
    final_size_mb = final_size_bytes / (1024 * 1024)

    print("\n" + "=" * 70)
    print("PEMBERSIHAN SELESAI DENGAN SUKSES!")
    print(f"  - Ukuran Database Sebelum Cleanup : {initial_size_mb:.2f} MB")
    print(f"  - Ukuran Database Sesudah Cleanup : {final_size_mb:.2f} MB")
    print(f"  - Jumlah Proyek Sebelum Cleanup   : {len(all_projects)}")
    print(f"  - Jumlah Proyek Tersisa           : {final_count}")
    print("\nDAFTAR PROYEK AKTIF DI DATABASE PRODUCTION:")
    for idx, r in enumerate(remaining_rows, 1):
        print(f"    {idx:2d}. {r[1]} (Stage {r[2]}) [ID: {r[0]}]")
    print("=" * 70)


if __name__ == "__main__":
    main()
