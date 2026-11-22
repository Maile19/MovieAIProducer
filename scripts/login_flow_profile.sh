#!/usr/bin/env bash
set -e

# ==============================================================================
# Helper Login Profil Google Flow (1 - 6) via noVNC (Port 6080)
# ==============================================================================

if [ -z "$1" ]; then
    echo "============================================================"
    echo "Penggunaan: $0 <nomor_akun_1_sampai_6>"
    echo "Contoh    : $0 1"
    echo "============================================================"
    exit 1
fi

ACCOUNT_NUM="$1"
if ! [[ "$ACCOUNT_NUM" =~ ^[1-6]$ ]]; then
    echo "Error: Nomor akun harus berupa angka antara 1 sampai 6."
    exit 1
fi

PROFILE_DIR="/opt/flow-profiles/akun_${ACCOUNT_NUM}"
mkdir -p "$PROFILE_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

# Baca konfigurasi proxy dari .env jika ada
PROXY_SERVER=""
if [ -f "$ENV_FILE" ]; then
    # Cari FLOW_SOCKS5_PROXY atau SOCKS5_PROXY
    PROXY_VAL=$(grep -E "^(FLOW_SOCKS5_PROXY|SOCKS5_PROXY)=" "$ENV_FILE" | head -n 1 | cut -d '=' -f2- | tr -d '"' | tr -d "'" | tr -d '[:space:]')
    if [ -n "$PROXY_VAL" ]; then
        PROXY_SERVER="$PROXY_VAL"
    fi
fi

echo "============================================================"
echo ">> Menyiapkan sesi login untuk Akun #${ACCOUNT_NUM}..."
echo ">> Direktori Profil: ${PROFILE_DIR}"
if [ -n "$PROXY_SERVER" ]; then
    echo ">> Proxy Server    : ${PROXY_SERVER}"
else
    echo ">> Proxy Server    : Direct (Tidak ada proxy yang dikonfigurasi di .env)"
fi
echo "============================================================"

# 1. Hentikan sementara flow-image-worker jika sedang berjalan
if systemctl is-active --quiet flow-image-worker.service; then
    echo ">> Menghentikan sementara flow-image-worker.service..."
    sudo systemctl stop flow-image-worker.service || true
fi

# Pastikan Xvfb :99 aktif
if ! systemctl is-active --quiet xvfb-flow.service; then
    echo ">> Menjalankan xvfb-flow.service..."
    sudo systemctl start xvfb-flow.service || true
    sleep 1
fi

export DISPLAY=:99

# Bersihkan lock / proses x11vnc, websockify, fluxbox lama jika tertinggal
pkill -f "x11vnc.*:99" || true
pkill -f "websockify.*6080" || true
pkill -f "fluxbox" || true
sleep 1

# 2. Jalankan fluxbox, x11vnc (127.0.0.1:5900), dan websockify (127.0.0.1:6080)
echo ">> Menjalankan Window Manager (fluxbox)..."
fluxbox > /dev/null 2>&1 &
FLUXBOX_PID=$!

echo ">> Menjalankan VNC Server (x11vnc pada 127.0.0.1:5900)..."
x11vnc -display :99 -listen 127.0.0.1 -rfbport 5900 -nopw -forever -shared > /tmp/x11vnc.log 2>&1 &
X11VNC_PID=$!

echo ">> Menjalankan noVNC Websockify (127.0.0.1:6080)..."
websockify --web /usr/share/novnc 127.0.0.1:6080 127.0.0.1:5900 > /tmp/websockify.log 2>&1 &
WEBSOCKIFY_PID=$!

# Handler Cleanup saat script dihentikan (Ctrl+C atau SIGTERM)
cleanup() {
    echo ""
    echo "============================================================"
    echo ">> Menerima sinyal keluar, membersihkan sesi login..."
    echo "============================================================"
    if [ -n "$CHROME_PID" ] && kill -0 "$CHROME_PID" 2>/dev/null; then
        echo ">> Menutup Google Chrome secara graceful agar cookie tersimpan..."
        kill -TERM "$CHROME_PID" 2>/dev/null || true
        for i in 1 2 3; do
            if ! kill -0 "$CHROME_PID" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        if kill -0 "$CHROME_PID" 2>/dev/null; then
            echo ">> Chrome belum berhenti setelah 3 detik, mengirim SIGKILL..."
            kill -9 "$CHROME_PID" 2>/dev/null || true
        fi
    fi
    if [ -n "$WEBSOCKIFY_PID" ] && kill -0 "$WEBSOCKIFY_PID" 2>/dev/null; then
        kill "$WEBSOCKIFY_PID" 2>/dev/null || true
    fi
    if [ -n "$X11VNC_PID" ] && kill -0 "$X11VNC_PID" 2>/dev/null; then
        kill "$X11VNC_PID" 2>/dev/null || true
    fi
    if [ -n "$FLUXBOX_PID" ] && kill -0 "$FLUXBOX_PID" 2>/dev/null; then
        kill "$FLUXBOX_PID" 2>/dev/null || true
    fi

    # Pastikan worker kembali aktif jika service ada
    if systemctl list-unit-files | grep -q "flow-image-worker.service"; then
        echo ">> Menghidupkan kembali flow-image-worker.service..."
        sudo systemctl start flow-image-worker.service || true
    fi
    echo ">> Selesai. Profil Akun #${ACCOUNT_NUM} tersimpan rapi."
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# 3. Jalankan Google Chrome Stable
CHROME_ARGS=(
    "--user-data-dir=${PROFILE_DIR}"
    "--disable-blink-features=AutomationControlled"
    "--no-first-run"
    "--no-default-browser-check"
    "--window-size=1920,1080"
    "--start-maximized"
)

if [ -n "$PROXY_SERVER" ]; then
    CHROME_ARGS+=("--proxy-server=${PROXY_SERVER}")
fi

echo ">> Membuka Google Chrome di DISPLAY=:99..."
/usr/bin/google-chrome-stable "${CHROME_ARGS[@]}" "https://labs.google/fx/tools/flow" > /tmp/chrome_flow_login.log 2>&1 &
CHROME_PID=$!

echo ""
echo "============================================================"
echo "         INSTRUKSI AKSES LOGIN PROFIL GOOGLE FLOW           "
echo "============================================================"
echo "1. Di komputer lokal Anda, buat SSH tunnel:"
echo "   ssh -N -L 6080:127.0.0.1:6080 ubuntu@<IP_VPS>"
echo ""
echo "2. Buka browser di komputer lokal:"
echo "   http://127.0.0.1:6080/vnc.html"
echo ""
echo "3. Klik 'Connect' (tanpa password). Anda akan melihat Google Chrome."
echo "4. Silakan login akun Google Anda di web Google Flow hingga selesai."
echo "5. Setelah login selesai, kembali ke terminal ini dan tekan Ctrl + C."
echo "============================================================"
echo "Menunggu Anda menyelesaikan proses login (Tekan Ctrl+C untuk selesai)..."

wait "$CHROME_PID" 2>/dev/null || true
