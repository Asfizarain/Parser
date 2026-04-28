import sqlite3
from datetime import datetime
from contextlib import contextmanager

class Database:
    def __init__(self, db_path="database.db"):
        self.db_path = db_path
        self.init_tables()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def init_tables(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица links
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    last_visited DATETIME,
                    status TEXT DEFAULT 'active',
                    keyword TEXT
                )
            ''')
            
            # Таблица products
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    link_id INTEGER UNIQUE,
                    name TEXT,
                    article TEXT,
                    url TEXT,
                    FOREIGN KEY (link_id) REFERENCES links(id)
                )
            ''')
            
            # Таблица reviews
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    variant TEXT,
                    text TEXT,
                    advantages TEXT,
                    disadvantages TEXT,
                    rating INTEGER,
                    date DATETIME,
                    FOREIGN KEY (product_id) REFERENCES products(product_id)
                )
            ''')
            
            # Таблица questions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    question_text TEXT,
                    answer_text TEXT,
                    date DATETIME,
                    FOREIGN KEY (product_id) REFERENCES products(product_id)
                )
            ''')
            
            # Таблица prices
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS prices (
                    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    price REAL,
                    fix_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products(product_id)
                )
            ''')
            
            # Таблица descriptions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS descriptions (
                    product_id INTEGER PRIMARY KEY,
                    full_description TEXT,
                    characteristics TEXT,
                    FOREIGN KEY (product_id) REFERENCES products(product_id)
                )
            ''')
    
    def add_link(self, url, keyword):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO links (url, status, keyword) VALUES (?, ?, ?)",
                    (url, 'active', keyword)
                )
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None
    
    def get_next_link(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, url FROM links 
                WHERE status = 'active' 
                ORDER BY 
                    CASE WHEN last_visited IS NULL THEN 0 ELSE 1 END,
                    last_visited ASC
                LIMIT 1
            ''')
            return cursor.fetchone()
    
    def update_link_status(self, link_id, status, last_visited=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if last_visited is None:
                last_visited = datetime.now()
            cursor.execute(
                "UPDATE links SET last_visited = ?, status = ? WHERE id = ?",
                (last_visited, status, link_id)
            )
    
    def save_product(self, link_id, product_data):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO products (link_id, name, article, url)
                VALUES (?, ?, ?, ?)
            ''', (link_id, product_data.get('name'), 
                  product_data.get('article'), product_data.get('url')))
            product_id = cursor.lastrowid
            
            # Сохраняем цену
            if product_data.get('price'):
                cursor.execute('''
                    INSERT INTO prices (product_id, price)
                    VALUES (?, ?)
                ''', (product_id, product_data['price']))
            
            # Сохраняем описание
            if product_data.get('description') or product_data.get('characteristics'):
                cursor.execute('''
                    INSERT INTO descriptions (product_id, full_description, characteristics)
                    VALUES (?, ?, ?)
                ''', (product_id, product_data.get('description'), 
                      product_data.get('characteristics')))
            
            # Сохраняем отзывы
            for review in product_data.get('reviews', []):
                cursor.execute('''
                    INSERT INTO reviews (product_id, variant, text, advantages, 
                                       disadvantages, rating, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (product_id, review.get('variant'), review.get('text'),
                      review.get('advantages'), review.get('disadvantages'),
                      review.get('rating'), review.get('date')))
            
            # Сохраняем вопросы
            for question in product_data.get('questions', []):
                cursor.execute('''
                    INSERT INTO questions (product_id, question_text, answer_text, date)
                    VALUES (?, ?, ?, ?)
                ''', (product_id, question.get('question'), 
                      question.get('answer'), question.get('date')))
            
            return product_id