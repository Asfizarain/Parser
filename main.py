import asyncio
import sys
import configparser
import argparse
import random
from pathlib import Path
from database import Database
from scraper import OzonScraper
from utils import setup_logging

# Определяем корневую директорию проекта
BASE_DIR = Path(__file__).parent

def load_keywords():
    """Загрузка ключевых слов из файла parser_list.txt"""
    keywords_file = BASE_DIR / "parser_list.txt"
    if not keywords_file.exists():
        print("Warning: parser_list.txt not found")
        return []
    with open(keywords_file, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def parse_args():
    parser = argparse.ArgumentParser(description='Ozon Parser')
    parser.add_argument('--rescan-catalog', action='store_true',
                        help='Rescan catalog for new links')
    parser.add_argument('--max-pages', type=int, default=100,
                        help='Maximum number of product pages to scrape')
    parser.add_argument('--headless', action='store_true',
                        help='Run browser in headless mode')
    return parser.parse_args()

async def scan_catalog(scraper, keywords, config, max_search_pages):
    """
    Сканирование каталога по ключевым словам:
    для каждого слова выполняется поиск на Ozon, собираются ссылки на товары.
    """
    logger = scraper.logger
    logger.info("Starting catalog scan for keywords: %s", keywords)
    
    for keyword in keywords:
        logger.info(f"Searching for keyword: {keyword}")
        # URL поиска
        search_url = f"https://www.ozon.ru/search/?text={keyword}"
        await scraper.page.goto(search_url, wait_until='networkidle', timeout=30000)
        
        # Небольшая задержка для имитации
        await asyncio.sleep(random.uniform(2, 4))
        
        page_num = 1
        while page_num <= max_search_pages:
            logger.info(f"Processing page {page_num} for '{keyword}'")
            
            # Ждём появления результатов (можно адаптировать селектор)
            try:
                await scraper.page.wait_for_selector('div[data-widget="searchResultsV2"]', timeout=10000)
            except:
                # Возможно, результатов нет или страница не загрузилась
                break
            
            # Селекторы для ссылок товаров (несколько вариантов)
            selectors = [
                'a.tile-hover-target',
                'a[data-testid="tile-link"]',
                'a[href*="/product/"]'
            ]
            product_links = set()
            for selector in selectors:
                links = await scraper.page.query_selector_all(selector)
                for link in links:
                    href = await link.get_attribute('href')
                    if href and '/product/' in href:
                        if href.startswith('/'):
                            href = f"https://www.ozon.ru{href}"
                        product_links.add(href)
            
            # Сохраняем найденные ссылки в БД
            for link in product_links:
                scraper.db.add_link(link, keyword)
            
            logger.info(f"Found {len(product_links)} products for '{keyword}' on page {page_num}")
            
            # Пытаемся перейти на следующую страницу
            next_button = await scraper.page.query_selector('a[data-testid="pagination-next"]')
            if next_button and await next_button.is_enabled():
                await next_button.click()
                await scraper.page.wait_for_load_state('networkidle')
                await asyncio.sleep(random.uniform(2, 4))
                page_num += 1
            else:
                break
        
        logger.info(f"Finished keyword '{keyword}', total pages processed: {page_num-1}")
    
    logger.info("Catalog scan completed")

async def main():
    args = parse_args()
    
    # Загрузка конфигурации
    config_path = BASE_DIR / "config.ini"
    config = configparser.ConfigParser()
    config.read(config_path)
    
    if args.headless:
        config.set('main', 'headless', 'true')
    if args.max_pages:
        # Можно переопределить max_pages для парсинга товаров
        max_pages_to_scrape = args.max_pages
    else:
        max_pages_to_scrape = config.getint('parser', 'max_pages', fallback=100)
    
    # Загрузка ключевых слов
    keywords = load_keywords()
    if not keywords:
        print("No keywords found in parser_list.txt. Exiting.")
        return
    
    # Настройка логов
    logger = setup_logging(BASE_DIR / "logs")
    logger.info("Starting Ozon Parser")
    
    # База данных – внутри BASE_DIR
    db_path = BASE_DIR / "database.db"
    db = Database(str(db_path))
    
    # Инициализация скрапера
    scraper = OzonScraper(config, db, logger)
    
    try:
        await scraper.init_browser()
        
        # Сканирование каталога, если указан флаг или в БД нет ссылок
        if args.rescan_catalog or not db.get_next_link():
            max_search_pages = config.getint('parser', 'max_search_pages', fallback=5)
            await scan_catalog(scraper, keywords, config, max_search_pages)
        
        # Основной цикл парсинга товаров
        pages_scraped = 0
        while pages_scraped < max_pages_to_scrape:
            link = db.get_next_link()
            if not link:
                logger.info("No more links to scrape")
                break
            
            success = await scraper.scrape_product(link['id'], link['url'])
            if success:
                pages_scraped += 1
                logger.info(f"Progress: {pages_scraped}/{max_pages_to_scrape}")
            else:
                logger.warning(f"Failed to scrape {link['url']}, moving to next")
            
            # Случайная пауза между товарами
            await asyncio.sleep(random.uniform(5, 15))
        
        logger.info(f"Scraping completed. Scraped {pages_scraped} pages")
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal. Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())