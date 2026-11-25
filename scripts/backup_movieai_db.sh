#!/usr/bin/env bash
set -euo pipefail

DB_PATH="/home/ubuntu/MovieAIProducer/data/movieai.db"
BACKUP_DIR="/home/ubuntu/db_backups"
RETENTION_DAYS=30
LOCK_FILE="${BACKUP_DIR}/.backup.lock"

mkdir -p "${BACKUP_DIR}"
chmod 750 "${BACKUP_DIR}"

if [[ ! -f "${DB_PATH}" ]]; then
  echo "[ERROR] $(date -Is) Database file not found: ${DB_PATH}" >&2
  exit 1
fi

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "[WARN] $(date -Is) Another backup instance is already running." >&2
  exit 0
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
TMP_SQLITE="${BACKUP_DIR}/.movieai-${TIMESTAMP}.tmp.sqlite3"
FINAL_ARCHIVE="${BACKUP_DIR}/movieai-${TIMESTAMP}.sqlite3.gz"

cleanup() {
  rm -f "${TMP_SQLITE}" "${TMP_SQLITE}.gz"
}
trap cleanup EXIT

# Use SQLite online backup API so WAL transactions are safely included
sqlite3 "${DB_PATH}" ".timeout 5000" ".backup '${TMP_SQLITE}'"

INTEGRITY="$(sqlite3 "${TMP_SQLITE}" "PRAGMA integrity_check;")"
if [[ "${INTEGRITY}" != "ok" ]]; then
  echo "[ERROR] $(date -Is) Integrity check failed: ${INTEGRITY}" >&2
  exit 1
fi

gzip -9 "${TMP_SQLITE}"
mv "${TMP_SQLITE}.gz" "${FINAL_ARCHIVE}"
chmod 640 "${FINAL_ARCHIVE}"

# Prune backups older than RETENTION_DAYS
find "${BACKUP_DIR}" -maxdepth 1 -type f -name "movieai-*.sqlite3.gz" -mtime +"${RETENTION_DAYS}" -delete

SIZE_BYTES="$(stat -c%s "${FINAL_ARCHIVE}")"
echo "[OK] $(date -Is) Created ${FINAL_ARCHIVE} (${SIZE_BYTES} bytes, integrity=ok)"
