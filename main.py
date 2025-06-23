import os
import time
import sqlite3
import logging
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from telegram import Bot

# Ваши данные (замените на реальные перед деплоем)
TELEGRAM_TOKEN = "8064060634:AAGKtPIvf9R3oZS2dx2bqy0JMhJT_MBUI10"
TELEGRAM_CHANNEL = "@gordep_ru"
RSS_URL = "https://torgi.gov.ru/new/api/public/lotcards/rss?biddType=ZK"

# Настройки
DB_NAME = "sent_lots.db"
CHECK_INTERVAL = 1800  # 30 минут
USER_AGENT = "Mozilla/5.0 (compatible; TorgiGovBot/1.0)"

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

def init_db():
    """Инициализация базы данных SQLite"""
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
        logger.info("База данных готова")
    except Exception as e:
        logger.error(f"Ошибка БД: {e}")
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
        logger.error(f"Ошибка проверки лота: {e}")
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
        logger.error(f"Ошибка отметки лота: {e}")
    finally:
        if conn:
            conn.close()

def send_to_telegram(title, link, description):
    """Отправка сообщения в Telegram"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        message = (
            f"🏷 <b>{title}</b>\n\n"
            f"📄 Описание: {description}\n\n"
            f"🔗 <a href='{link}'>Ссылка на лот</a>"
        )
        bot.send_message(
            chat_id=TELEGRAM_CHANNEL,
            text=message,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        return False

def get_rss_feed():
    """Получение RSS с обработкой ошибок"""
    try:
        response = requests.get(
            RSS_URL,
            headers={'User-Agent': USER_AGENT},
            timeout=15
        )
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса RSS: {e}")
        return None

def parse_rss_feed(xml_content):
    """Парсинг RSS ленты"""
    if not xml_content:
        return []
    
    try:
        soup = BeautifulSoup(xml_content, 'xml')
        return soup.find_all('item')
    except Exception as e:
        logger.error(f"Ошибка парсинга RSS: {e}")
        return []

def check_new_lots():
    """Основная функция проверки лотов"""
    logger.info("Проверка новых лотов...")
    
    # Получаем и парсим RSS
    xml_content = get_rss_feed()
    items = parse_rss_feed(xml_content)
    
    if not items:
        logger.warning("Лоты не найдены или ошибка парсинга")
        return
    
    logger.info(f"Найдено лотов: {len(items)}")
    
    # Ограничиваем количество за одну проверку
    new_lots = 0
    for item in items[:10]:  # Не более 10 за раз
        try:
            lot_id = item.guid.text if item.guid else item.link.text
            if not is_lot_sent(lot_id):
                title = item.title.text if item.title else "Без названия"
                link = item.link.text if item.link else "#"
                description = item.description.text if item.description else "Нет описания"
                
                if send_to_telegram(title, link, description):
                    mark_lot_sent(lot_id)
                    new_lots += 1
                    time.sleep(2)  # Задержка между отправками
        except Exception as e:
            logger.error(f"Ошибка обработки лота: {e}")
    
    logger.info(f"Отправлено новых лотов: {new_lots}")

if __name__ == "__main__":
    init_db()
    logger.info("Бот запущен с настройками:")
    logger.info(f"Telegram канал: {TELEGRAM_CHANNEL}")
    logger.info(f"RSS URL: {RSS_URL}")
    
    while True:
        try:
            check_new_lots()
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Бот остановлен")
            break
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
            time.sleep(300)  # Пауза при ошибках
