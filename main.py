# compat.py (обязательный файл)
import sys
from types import ModuleType

class FakeCGI(ModuleType):
    def __getattr__(self, name):
        return None

sys.modules['cgi'] = FakeCGI('cgi')

# main.py
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
DB_NAME = "sent_lots.db"
CHECK_INTERVAL = 3600  # 1 час между проверками
REQUEST_DELAY = random.randint(10, 30)  # Случайная задержка

# Альтернативные источники данных
RSS_SOURCES = [
    "https://torgi.gov.ru/new/api/public/lotcards/rss?biddType=ZK",
    "https://torgi.gov.ru/opendata/7710349494-torgi/data.rss",
    "https://torgi.gov.ru/opendata/feed"
]

# Прокси-серверы (замените на реальные)
PROXY_LIST = [
    None,  # Прямое подключение
    {'http': 'http://proxy1.example.com:8080', 'https': 'http://proxy1.example.com:8080'},
    {'http': 'http://proxy2.example.com:8080', 'https': 'http://proxy2.example.com:8080'}
]

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Mozilla/5.0 (X11; Linux x86_64)'
]

# Настройка сессии
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
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'application/xml',
        'Accept-Language': 'ru-RU,ru;q=0.9',
        'Referer': 'https://torgi.gov.ru/'
    }

def safe_fetch_rss(url):
    """Безопасное получение RSS с ротацией прокси"""
    for proxy in PROXY_LIST:
        try:
            time.sleep(REQUEST_DELAY)
            headers = get_random_headers()
            
            logger.info(f"Пробуем подключиться через прокси: {proxy}")
            response = session.get(
                url,
                headers=headers,
                proxies=proxy,
                timeout=15
            )
            response.raise_for_status()
            
            return feedparser.parse(response.content)
        except Exception as e:
            logger.warning(f"Ошибка подключения: {str(e)}")
            continue
    
    logger.error("Все попытки подключения провалились")
    return None

def init_db():
    """Инициализация базы данных"""
    conn = None
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
        logger.error(f"Ошибка БД: {str(e)}")
    finally:
        if conn:
            conn.close()

def is_lot_sent(lot_id):
    """Проверка, был ли лот отправлен ранее"""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sent_lots WHERE id=?", (lot_id,))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка проверки лота: {str(e)}")
        return True
    finally:
        if conn:
            conn.close()

def mark_lot_sent(lot_id):
    """Пометка лота как отправленного"""
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sent_lots (id, sent_time) VALUES (?, ?)",
            (lot_id, datetime.now())
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка отметки лота: {str(e)}")
    finally:
        if conn:
            conn.close()

def send_to_telegram(title, link, description):
    """Отправка сообщения в Telegram"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        message = (
            f"🏷 *{title}*\n\n"
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
        logger.error(f"Ошибка отправки: {str(e)}")
        return False

def check_new_lots():
    """Проверка новых лотов"""
    logger.info("Начало проверки лотов...")
    
    for rss_url in RSS_SOURCES:
        feed = safe_fetch_rss(rss_url)
        if not feed or not feed.entries:
            continue
            
        logger.info(f"Найдено {len(feed.entries)} лотов из {rss_url}")
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
                logger.error(f"Ошибка обработки лота: {str(e)}")
                continue
        
        logger.info(f"Отправлено новых лотов: {new_lots}")
        return
    
    logger.error("Не удалось получить данные ни из одного источника")

if __name__ == "__main__":
    init_db()
    logger.info("Бот запущен. Ожидание первой проверки...")
    
    while True:
        try:
            check_new_lots()
            logger.info(f"Следующая проверка через {CHECK_INTERVAL//60} минут")
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Бот остановлен")
            break
        except Exception as e:
            logger.error(f"Критическая ошибка: {str(e)}")
            time.sleep(300)  # Пауза 5 минут при ошибках
