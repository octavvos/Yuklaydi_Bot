import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
# Adminlar Telegram ID lari, vergul bilan: ADMIN_IDS=111111,222222
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()}
COOKIES_FILE = os.getenv("COOKIES_FILE")  # ixtiyoriy: Instagram/YouTube uchun cookies.txt
PROXY = os.getenv("PROXY")  # ixtiyoriy: masalan http://127.0.0.1:8080 yoki socks5://127.0.0.1:1080
DB_PATH = os.getenv("DB_PATH", "bot.db")
