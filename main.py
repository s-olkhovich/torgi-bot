import requests
from bs4 import BeautifulSoup
from telegram import Bot
import sqlite3
from datetime import datetime
import time
import os
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

def parse_rss_with_bs(url):
    """Альтернативный парсер RSS через BeautifulSoup"""
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'xml')
        return soup.find_all('item')
    except Exception as e:
        logger.error(f"Ошибка парсинга RSS: {e}")
        return []

# Остальные функции (init_db, is_lot_sent, mark_lot_sent, send_to_telegram) 
# остаются без изменений, как в вашем исходном коде

def check_new_lots():
    """Проверка новых лотов с использованием BeautifulSoup"""
    logger.info("Проверяем новые лоты...")
    items = parse_rss_with_bs(RSS_URL)
    logger.info(f"Найдено лотов: {len(items)}")

    new_lots = 0
    for item in items:
        try:
            lot_id = item.guid.text if item.guid else item.link.text
            if not is_lot_sent(lot_id):
                title = item.title.text
                link = item.link.text
                description = item.description.text if item.description else "Нет описания"
                
                if send_to_telegram(title, link, description):
                    mark_lot_sent(lot_id)
                    new_lots += 1
                    time.sleep(1)
        except Exception as e:
            logger.error(f"Ошибка обработки лота: {e}")

    logger.info(f"Отправлено новых лотов: {new_lots}")

if __name__ == "__main__":
    init_db()
    while True:
        check_new_lots()
        time.sleep(1800)
