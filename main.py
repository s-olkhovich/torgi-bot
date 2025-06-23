import os
import time
import sqlite3
import logging
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from telegram import Bot

# Настройки
TELEGRAM_TOKEN = "8064060634:AAGKtPIvf9R3oZS2dx2bqy0JMhJT_MBUI10"
TELEGRAM_CHANNEL = "@gordep_ru"
DB_NAME = "sent_lots.db"
CHECK_INTERVAL = 1800  # 30 минут
USER_AGENT = "Mozilla/5.0 (compatible; TorgiGovBot/1.0; +http://example.com/bot)"

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
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

def get_rss_feed():
    """Безопасное получение RSS с таймаутами"""
    try:
        # Упрощенный URL без лишних параметров
        url = "https://torgi.gov.ru/new/api/public/lotcards/rss?biddType=ZK"
        
        response = requests.get(
            url,
            headers={'User-Agent': USER_AGENT},
            timeout=10  # Уменьшенный таймаут
        )
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"Ошибка запроса: {e}")
        return None

def parse_rss_feed(xml_content):
    """Парсинг RSS с обработкой ошибок"""
    if not xml_content:
        return []
    
    try:
        soup = BeautifulSoup(xml_content, 'xml')
        return soup.find_all('item')[:5]  # Берем только первые 5 лотов
    except Exception as e:
        logger.error(f"Ошибка парсинга: {e}")
        return []

# ... (функции is_lot_sent, mark_lot_sent остаются без изменений)

def send_to_telegram(title, link, description):
    """Улучшенная отправка в Telegram"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        message = (
            f"🏷 *{title}*\n\n"
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
        logger.error(f"Ошибка Telegram: {e}")
        return False

def check_new_lots():
    """Проверка лотов с улучшенной обработкой ошибок"""
    logger.info("Начало проверки лотов...")
    
    # Получаем данные
    xml_content = get_rss_feed()
    items = parse_rss_feed(xml_content)
    
    if not items:
        logger.warning("Не удалось получить лоты")
        return
    
    logger.info(f"Найдено {len(items)} лотов")
    
    # Обработка лотов
    new_lots = 0
    for item in items:
        try:
            lot_id = item.guid.text if item.guid else item.link.text
            if not is_lot_sent(lot_id):
                if send_to_telegram(
                    item.title.text,
                    item.link.text,
                    item.description.text if item.description else ""
                ):
                    mark_lot_sent(lot_id)
                    new_lots += 1
                    time.sleep(1)  # Задержка между отправками
        except Exception as e:
            logger.error(f"Ошибка обработки лота: {e}")
    
    logger.info(f"Успешно отправлено: {new_lots}")

if __name__ == "__main__":
    init_db()
    logger.info("Бот запущен. Ожидание первой проверки...")
    
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
