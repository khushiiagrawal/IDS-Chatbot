import sqlite3
from datetime import datetime
import uuid
import threading

class ComplaintDatabase:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ComplaintDatabase, cls).__new__(cls)
                cls._instance.initialized = False
            return cls._instance
    
    def __init__(self):
        if self.initialized:
            return
            
        with self._lock:
            if not self.initialized:
                self.conn = sqlite3.connect('complaints.db', check_same_thread=False)
                self.create_tables()
                self.initialized = True
    
    def create_tables(self):
        cursor = self.conn.cursor()
        # Create complaints table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS complaints (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolution TEXT
            )
        ''')
        
        # Create conversation history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS complaint_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complaint_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY (complaint_id) REFERENCES complaints (id)
            )
        ''')
        self.conn.commit()
    
    def generate_complaint_id(self):
        """Generate a unique complaint ID"""
        date = datetime.now().strftime("%Y%m%d")
        unique_id = str(uuid.uuid4())[:4]
        return f"COMP-{date}-{unique_id}"
    
    def add_complaint(self, description, initial_response):
        """Add a new complaint and its initial response"""
        with self._lock:
            complaint_id = self.generate_complaint_id()
            cursor = self.conn.cursor()
            
            # Add complaint
            cursor.execute(
                'INSERT INTO complaints (id, description, status) VALUES (?, ?, ?)',
                (complaint_id, description, "Open")
            )
            
            # Add initial conversation
            cursor.execute(
                'INSERT INTO complaint_conversations (complaint_id, role, content) VALUES (?, ?, ?)',
                (complaint_id, "user", description)
            )
            cursor.execute(
                'INSERT INTO complaint_conversations (complaint_id, role, content) VALUES (?, ?, ?)',
                (complaint_id, "bot", initial_response)
            )
            
            self.conn.commit()
            return complaint_id
    
    def get_complaint(self, complaint_id):
        """Get complaint details"""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM complaints WHERE id = ?', (complaint_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'description': row[1],
                    'status': row[2],
                    'created_at': row[3],
                    'updated_at': row[4],
                    'resolution': row[5]
                }
            return None
    
    def update_complaint_status(self, complaint_id, status, resolution=None):
        """Update complaint status and resolution"""
        with self._lock:
            cursor = self.conn.cursor()
            if resolution:
                cursor.execute(
                    'UPDATE complaints SET status = ?, resolution = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (status, resolution, complaint_id)
                )
            else:
                cursor.execute(
                    'UPDATE complaints SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (status, complaint_id)
                )
            self.conn.commit()
    
    def add_to_conversation(self, complaint_id, role, content):
        """Add a message to the complaint conversation"""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
                'INSERT INTO complaint_conversations (complaint_id, role, content) VALUES (?, ?, ?)',
                (complaint_id, role, content)
            )
            self.conn.commit()
    
    def get_conversation_history(self, complaint_id):
        """Get conversation history for a complaint"""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
                'SELECT role, content, timestamp FROM complaint_conversations WHERE complaint_id = ? ORDER BY timestamp ASC',
                (complaint_id,)
            )
            return cursor.fetchall()
    
    def get_all_complaints(self):
        """Get all complaints"""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM complaints ORDER BY created_at DESC')
            return cursor.fetchall()
    
    def close(self):
        """Close the database connection"""
        with self._lock:
            if hasattr(self, 'conn'):
                self.conn.close() 