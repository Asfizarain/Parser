import asyncio
import random
import json
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from datetime import datetime
from utils import random_delay, human_like_mouse_movement

class OzonScraper:
    def __init__(self, config, db, logger):
        self.config = config
        self.db = db
        self.logger = logger
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
    
    async def init_browser(self):
        """Инициализация браузера с stealth-настройками"""
        self.playwright = await async_playwright().start()
        
        headless = self.config.getboolean('main', 'headless', fallback=False)
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        
        viewport_width = random.randint(
            self.config.getint('browser', 'viewport_width_min', fallback=1280),
            self.config.getint('browser', 'viewport_width_max', fallback=1920)
        )
        viewport_height = random.randint(
            self.config.getint('browser', 'viewport_height_min', fallback=720),
            self.config.getint('browser', 'viewport_height_max', fallback=1080)
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': viewport_width, 'height': viewport_height},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='ru-RU',
            timezone_id='Europe/Moscow',
            extra_http_headers={
                'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8'
            }
        )
        
        self.page = await self.context.new_page()
        
        # Скрываем признаки автоматизации
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """)
    
    async def scroll_page(self):
        """Плавная прокрутка страницы"""
        scrolls = random.randint(2, 5)
        for _ in range(scrolls):
            scroll_distance = random.randint(300, 800)
            await self.page.evaluate(f"window.scrollBy(0, {scroll_distance})")
            await asyncio.sleep(random.uniform(0.5, 1.5))
        if random.random() < 0.3:
            await self.page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(random.uniform(0.3, 0.8))
    
    async def random_click(self):
        """Случайный клик по нерелевантным элементам (без перехода назад)"""
        if random.random() < 0.2:
            elements = await self.page.query_selector_all('a, button, div[role="button"]')
            if elements:
                random_element = random.choice(elements)
                try:
                    await random_element.click()
                    await asyncio.sleep(random.uniform(1, 2))
                    # Если открылось модальное окно – закроем нажатием Escape
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(random.uniform(0.5, 1))
                except:
                    pass
    
    async def parse_product_page(self, url):
        """Парсинг страницы товара с ожиданием загрузки элементов"""
        product_data = {
            'url': url,
            'reviews': [],
            'questions': []
        }
        
        try:
            # Ждём загрузки хотя бы заголовка (10 секунд)
            await self.page.wait_for_selector('h1', timeout=10000)
            
            # Название товара
            name_selectors = [
                '[data-widget="webProductHeading"] h1',
                'h1[data-testid="product-title"]',
                '.r3k2k9.eh'
            ]
            for selector in name_selectors:
                element = await self.page.query_selector(selector)
                if element:
                    product_data['name'] = (await element.inner_text()).strip()
                    break
            
            # Артикул
            article_selectors = [
                '[data-testid="product-article"]',
                'div:has-text("Артикул") + div'
            ]
            for selector in article_selectors:
                element = await self.page.query_selector(selector)
                if element:
                    product_data['article'] = (await element.inner_text()).strip()
                    break
            
            # Цена (основная, без скидки)
            price_selectors = [
                '[data-testid="price"]',
                '.r1k3x3a.eh'
            ]
            for selector in price_selectors:
                element = await self.page.query_selector(selector)
                if element:
                    price_text = await element.inner_text()
                    price_text = price_text.replace('₽', '').replace(' ', '').replace(',', '.')
                    try:
                        product_data['price'] = float(price_text)
                    except:
                        pass
                    break
            
            # Описание
            desc_selectors = [
                '[data-testid="product-description"]',
                '.r3s2k9.eh'
            ]
            for selector in desc_selectors:
                element = await self.page.query_selector(selector)
                if element:
                    product_data['description'] = (await element.inner_text()).strip()
                    break
            
            # Характеристики (если есть таблица)
            char_section = await self.page.query_selector('[data-testid="product-attributes"]')
            if char_section:
                characteristics = {}
                rows = await char_section.query_selector_all('.characteristic-row')
                for row in rows:
                    key = await row.query_selector('.key')
                    value = await row.query_selector('.value')
                    if key and value:
                        characteristics[(await key.inner_text()).strip()] = (await value.inner_text()).strip()
                product_data['characteristics'] = json.dumps(characteristics, ensure_ascii=False)
            
            # Отзывы (первые 5)
            reviews_section = await self.page.query_selector('[data-testid="reviews-section"]')
            if reviews_section:
                review_items = await reviews_section.query_selector_all('.review-item')
                for review in review_items[:5]:
                    review_data = {}
                    rating_elem = await review.query_selector('[data-testid="rating"]')
                    if rating_elem:
                        aria = await rating_elem.get_attribute('aria-label')
                        # Пример: "Рейтинг: 4 из 5"
                        if aria and ':' in aria:
                            try:
                                review_data['rating'] = int(aria.split(':')[1].strip().split(' ')[0])
                            except:
                                pass
                    text_elem = await review.query_selector('.review-text')
                    if text_elem:
                        review_data['text'] = (await text_elem.inner_text()).strip()
                    adv_elem = await review.query_selector('.advantages')
                    if adv_elem:
                        review_data['advantages'] = (await adv_elem.inner_text()).strip()
                    disadv_elem = await review.query_selector('.disadvantages')
                    if disadv_elem:
                        review_data['disadvantages'] = (await disadv_elem.inner_text()).strip()
                    date_elem = await review.query_selector('.review-date')
                    if date_elem:
                        review_data['date'] = (await date_elem.inner_text()).strip()
                    product_data['reviews'].append(review_data)
            
            return product_data
            
        except Exception as e:
            self.logger.error(f"Error parsing product {url}: {e}")
            return None
    
    async def scrape_product(self, link_id, url):
        """Скрапинг одного товара"""
        self.logger.info(f"Scraping product: {url}")
        
        try:
            # Переход на страницу
            await self.page.goto(url, wait_until='networkidle', timeout=45000)
            
            # Случайная задержка
            min_delay = self.config.getfloat('main', 'min_delay', fallback=3)
            max_delay = self.config.getfloat('main', 'max_delay', fallback=20)
            await random_delay(min_delay, max_delay, async_mode=True)
            
            # Имитация человеческого поведения
            await self.scroll_page()
            await human_like_mouse_movement(self.page)
            await self.random_click()
            
            # Парсинг данных
            product_data = await self.parse_product_page(url)
            
            if product_data:
                self.db.save_product(link_id, product_data)
                self.db.update_link_status(link_id, 'active')
                self.logger.info(f"Successfully scraped product: {product_data.get('name', 'Unknown')}")
                return True
            else:
                self.db.update_link_status(link_id, 'blocked')
                return False
                
        except PlaywrightTimeout:
            self.logger.error(f"Timeout while loading {url}")
            self.db.update_link_status(link_id, 'blocked')
            return False
        except Exception as e:
            self.logger.error(f"Error scraping {url}: {e}")
            self.db.update_link_status(link_id, 'blocked')
            return False
    
    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()