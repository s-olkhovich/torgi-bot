# main.py
import compat  # Должен быть первым импортом!
import feedparser
from telegram import Bot
import sqlite3
from datetime import datetime
import time
import logging

# Настройки
TELEGRAM_TOKEN = "8064060634:AAGKtPIvf9R3oZS2dx2bqy0JMhJT_MBUI10"
TELEGRAM_CHANNEL = "@gordep_ru"
RSS_URL = "https://torgi.gov.ru/new/api/public/lotcards/rss?biddType=ZK"
DB_NAME = "sent_lots.db"

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def init_db():
    """Инициализация базы данных"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_lots (
                id TEXT PRIMARY KEY,
                sent_time TIMESTAMP
            )
        ''')
        conn.commit()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка БД: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def is_lot_sent(lot_id):
    """Проверка, был ли лот отправлен"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sent_lots WHERE id=?", (lot_id,))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка проверки лота: {e}")
        return True
    finally:
        if 'conn' in locals():
            conn.close()

def mark_lot_sent(lot_id):
    """Пометка лота как отправленного"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sent_lots (id, sent_time) VALUES (?, ?)",
            (lot_id, datetime.now())
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка отметки лота: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def send_to_telegram(title, link, description):
    """Отправка сообщения в Telegram"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        message = (
            f"🏷 **{title}**\n\n"
            f"📄 Описание: {description}\n\n"
            f"🔗 [Ссылка на лот]({link})"
        )
        bot.send_message(
            chat_id=TELEGRAM_CHANNEL,
            text=message,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        return False

def check_new_lots():
    """Проверка новых лотов"""
    logger.info("Проверяем новые лоты...")
    try:
        feed = feedparser.parse(RSS_URL)
        new_lots = 0
        
        for entry in feed.entries:
            lot_id = entry.get("id", entry.link)
            if not is_lot_sent(lot_id):
                success = send_to_telegram(
                    entry.title,
                    entry.link,
                    entry.get("description", "Нет описания")
                )
                if success:
                    mark_lot_sent(lot_id)
                    new_lots += 1
                    time.sleep(1)  # Задержка между отправками
        
        logger.info(f"Найдено новых лотов: {new_lots}")
    except Exception as e:
        logger.error(f"Ошибка при проверке лотов: {e}")

if __name__ == "__main__":
    init_db()
    while True:
        check_new_lots()
        time.sleep(1800)  # Проверка каждые 30 минут
