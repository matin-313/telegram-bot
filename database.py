# ======================================================
# DATABASE MODULE
# ======================================================
import sqlite3
import json
from datetime import datetime, date
import threading

class Database:
    def __init__(self, db_file="sport_bot.db"):
        self.db_file = db_file
        self.lock = threading.Lock()
        self.init_db()
    
    def init_db(self):
        """ایجاد تمام جداول مورد نیاز"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # ========== جدول کاربران ==========
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        first_name TEXT,
                        last_name TEXT,
                        username TEXT,
                        full_name TEXT,
                        date TEXT,
                        language TEXT,
                        help_seen INTEGER DEFAULT 0
                    )
                ''')
                
                # ========== جدول بازیکنان فوتسال ==========
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS futsal_players (
                        phone TEXT,
                        group_name TEXT,
                        name TEXT,
                        PRIMARY KEY (phone, group_name)
                    )
                ''')
                
                # ========== جدول بازیکنان بسکتبال ==========
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS basketball_players (
                        phone TEXT PRIMARY KEY,
                        name TEXT
                    )
                ''')
                
                # ========== جدول بازیکنان والیبال ==========
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS volleyball_players (
                        phone TEXT PRIMARY KEY,
                        name TEXT
                    )
                ''')
                
                # ========== جدول بازیکنان اشتراکی ==========
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS shared_players (
                        phone TEXT PRIMARY KEY,
                        name TEXT
                    )
                ''')
                
                # ========== جدول تایم‌های فوتسال ==========
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS futsal_times (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_name TEXT,
                        date TEXT,
                        start TEXT,
                        end TEXT,
                        cap INTEGER,
                        date_obj TEXT
                    )
                ''')
                
                # ========== جدول تایم‌های بسکتبال ==========
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS basketball_times (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT,
                        start TEXT,
                        end TEXT,
                        cap INTEGER,
                        date_obj TEXT
                    )
                ''')
                
                # ========== جدول تایم‌های والیبال ==========
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS volleyball_times (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT,
                        start TEXT,
                        end TEXT,
                        cap INTEGER,
                        date_obj TEXT
                    )
                ''')
                
                # ========== جدول تایم‌های اشتراکی ==========
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS shared_times (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT,
                        start TEXT,
                        end TEXT,
                        cap INTEGER,
                        date_obj TEXT
                    )
                ''')
                
                # ========== جدول ثبت‌نام‌ها ==========
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS registrations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sport TEXT,
                        group_name TEXT,
                        time_key TEXT,
                        phone TEXT,
                        name TEXT,
                        UNIQUE(sport, group_name, time_key, phone)
                    )
                ''')
                
                conn.commit()
                print("✅ دیتابیس راه‌اندازی شد")
    
    # ========== لود کامل دیتا به RAM ==========
    
    def load_all_to_ram(self):
        """همه دیتا رو از دیتابیس میخونه و به فرمت RAM برمیگردونه"""
        data = {
            "USERS": {},
            "RAM_PLAYERS": {
                "futsal": {g: {} for g in "ABCDEFGHIJ"},
                "basketball": {},
                "volleyball": {},
                "shared": {}
            },
            "RAM_TIMES": {
                "futsal": {g: [] for g in "ABCDEFGHIJ"},
                "basketball": [],
                "volleyball": [],
                "shared": []
            },
            "RAM_REGISTRATIONS": {
                "futsal": {g: {} for g in "ABCDEFGHIJ"},
                "basketball": {},
                "volleyball": {},
                "shared": {}
            }
        }
        
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # ===== کاربران =====
                cursor.execute("SELECT * FROM users")
                for row in cursor.fetchall():
                    data["USERS"][row["user_id"]] = {
                        "first_name": row["first_name"],
                        "last_name": row["last_name"],
                        "username": row["username"],
                        "full_name": row["full_name"],
                        "date": row["date"],
                        "language": row["language"],
                        "help_seen": bool(row["help_seen"])
                    }
                
                # ===== بازیکنان فوتسال =====
                cursor.execute("SELECT * FROM futsal_players")
                for row in cursor.fetchall():
                    data["RAM_PLAYERS"]["futsal"][row["group_name"]][row["phone"]] = row["name"]
                
                # ===== بازیکنان بسکتبال =====
                cursor.execute("SELECT * FROM basketball_players")
                for row in cursor.fetchall():
                    data["RAM_PLAYERS"]["basketball"][row["phone"]] = row["name"]
                
                # ===== بازیکنان والیبال =====
                cursor.execute("SELECT * FROM volleyball_players")
                for row in cursor.fetchall():
                    data["RAM_PLAYERS"]["volleyball"][row["phone"]] = row["name"]
                
                # ===== بازیکنان اشتراکی =====
                cursor.execute("SELECT * FROM shared_players")
                for row in cursor.fetchall():
                    data["RAM_PLAYERS"]["shared"][row["phone"]] = row["name"]
                
                # ===== تایم‌های فوتسال =====
                cursor.execute("SELECT * FROM futsal_times ORDER BY date_obj")
                for row in cursor.fetchall():
                    time_dict = {
                        "date": row["date"],
                        "start": row["start"],
                        "end": row["end"],
                        "cap": row["cap"],
                        "date_obj": datetime.fromisoformat(row["date_obj"]).date()
                    }
                    data["RAM_TIMES"]["futsal"][row["group_name"]].append(time_dict)
                
                # ===== تایم‌های بسکتبال =====
                cursor.execute("SELECT * FROM basketball_times ORDER BY date_obj")
                for row in cursor.fetchall():
                    time_dict = {
                        "date": row["date"],
                        "start": row["start"],
                        "end": row["end"],
                        "cap": row["cap"],
                        "date_obj": datetime.fromisoformat(row["date_obj"]).date()
                    }
                    data["RAM_TIMES"]["basketball"].append(time_dict)
                
                # ===== تایم‌های والیبال =====
                cursor.execute("SELECT * FROM volleyball_times ORDER BY date_obj")
                for row in cursor.fetchall():
                    time_dict = {
                        "date": row["date"],
                        "start": row["start"],
                        "end": row["end"],
                        "cap": row["cap"],
                        "date_obj": datetime.fromisoformat(row["date_obj"]).date()
                    }
                    data["RAM_TIMES"]["volleyball"].append(time_dict)
                
                # ===== تایم‌های اشتراکی =====
                cursor.execute("SELECT * FROM shared_times ORDER BY date_obj")
                for row in cursor.fetchall():
                    time_dict = {
                        "date": row["date"],
                        "start": row["start"],
                        "end": row["end"],
                        "cap": row["cap"],
                        "date_obj": datetime.fromisoformat(row["date_obj"]).date()
                    }
                    data["RAM_TIMES"]["shared"].append(time_dict)
                
                # ===== ثبت‌نام‌ها =====
                cursor.execute("SELECT * FROM registrations")
                for row in cursor.fetchall():
                    sport = row["sport"]
                    group = row["group_name"]
                    time_key = row["time_key"]
                    phone = row["phone"]
                    name = row["name"]
                    
                    if sport == "futsal":
                        if time_key not in data["RAM_REGISTRATIONS"]["futsal"][group]:
                            data["RAM_REGISTRATIONS"]["futsal"][group][time_key] = {}
                        data["RAM_REGISTRATIONS"]["futsal"][group][time_key][phone] = name
                    elif sport == "basketball":
                        if time_key not in data["RAM_REGISTRATIONS"]["basketball"]:
                            data["RAM_REGISTRATIONS"]["basketball"][time_key] = {}
                        data["RAM_REGISTRATIONS"]["basketball"][time_key][phone] = name
                    elif sport == "volleyball":
                        if time_key not in data["RAM_REGISTRATIONS"]["volleyball"]:
                            data["RAM_REGISTRATIONS"]["volleyball"][time_key] = {}
                        data["RAM_REGISTRATIONS"]["volleyball"][time_key][phone] = name
                    elif sport == "shared":
                        if time_key not in data["RAM_REGISTRATIONS"]["shared"]:
                            data["RAM_REGISTRATIONS"]["shared"][time_key] = {}
                        data["RAM_REGISTRATIONS"]["shared"][time_key][phone] = name
        
        return data
    
    # ========== توابع همگام‌سازی کاربران ==========
    
    def save_user(self, user_id, user_data):
        """ذخیره یا به‌روزرسانی کاربر"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO users 
                    (user_id, first_name, last_name, username, full_name, date, language, help_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    user_data.get("first_name", ""),
                    user_data.get("last_name", ""),
                    user_data.get("username", ""),
                    user_data.get("full_name", ""),
                    user_data.get("date", ""),
                    user_data.get("language", ""),
                    1 if user_data.get("help_seen") else 0
                ))
                conn.commit()
    
    # ========== توابع همگام‌سازی بازیکنان ==========
    
    def save_futsal_player(self, group, phone, name):
        """ذخیره بازیکن فوتسال"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO futsal_players (phone, group_name, name)
                    VALUES (?, ?, ?)
                ''', (phone, group, name))
                conn.commit()
    
    def delete_futsal_player(self, group, phone):
        """حذف بازیکن فوتسال"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM futsal_players WHERE phone=? AND group_name=?', 
                             (phone, group))
                conn.commit()
    
    def save_basketball_player(self, phone, name):
        """ذخیره بازیکن بسکتبال"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO basketball_players (phone, name)
                    VALUES (?, ?)
                ''', (phone, name))
                conn.commit()
    
    def delete_basketball_player(self, phone):
        """حذف بازیکن بسکتبال"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM basketball_players WHERE phone=?', (phone,))
                conn.commit()
    
    def save_volleyball_player(self, phone, name):
        """ذخیره بازیکن والیبال"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO volleyball_players (phone, name)
                    VALUES (?, ?)
                ''', (phone, name))
                conn.commit()
    
    def delete_volleyball_player(self, phone):
        """حذف بازیکن والیبال"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM volleyball_players WHERE phone=?', (phone,))
                conn.commit()
    
    # ========== توابع همگام‌سازی تایم‌ها ==========
    
    def save_futsal_time(self, group, time_data):
        """ذخیره تایم فوتسال"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO futsal_times (group_name, date, start, end, cap, date_obj)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    group,
                    time_data["date"],
                    time_data["start"],
                    time_data["end"],
                    time_data["cap"],
                    time_data["date_obj"].isoformat()
                ))
                conn.commit()
                return cursor.lastrowid
    
    def delete_futsal_time(self, time_id):
        """حذف تایم فوتسال با id"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM futsal_times WHERE id=?', (time_id,))
                conn.commit()
        
    def delete_basketball_time(self, time_id):
        """حذف تایم بسکتبال با id"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM basketball_times WHERE id=?', (time_id,))
                conn.commit()
    
    def delete_volleyball_time(self, time_id):
        """حذف تایم والیبال با id"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM volleyball_times WHERE id=?', (time_id,))
                conn.commit()
    
    def delete_shared_time(self, time_id):
        """حذف تایم اشتراکی با id"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM shared_times WHERE id=?', (time_id,))
                conn.commit()

    def save_basketball_time(self, time_data):
        """ذخیره تایم بسکتبال"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO basketball_times (date, start, end, cap, date_obj)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    time_data["date"],
                    time_data["start"],
                    time_data["end"],
                    time_data["cap"],
                    time_data["date_obj"].isoformat()
                ))
                conn.commit()
                return cursor.lastrowid 

    def save_volleyball_time(self, time_data):
        """ذخیره تایم والیبال"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO volleyball_times (date, start, end, cap, date_obj)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    time_data["date"],
                    time_data["start"],
                    time_data["end"],
                    time_data["cap"],
                    time_data["date_obj"].isoformat()
                ))
                conn.commit()
                return cursor.lastrowid  # ✅ برگردوندن id
    
    def save_shared_time(self, time_data):
        """ذخیره تایم اشتراکی"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO shared_times (date, start, end, cap, date_obj)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    time_data["date"],
                    time_data["start"],
                    time_data["end"],
                    time_data["cap"],
                    time_data["date_obj"].isoformat()
                ))
                conn.commit()
                return cursor.lastrowid  # ✅ برگردوندن id
    
    # ========== توابع همگام‌سازی ثبت‌نام‌ها ==========
    
    def save_registration(self, sport, group, time_key, phone, name):
        """ذخیره ثبت‌نام"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO registrations (sport, group_name, time_key, phone, name)
                    VALUES (?, ?, ?, ?, ?)
                ''', (sport, group, time_key, phone, name))
                conn.commit()
    
    def delete_registration(self, sport, group, time_key, phone):
        """حذف ثبت‌نام"""
        with self.lock:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM registrations 
                    WHERE sport=? AND group_name=? AND time_key=? AND phone=?
                ''', (sport, group, time_key, phone))
                conn.commit()
