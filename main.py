import feedparser
from telegram import Bot
import sqlite3
from datetime import datetime
import time
import logging
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import random

# Настройки
TELEGRAM_TOKEN = "8064060634:AAGKtPIvf9R3oZS2dx2bqy0JMhJT_MBUI10"
TELEGRAM_CHANNEL = "@gordep_ru"
RSS_URL = "https://torgi.gov.ru/new/api/public/lotcards/rss?biddType=ZK"
DB_NAME = "sent_lots.db"
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
]

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Настройка сессии с повторами
session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504, 429]
)
session.mount('https://', HTTPAdapter(max_retries=retries))

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'application/xml',
        'Accept-Language': 'ru-RU,ru;q=0.9',
    }

def safe_feed_parse(url):
    """Безопасный парсинг RSS с обработкой ошибок"""
    try:
        headers = get_random_headers()
        response = session.get(
            url,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        return feedparser.parse(response.content)
    except Exception as e:
        logger.error(f"Ошибка при запросе RSS: {str(e)}")
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
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

def is_lot_sent(lot_id):
    """Проверка, был ли лот отправлен ранее"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sent_lots WHERE id=?", (lot_id,))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка проверки лота: {str(e)}")
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
        logger.error(f"Ошибка отметки лота: {str(e)}")
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
        logger.error(f"Ошибка отправки в Telegram: {str(e)}")
        return False

def check_new_lots():
    """Проверка новых лотов с защитой от блокировки"""
    try:
        # Случайная задержка от 5 до 15 секунд
        delay = random.randint(5, 15)
        time.sleep(delay)
        
        logger.info("Начало проверки новых лотов...")
        feed = safe_feed_parse(RSS_URL)
        
        # Логирование для диагностики
        logger.info(f"Статус RSS: {getattr(feed, 'status', 'N/A')}")
        logger.info(f"Найдено лотов: {len(feed.entries)}")
        
        new_lots = 0
        for entry in feed.entries:
            try:
                lot_id = entry.get('id', entry.link)
                if not is_lot_sent(lot_id):
                    if send_to_telegram(
                        entry.title,
                        entry.link,
                        entry.get('description', 'Нет описания')
                    ):
                        mark_lot_sent(lot_id)
                        new_lots += 1
                        # Задержка между отправками
                        time.sleep(random.uniform(1.0, 3.0))
            except Exception as e:
                logger.error(f"Ошибка обработки лота: {str(e)}")
                continue
                
        logger.info(f"Успешно отправлено новых лотов: {new_lots}")
        return True
        
    except Exception as e:
        logger.error(f"Критическая ошибка при проверке лотов: {str(e)}")
        return False

if __name__ == "__main__":
    init_db()
    logger.info("Бот запущен")
    
    while True:
        try:
            if not check_new_lots():
                # Увеличенная задержка при ошибках
                time.sleep(60)
            
            # Основной интервал проверки (30 минут)
            time.sleep(1800)
            
        except KeyboardInterrupt:
            logger.info("Бот остановлен")
            break
        except Exception as e:
            logger.error(f"Необработанная ошибка: {str(e)}")
            time.sleep(300)  # Пауза 5 минут при критических ошибках
