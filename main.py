# compat.py (должен быть в том же каталоге)
import sys
from types import ModuleType

class FakeCGI(ModuleType):
    def __getattr__(self, name):
        return None

sys.modules['cgi'] = FakeCGI('cgi')

# main.py
import compat  # Должен быть первым импортом!
import feedparser
from telegram import Bot
import sqlite3
from datetime import datetime
import time
import logging
import random
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# Настройки
TELEGRAM_TOKEN = "8064060634:AAGKtPIvf9R3oZS2dx2bqy0JMhJT_MBUI10"
TELEGRAM_CHANNEL = "@gordep_ru"
RSS_URLS = [
    "https://torgi.gov.ru/new/api/public/lotcards/rss?biddType=ZK",
    "https://torgi.gov.ru/opendata/7710349494-torgi/data.rss"
]
DB_NAME = "sent_lots.db"
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Mozilla/5.0 (X11; Linux x86_64)'
]

# Настройка сессии с повторами
session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504, 429]
)
session.mount('https://', HTTPAdapter(max_retries=retries))

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def safe_feed_parse(url):
    """Безопасный парсинг RSS с обработкой ошибок"""
    try:
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        response = session.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return feedparser.parse(response.content)
    except Exception as e:
        logger.error(f"Ошибка запроса RSS: {e}")
        return feedparser.parse("")

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
    
    # Пробуем все доступные RSS-источники
    for rss_url in RSS_URLS:
        try:
            feed = safe_feed_parse(rss_url)
            if not feed.entries:
                continue
                
            new_lots = 0
            for entry in feed.entries[:10]:  # Ограничиваем 10 лотами
                try:
                    lot_id = entry.get("id", entry.link)
                    if not is_lot_sent(lot_id):
                        if send_to_telegram(
                            entry.title,
                            entry.link,
                            entry.get("description", "Нет описания")
                        ):
                            mark_lot_sent(lot_id)
                            new_lots += 1
                            time.sleep(random.uniform(1, 3))  # Случайная задержка
                except Exception as e:
                    logger.error(f"Ошибка обработки лота: {e}")
                    continue
            
            logger.info(f"Найдено новых лотов: {new_lots}")
            return  # Успешно обработали один источник
            
        except Exception as e:
            logger.error(f"Ошибка при обработке {rss_url}: {e}")
            continue
    
    logger.warning("Не удалось получить данные ни из одного источника")

if __name__ == "__main__":
    init_db()
    logger.info("Бот запущен")
    
    while True:
        try:
            check_new_lots()
            time.sleep(1800)  # Проверка каждые 30 минут
        except KeyboardInterrupt:
            logger.info("Бот остановлен")
            break
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
            time.sleep(300)  # Пауза при ошибках
