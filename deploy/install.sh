#!/usr/bin/env bash
# Botni Ubuntu serverga o'rnatadi yoki yangilaydi. root sifatida ishga tushiring:
#   bash install.sh
# Birinchi o'rnatishda BOT_TOKEN va ADMIN_IDS so'raladi (yoki oldindan export qiling).
set -euo pipefail

REPO="https://github.com/octavvos/Yuklaydi_Bot.git"
APP_DIR="/opt/Yuklaydi_Bot"
APP_USER="yuklaydi"
SERVICE="yuklaydi-bot"

echo "==> Paketlar o'rnatilmoqda"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git python3 python3-venv ffmpeg

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
