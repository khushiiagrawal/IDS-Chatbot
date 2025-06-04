import sqlite3
from datetime import datetime

class ConversationDatabase:
    def __init__(self):
        self.conn = sqlite3.connect('conversations.db')
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                role TEXT NOT NULL,
                content TEXT NOT NULL
            )
        ''')
        self.conn.commit()
    
    def add_message(self, session_id, role, content):
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)',
            (session_id, role, content)
        )
        self.conn.commit()
    
    def get_conversation_history(self, session_id):
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT role, content, timestamp FROM conversations WHERE session_id = ? ORDER BY timestamp ASC',
            (session_id,)
        )
        return cursor.fetchall()
    
    def close(self):
        self.conn.close() 