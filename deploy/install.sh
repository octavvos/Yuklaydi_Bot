#!/usr/bin/env bash
# Botni Ubuntu serverga o'rnatadi yoki yangilaydi. root sifatida ishga tushiring:
#   bash install.sh
# Birinchi o'rnatishda BOT_TOKEN va ADMIN_IDS so'raladi (yoki oldindan export qiling).
# 50 MB dan katta fayllar uchun TELEGRAM_API_ID va TELEGRAM_API_HASH ham so'raladi
# (my.telegram.org -> API development tools). Enter bosilsa, bu qadam o'tkazib yuboriladi.
set -euo pipefail

REPO="https://github.com/octavvos/yuklaydi-bot.git"
APP_DIR="/opt/Yuklaydi_Bot"
APP_USER="yuklaydi"
SERVICE="yuklaydi-bot"
API_CONTAINER="telegram-bot-api"
API_URL="http://127.0.0.1:8081"

echo "==> Paketlar o'rnatilmoqda"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git python3 python3-venv ffmpeg curl unzip

echo "==> deno (yt-dlp YouTube uchun JS runtime)"
if ! command -v deno &>/dev/null; then
    # GitHub'dan: dl.deno.land ba'zi serverlardan juda sekin yuklanadi
    { curl -fsSL -m 300 -o /tmp/deno.zip \
        https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip \
        && unzip -oq /tmp/deno.zip -d /usr/local/bin && chmod +x /usr/local/bin/deno; } \
        || echo "⚠️  deno o'rnatilmadi, YouTube'da ba'zi formatlar chiqmasligi mumkin"
    rm -f /tmp/deno.zip
fi

echo "==> Bot uchun alohida foydalanuvchi"
id "$APP_USER" &>/dev/null || useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"

echo "==> Kod yuklanmoqda"
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull --ff-only
else
    git clone "$REPO" "$APP_DIR"
fi

echo "==> Python kutubxonalari"
[ -d "$APP_DIR/venv" ] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
    echo "==> .env yaratilmoqda"
    : "${BOT_TOKEN:=$(read -rp 'BOT_TOKEN: ' t && echo "$t")}"
    : "${ADMIN_IDS:=$(read -rp 'ADMIN_IDS (vergul bilan): ' a && echo "$a")}"
    cat > "$APP_DIR/.env" <<EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS
COOKIES_FILE=
PROXY=
DB_PATH=$APP_DIR/bot.db
EOF
fi

env_get() { grep -E "^$1=" "$APP_DIR/.env" | tail -n1 | cut -d= -f2- || true; }

if [ -z "$(env_get TELEGRAM_API_URL)" ]; then
    echo "==> Lokal Telegram Bot API server (50 MB dan katta fayllar uchun, 2000 MB gacha)"
    [ -n "${TELEGRAM_API_ID:-}" ] || read -rp "TELEGRAM_API_ID (o'tkazib yuborish uchun Enter): " TELEGRAM_API_ID || true
    if [ -n "${TELEGRAM_API_ID:-}" ]; then
        [ -n "${TELEGRAM_API_HASH:-}" ] || read -rp "TELEGRAM_API_HASH: " TELEGRAM_API_HASH || true
    fi
    if [ -n "${TELEGRAM_API_ID:-}" ] && [ -n "${TELEGRAM_API_HASH:-}" ]; then
        command -v docker &>/dev/null || DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io
        systemctl enable --now docker >/dev/null
        docker rm -f "$API_CONTAINER" &>/dev/null || true
        docker run -d --name "$API_CONTAINER" --restart always \
            -p 127.0.0.1:8081:8081 \
            -e TELEGRAM_API_ID="$TELEGRAM_API_ID" -e TELEGRAM_API_HASH="$TELEGRAM_API_HASH" -e TELEGRAM_LOCAL=1 \
            -v telegram-bot-api-data:/var/lib/telegram-bot-api \
            aiogram/telegram-bot-api:latest >/dev/null 2>&1
        # Botni Telegram'ning umumiy serveridan chiqaramiz, aks holda xabarlar lokal serverga kelmasligi mumkin
        TOKEN="$(env_get BOT_TOKEN)"
        curl -fsS "https://api.telegram.org/bot$TOKEN/logOut" >/dev/null || true
        echo "TELEGRAM_API_URL=$API_URL" >> "$APP_DIR/.env"
        echo "Lokal server kutilmoqda..."
        for _ in $(seq 1 30); do curl -fsS "$API_URL/bot$TOKEN/getMe" &>/dev/null && break; sleep 2; done
    else
        echo "O'tkazib yuborildi: fayl chegarasi 50 MB bo'lib qoladi."
    fi
fi

chmod 600 "$APP_DIR/.env"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "==> systemd servis"
cat > "/etc/systemd/system/$SERVICE.service" <<EOF
[Unit]
Description=Yuklaydi Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python bot.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null
systemctl restart "$SERVICE"

sleep 5
systemctl --no-pager --lines=15 status "$SERVICE" || true
echo
echo "✅ Tayyor. Loglar: journalctl -u $SERVICE -f"
