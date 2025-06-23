import os
import time
import sqlite3
import logging
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from telegram import Bot
import random

# Конфигурация
TELEGRAM_TOKEN = "8064060634:AAGKtPIvf9R3oZS2dx2bqy0JMhJT_MBUI10"
TELEGRAM_CHANNEL = "@gordep_ru"
DB_NAME = "sent_lots.db"
CHECK_INTERVAL = 1800  # 30 минут
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Mozilla/5.0 (X11; Linux x86_64)'
]

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TorgiAPI:
    @staticmethod
    def get_rss():
        """Получение данных через несколько источников"""
        sources = [
            TorgiAPI._try_direct_api,
            TorgiAPI._try_opendata,
            TorgiAPI._try_alternative
        ]
        
        for source in sources:
            data = source()
            if data:
                return data
        return None

    @staticmethod
    def _try_direct_api():
        """Прямое обращение к API"""
        try:
            url = "https://torgi.gov.ru/new/api/public/lotcards/rss?biddType=ZK"
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.warning(f"Direct API failed: {str(e)}")
            return None

    @staticmethod
    def _try_opendata():
        """Через раздел открытых данных"""
        try:
            url = "https://torgi.gov.ru/opendata/7710349494-torgi/data.rss"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.warning(f"OpenData failed: {str(e)}")
            return None

    @staticmethod
    def _try_alternative():
        """Альтернативный источник"""
        try:
            url = "https://api.allorigins.win/get?url=https://torgi.gov.ru/new/api/public/lotcards/rss?biddType=ZK"
            response = requests.get(url, timeout=10)
            data = response.json()
            return data['contents'].encode('utf-8') if data['contents'] else None
        except Exception as e:
            logger.warning(f"Alternative failed: {str(e)}")
            return None

# ... (остальные функции init_db, is_lot_sent, mark_lot_sent остаются без изменений)

def parse_rss(xml_content):
    """Парсинг RSS с обработкой ошибок"""
    if not xml_content:
        return []
    
    try:
        soup = BeautifulSoup(xml_content, 'xml')
        items = soup.find_all('item')
        
        # Фильтрация дубликатов и невалидных записей
        valid_items = []
        for item in items:
            try:
                if item.title and item.link:
                    valid_items.append(item)
            except:
                continue
                
        return valid_items[:10]  # Не более 10 лотов
    except Exception as e:
        logger.error(f"Parse error: {str(e)}")
        return []

def send_to_telegram(title, link, description=""):
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
        logger.error(f"Telegram error: {str(e)}")
        return False

def check_new_lots():
    """Основная функция проверки"""
    logger.info("Checking for new lots...")
    
    # Получаем данные
    xml_content = TorgiAPI.get_rss()
    items = parse_rss(xml_content) if xml_content else []
    
    if not items:
        logger.warning("No valid lots found")
        return
    
    logger.info(f"Found {len(items)} lots")
    
    # Обработка лотов
    new_lots = 0
    for item in items:
        try:
            lot_id = item.guid.text if item.guid else item.link.text
            title = item.title.text
            link = item.link.text
            
            if not is_lot_sent(lot_id):
                if send_to_telegram(title, link):
                    mark_lot_sent(lot_id)
                    new_lots += 1
                    time.sleep(random.uniform(1, 3))  # Случайная задержка
        except Exception as e:
            logger.error(f"Lot processing error: {str(e)}")
    
    logger.info(f"Sent {new_lots} new lots")

if __name__ == "__main__":
    init_db()
    logger.info("Service started")
    
    while True:
        try:
            check_new_lots()
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Service stopped")
            break
        except Exception as e:
            logger.error(f"Main loop error: {str(e)}")
            time.sleep(300)
