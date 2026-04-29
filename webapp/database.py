#!/usr/bin/env python3
"""
Database module for Off-Grid AI Agent
Handles all SQLite database operations using pysqlite3
"""

try:
    import pysqlite3 as sqlite3
except ImportError:
    import sqlite3

from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import os
import hashlib
import base64
import bcrypt

try:
    from cryptography.fernet import Fernet as _Fernet

    def _get_fernet() -> "_Fernet":
        raw = hashlib.sha256(os.environ.get("SECRET_KEY", "").encode()).digest()
        return _Fernet(base64.urlsafe_b64encode(raw))

    def encrypt_value(value: str) -> str:
        return _get_fernet().encrypt(value.encode()).decode()

    def decrypt_value(ciphertext: str) -> str:
        return _get_fernet().decrypt(ciphertext.encode()).decode()

except ImportError:
    def encrypt_value(value: str) -> str:
        return value
    def decrypt_value(ciphertext: str) -> str:
        return ciphertext

# Database file location
DB_PATH = Path(__file__).parent.parent / "offgrid_agent.db"


class Database:
    """Database manager for Off-Grid AI Agent"""
    
    def __init__(self, db_path: str = None):
        """Initialize database connection"""
        self.db_path = db_path or str(DB_PATH)
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                phone_number TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                is_verified BOOLEAN DEFAULT 0,
                failed_login_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP NULL
            )
        """)
        
        # SMS Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sms_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                phone_number TEXT NOT NULL,
                message_text TEXT NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('inbound', 'outbound')),
                status TEXT DEFAULT 'sent',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # User Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                setting_key TEXT NOT NULL,
                setting_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, setting_key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # API Keys table - stores encrypted LLM provider keys
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service_name TEXT NOT NULL,
                api_key TEXT NOT NULL,
                key_hint TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, service_name),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Gmail watched senders — addresses that trigger an SMS alert
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gmail_watched_senders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                email_address TEXT NOT NULL,
                display_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, email_address),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Tracks which Gmail message IDs we have already notified via SMS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gmail_notified_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                gmail_message_id TEXT NOT NULL,
                notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, gmail_message_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Gmail OAuth tokens table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gmail_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                token_expiry TIMESTAMP,
                gmail_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Geocode cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS geocode_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city TEXT NOT NULL COLLATE NOCASE,
                state TEXT NOT NULL COLLATE NOCASE,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(city, state)
            )
        """)

        # Follow-up hold table: phone numbers waiting for user reply (human-in-the-loop)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS follow_up_hold (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                phone_number TEXT NOT NULL UNIQUE,
                context TEXT,
                follow_up_answer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_follow_up_hold_phone ON follow_up_hold(phone_number)")

        # Weather cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weather_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                date TEXT NOT NULL,
                high_f REAL,
                low_f REAL,
                precipitation_sum REAL,
                precipitation_probability_max INTEGER,
                weather_code INTEGER,
                wind_speed_max REAL,
                wind_gusts_max REAL,
                sunrise TEXT,
                sunset TEXT,
                fetched_at TEXT NOT NULL,
                UNIQUE(latitude, longitude, date)
            )
        """)

        # Migrate existing database: add missing columns if they don't exist
        self._migrate_database(conn, cursor)

        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sms_user_id ON sms_messages(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sms_timestamp ON sms_messages(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_weather_cache_lookup ON weather_cache(latitude, longitude, date)")
        
        conn.commit()
        conn.close()
    
    def _migrate_database(self, conn, cursor):
        """Migrate existing database schema to add new columns"""
        try:
            # Get current table schema
            cursor.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Add failed_login_attempts if it doesn't exist
            if 'failed_login_attempts' not in columns:
                cursor.execute("""
                    ALTER TABLE users 
                    ADD COLUMN failed_login_attempts INTEGER DEFAULT 0
                """)
                print("✅ Added failed_login_attempts column to users table")
            
            # Add locked_until if it doesn't exist
            if 'locked_until' not in columns:
                cursor.execute("""
                    ALTER TABLE users
                    ADD COLUMN locked_until TIMESTAMP NULL
                """)
                print("✅ Added locked_until column to users table")

            # Migrate api_keys table: add key_hint column if missing
            cursor.execute("PRAGMA table_info(api_keys)")
            ak_columns = [row[1] for row in cursor.fetchall()]
            if 'key_hint' not in ak_columns:
                cursor.execute("ALTER TABLE api_keys ADD COLUMN key_hint TEXT")
                print("✅ Added key_hint column to api_keys table")

            conn.commit()
        except Exception as e:
            print(f"⚠️ Migration warning: {e}")
            conn.rollback()
    
    # ==================== USER MANAGEMENT ====================
    
    def create_user(self, username: str, email: str, password: str, 
                    full_name: str = None) -> Optional[int]:
        """Create a new user"""
        try:
            # Hash password
            password_hash = self._hash_password(password)
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, full_name)
                VALUES (?, ?, ?, ?)
            """, (username, email, password_hash, full_name))
            
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return user_id
        except sqlite3.IntegrityError as e:
            print(f"User creation error: {e}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_user_by_phone(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Get user by phone number"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE phone_number = ?", (phone_number,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def update_user_phone(self, user_id: int, phone_number: str) -> bool:
        """Update user's phone number"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE users SET phone_number = ?
                WHERE id = ?
            """, (phone_number, user_id))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            
            return success
        except sqlite3.IntegrityError:
            return False
    
    def update_last_login(self, user_id: int) -> bool:
        """Update user's last login timestamp and reset failed attempts"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET last_login = CURRENT_TIMESTAMP,
                failed_login_attempts = 0,
                locked_until = NULL
            WHERE id = ?
        """, (user_id,))
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        
        return success
    
    def increment_failed_login(self, username: str) -> int:
        """Increment failed login attempts and lock account if needed"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Increment failed attempts
        cursor.execute("""
            UPDATE users 
            SET failed_login_attempts = failed_login_attempts + 1
            WHERE username = ?
        """, (username,))
        
        # Get current failed attempts
        cursor.execute("""
            SELECT failed_login_attempts FROM users WHERE username = ?
        """, (username,))
        
        row = cursor.fetchone()
        failed_attempts = row['failed_login_attempts'] if row else 0
        
        # Lock account for 15 minutes after 5 failed attempts
        if failed_attempts >= 5:
            cursor.execute("""
                UPDATE users 
                SET locked_until = datetime('now', '+15 minutes')
                WHERE username = ?
            """, (username,))
        
        conn.commit()
        conn.close()
        
        return failed_attempts
    
    def is_account_locked(self, username: str) -> bool:
        """Check if account is locked"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT locked_until FROM users 
            WHERE username = ? AND locked_until > datetime('now')
        """, (username,))
        
        row = cursor.fetchone()
        conn.close()
        
        return row is not None
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        try:
            password_bytes = plain_password.encode('utf-8')
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]
            
            if isinstance(hashed_password, str):
                hashed_password = hashed_password.encode('utf-8')
            
            return bcrypt.checkpw(password_bytes, hashed_password)
        except Exception as e:
            print(f"Password verification error: {e}")
            return False
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    
    # ==================== SMS MESSAGES ====================
    
    def log_sms_message(self, user_id: int, phone_number: str, 
                       message_text: str, direction: str) -> int:
        """Log an SMS message"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO sms_messages (user_id, phone_number, message_text, direction)
            VALUES (?, ?, ?, ?)
        """, (user_id, phone_number, message_text, direction))
        
        message_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return message_id
    
    def get_user_messages(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's SMS messages"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM sms_messages
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

    def clear_user_messages(self, user_id: int) -> int:
        """Delete all conversation history for a user. Returns number of rows deleted."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sms_messages WHERE user_id = ?", (user_id,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def delete_user(self, user_id: int) -> bool:
        """Permanently delete a user and all child rows.

        SQLite ON DELETE CASCADE only fires when ``PRAGMA foreign_keys = ON`` is set
        on the connection, which this codebase does not do. Delete child rows
        explicitly so the operation is correct regardless of pragma state.
        """
        child_tables = (
            "sms_messages",
            "user_settings",
            "api_keys",
            "follow_up_hold",
            "gmail_tokens",
            "gmail_watched_senders",
            "gmail_notified_emails",
        )
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            for table in child_tables:
                cursor.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            success = cursor.rowcount > 0
            conn.commit()
            return success
        finally:
            conn.close()

    def get_user_message_count(self, user_id: int) -> Dict[str, int]:
        """Get count of user's messages by direction"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT direction, COUNT(*) as count
            FROM sms_messages
            WHERE user_id = ?
            GROUP BY direction
        """, (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        result = {"inbound": 0, "outbound": 0, "total": 0}
        for row in rows:
            result[row['direction']] = row['count']
        
        result['total'] = result['inbound'] + result['outbound']
        return result
    
    # ==================== USER SETTINGS ====================
    
    def get_user_setting(self, user_id: int, setting_key: str) -> Optional[str]:
        """Get a user setting"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT setting_value FROM user_settings
            WHERE user_id = ? AND setting_key = ?
        """, (user_id, setting_key))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row['setting_value']
        return None
    
    def get_all_user_settings(self, user_id: int) -> Dict[str, str]:
        """Get all settings for a user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT setting_key, setting_value FROM user_settings
            WHERE user_id = ?
        """, (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return {row['setting_key']: row['setting_value'] for row in rows}
    
    def set_user_setting(self, user_id: int, setting_key: str, setting_value: str) -> bool:
        """Set a user setting"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO user_settings (user_id, setting_key, setting_value)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, setting_key) 
            DO UPDATE SET setting_value = ?, updated_at = CURRENT_TIMESTAMP
        """, (user_id, setting_key, setting_value, setting_value))
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        
        return success
    
    # ==================== CACHE ====================

    def get_cached_geocode(self, city: str, state: str) -> Optional[Dict[str, Any]]:
        """Get cached geocode result for city/state."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT latitude, longitude FROM geocode_cache WHERE city = ? AND state = ?",
            (city, state),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def cache_geocode(self, city: str, state: str, lat: float, lon: float):
        """Upsert a geocode result into the cache."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO geocode_cache (city, state, latitude, longitude)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(city, state)
               DO UPDATE SET latitude = excluded.latitude,
                             longitude = excluded.longitude,
                             created_at = CURRENT_TIMESTAMP""",
            (city, state, lat, lon),
        )
        conn.commit()
        conn.close()

    def get_cached_weather(self, lat: float, lon: float, dates: List[str]) -> List[Dict[str, Any]]:
        """Return cached weather rows for the given dates at rounded lat/lon.
        Only returns rows whose fetched_at is from today (UTC)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in dates)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cursor.execute(
            f"""SELECT * FROM weather_cache
                WHERE latitude = ? AND longitude = ?
                  AND date IN ({placeholders})
                  AND fetched_at >= ?""",
            [lat, lon] + list(dates) + [today],
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def cache_weather(self, lat: float, lon: float, daily_rows: List[Dict[str, Any]]):
        """Upsert a list of daily forecast dicts into the weather cache."""
        conn = self.get_connection()
        cursor = conn.cursor()
        fetched_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        for row in daily_rows:
            cursor.execute(
                """INSERT INTO weather_cache
                       (latitude, longitude, date, high_f, low_f,
                        precipitation_sum, precipitation_probability_max,
                        weather_code, wind_speed_max, wind_gusts_max,
                        sunrise, sunset, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(latitude, longitude, date)
                   DO UPDATE SET high_f = excluded.high_f,
                                 low_f = excluded.low_f,
                                 precipitation_sum = excluded.precipitation_sum,
                                 precipitation_probability_max = excluded.precipitation_probability_max,
                                 weather_code = excluded.weather_code,
                                 wind_speed_max = excluded.wind_speed_max,
                                 wind_gusts_max = excluded.wind_gusts_max,
                                 sunrise = excluded.sunrise,
                                 sunset = excluded.sunset,
                                 fetched_at = excluded.fetched_at""",
                (
                    lat, lon, row["date"], row["high_f"], row["low_f"],
                    row["precipitation_sum"], row["precipitation_probability_max"],
                    row["weather_code"], row["wind_speed_max"], row["wind_gusts_max"],
                    row["sunrise"], row["sunset"], fetched_at,
                ),
            )
        conn.commit()
        conn.close()

    # ==================== STATISTICS ====================
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive user statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get message counts
        message_counts = self.get_user_message_count(user_id)
        
        # Get account age
        cursor.execute("""
            SELECT 
                created_at,
                last_login,
                julianday('now') - julianday(created_at) as days_active
            FROM users
            WHERE id = ?
        """, (user_id,))
        
        user_info = cursor.fetchone()
        
        # Get recent activity (last 7 days)
        cursor.execute("""
            SELECT COUNT(*) as recent_count
            FROM sms_messages
            WHERE user_id = ? AND timestamp >= datetime('now', '-7 days')
        """, (user_id,))
        
        recent = cursor.fetchone()
        
        conn.close()
        
        return {
            "total_messages": message_counts['total'],
            "inbound_messages": message_counts['inbound'],
            "outbound_messages": message_counts['outbound'],
            "created_at": user_info['created_at'] if user_info else None,
            "last_login": user_info['last_login'] if user_info else None,
            "days_active": int(user_info['days_active']) if user_info and user_info['days_active'] else 0,
            "recent_messages_7d": recent['recent_count'] if recent else 0
        }

    # ==================== FOLLOW-UP HOLD (human-in-the-loop) ====================

    # Max age (seconds) for a follow-up hold; older holds are treated as stale and cleared.
    FOLLOW_UP_HOLD_MAX_AGE_SECONDS = 90

    def is_phone_in_follow_up_hold(self, phone_number: str) -> bool:
        """Check if this phone number is currently in the follow-up hold table."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM follow_up_hold WHERE phone_number = ?",
            (phone_number,),
        )
        row = cursor.fetchone()
        conn.close()
        return row is not None

    def get_recent_follow_up_hold_by_phone(
        self, phone_number: str, max_age_seconds: int = FOLLOW_UP_HOLD_MAX_AGE_SECONDS
    ) -> Optional[Dict[str, Any]]:
        """Get the follow-up hold row only if it was created within max_age_seconds (not stale)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM follow_up_hold
               WHERE phone_number = ?
                 AND datetime(created_at) > datetime('now', ?)""",
            (phone_number, f"-{max_age_seconds} seconds"),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_follow_up_hold_by_phone(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Get the follow-up hold row for this phone number, or None."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM follow_up_hold WHERE phone_number = ?",
            (phone_number,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def add_follow_up_hold(
        self,
        user_id: int,
        phone_number: str,
        context: Optional[str] = None,
    ) -> bool:
        """Add a phone number to the follow-up hold table (one row per phone)."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO follow_up_hold (user_id, phone_number, context)
                   VALUES (?, ?, ?)
                   ON CONFLICT(phone_number) DO UPDATE SET
                     user_id = excluded.user_id,
                     context = excluded.context,
                     follow_up_answer = NULL,
                     created_at = CURRENT_TIMESTAMP""",
                (user_id, phone_number, context),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"add_follow_up_hold error: {e}")
            return False

    def set_follow_up_answer(self, phone_number: str, answer: str) -> bool:
        """Store the user's reply as the follow-up answer for this phone."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE follow_up_hold SET follow_up_answer = ? WHERE phone_number = ?",
            (answer, phone_number),
        )
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success

    def remove_follow_up_hold(self, phone_number: str) -> bool:
        """Remove this phone number from the follow-up hold table."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM follow_up_hold WHERE phone_number = ?", (phone_number,))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success


    # ==================== GMAIL WATCHED SENDERS ====================

    def get_watched_senders(self, user_id: int) -> List[Dict[str, Any]]:
        """Return all watched senders for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT email_address, display_name FROM gmail_watched_senders WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_watched_sender(self, user_id: int, email_address: str, display_name: str = None) -> bool:
        """Add a watched sender. Returns False if already exists."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO gmail_watched_senders (user_id, email_address, display_name) VALUES (?, ?, ?)",
                (user_id, email_address.lower().strip(), display_name),
            )
            conn.commit()
            added = cursor.rowcount > 0
            conn.close()
            return added
        except Exception as e:
            print(f"add_watched_sender error: {e}")
            return False

    def remove_watched_sender(self, user_id: int, email_address: str) -> bool:
        """Remove a watched sender."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM gmail_watched_senders WHERE user_id = ? AND email_address = ?",
            (user_id, email_address.lower().strip()),
        )
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success

    def get_all_gmail_users(self) -> List[Dict[str, Any]]:
        """Return all users who have Gmail connected, with their phone number."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT gt.user_id, u.phone_number, gt.access_token, gt.refresh_token,
                   gt.token_expiry, gt.gmail_address
            FROM gmail_tokens gt
            JOIN users u ON u.id = gt.user_id
            WHERE u.is_active = 1 AND u.phone_number IS NOT NULL
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def is_email_notified(self, user_id: int, gmail_message_id: str) -> bool:
        """True if we already sent an SMS for this email."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM gmail_notified_emails WHERE user_id = ? AND gmail_message_id = ?",
            (user_id, gmail_message_id),
        )
        found = cursor.fetchone() is not None
        conn.close()
        return found

    def mark_email_notified(self, user_id: int, gmail_message_id: str) -> bool:
        """Record that we sent an SMS for this email (ignore duplicates)."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO gmail_notified_emails (user_id, gmail_message_id) VALUES (?, ?)",
                (user_id, gmail_message_id),
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    # ==================== LLM API KEYS ====================

    def save_llm_api_key(self, user_id: int, provider: str, encrypted_key: str, key_hint: str) -> bool:
        """Save or update an encrypted LLM provider API key"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO api_keys (user_id, service_name, api_key, key_hint)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, service_name)
                DO UPDATE SET api_key = ?, key_hint = ?, created_at = CURRENT_TIMESTAMP
            """, (user_id, provider, encrypted_key, key_hint, encrypted_key, key_hint))
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            print(f"Error saving LLM API key: {e}")
            return False

    def get_llm_api_key(self, user_id: int, provider: str) -> Optional[Dict[str, Any]]:
        """Get encrypted LLM API key for a provider (backend use only)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT api_key, key_hint FROM api_keys
            WHERE user_id = ? AND service_name = ?
        """, (user_id, provider))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"encrypted_key": row["api_key"], "key_hint": row["key_hint"]}
        return None

    def get_all_llm_keys_status(self, user_id: int) -> Dict[str, Any]:
        """Return which LLM providers are configured (hints only, no keys)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT service_name, key_hint FROM api_keys
            WHERE user_id = ? AND service_name IN ('claude', 'openai', 'gemini')
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        result = {
            "claude":  {"is_set": False, "key_hint": None},
            "openai":  {"is_set": False, "key_hint": None},
            "gemini":  {"is_set": False, "key_hint": None},
        }
        for row in rows:
            result[row["service_name"]] = {"is_set": True, "key_hint": row["key_hint"]}
        return result

    def delete_llm_api_key(self, user_id: int, provider: str) -> bool:
        """Remove an LLM API key"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM api_keys WHERE user_id = ? AND service_name = ?", (user_id, provider))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success

    # ==================== GMAIL TOKENS ====================

    def save_gmail_tokens(self, user_id: int, access_token: str, refresh_token: Optional[str],
                          gmail_address: Optional[str], token_expiry: Optional[str]) -> bool:
        """Save or update Gmail OAuth tokens (should be pre-encrypted)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO gmail_tokens (user_id, access_token, refresh_token, gmail_address, token_expiry)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    access_token = ?,
                    refresh_token = COALESCE(?, refresh_token),
                    gmail_address = COALESCE(?, gmail_address),
                    token_expiry = ?,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, access_token, refresh_token, gmail_address, token_expiry,
                  access_token, refresh_token, gmail_address, token_expiry))
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
        except Exception as e:
            print(f"Error saving Gmail tokens: {e}")
            return False

    def get_gmail_tokens(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get Gmail OAuth tokens for a user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gmail_tokens WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def delete_gmail_tokens(self, user_id: int) -> bool:
        """Remove Gmail OAuth tokens (disconnect)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM gmail_tokens WHERE user_id = ?", (user_id,))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success


# Singleton database instance
db = Database()


if __name__ == "__main__":
    """Test database functionality"""
    print("Initializing database...")
    test_db = Database()
    print(f"✅ Database initialized at: {test_db.db_path}")
    
    # Create a test user
    print("\nCreating test user...")
    user_id = test_db.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        full_name="Test User"
    )
    
    if user_id:
        print(f"✅ Test user created with ID: {user_id}")
        
        # Get user
        user = test_db.get_user_by_username("testuser")
        print(f"✅ Retrieved user: {user['username']} ({user['email']})")
        
        # Test settings
        test_db.set_user_setting(user_id, "theme", "dark")
        theme = test_db.get_user_setting(user_id, "theme")
        print(f"✅ Setting saved and retrieved: theme={theme}")
        
        # Log test message
        test_db.log_sms_message(user_id, "+1234567890", "Test message", "outbound")
        print(f"✅ Test message logged")
        
        # Get stats
        stats = test_db.get_user_stats(user_id)
        print(f"✅ User stats: {stats}")
    else:
        print("⚠️ Test user may already exist")
    
    print("\n✅ Database test complete!")
