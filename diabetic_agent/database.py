"""
Database manager for the diabetic agent using SQLite
"""

import sqlite3
import json
from datetime import datetime, date, timedelta
from typing import List, Optional
from pathlib import Path

from .models import (
    UserProfile, BloodSugarLevel, MealLog, InsulinDose, 
    HealthStats, AnalysisResult, ChatMessage, FoodItem
)


class DatabaseManager:
    """Manages SQLite database operations for the diabetic agent"""
    
    def __init__(self, db_path: str = "diabetic_agent.db"):
        self.db_path = db_path
        self._init_database()
    
    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_database(self):
        """Initialize database tables"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # User profiles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                diabetes_type TEXT NOT NULL,
                diagnosis_date TEXT NOT NULL,
                current_medications TEXT,
                target_blood_sugar_range TEXT,
                dietary_restrictions TEXT,
                allergies TEXT,
                preferences TEXT
            )
        """)
        
        # Blood sugar levels table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blood_sugar_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                value REAL NOT NULL,
                measurement_type TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
            )
        """)
        
        # Meal logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meal_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                meal_type TEXT NOT NULL,
                total_calories REAL NOT NULL,
                total_carbs REAL NOT NULL,
                total_protein REAL NOT NULL,
                total_fat REAL NOT NULL,
                food_items TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
            )
        """)
        
        # Insulin doses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insulin_doses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                insulin_type TEXT NOT NULL,
                units REAL NOT NULL,
                injection_site TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
            )
        """)
        
        # Health stats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                steps INTEGER,
                weight REAL,
                height REAL,
                workout_duration INTEGER,
                workout_type TEXT,
                sleep_hours REAL,
                stress_level INTEGER,
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
            )
        """)
        
        # Analysis results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date_range TEXT NOT NULL,
                average_blood_sugar REAL NOT NULL,
                time_in_range REAL NOT NULL,
                patterns TEXT NOT NULL,
                recommendations TEXT NOT NULL,
                risk_factors TEXT NOT NULL,
                positive_trends TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
            )
        """)
        
        # Chat messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                user_message TEXT NOT NULL,
                agent_response TEXT NOT NULL,
                message_type TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_user_profile(self, profile: UserProfile, user_id: int = 1):
        """Add or update user profile"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO user_profiles 
            (user_id, name, age, diabetes_type, diagnosis_date, current_medications,
             target_blood_sugar_range, dietary_restrictions, allergies, preferences)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            profile.name,
            profile.age,
            profile.diabetes_type,
            profile.diagnosis_date.isoformat(),
            json.dumps(profile.current_medications),
            json.dumps(profile.target_blood_sugar_range),
            json.dumps(profile.dietary_restrictions),
            json.dumps(profile.allergies),
            json.dumps(profile.preferences)
        ))
        
        conn.commit()
        conn.close()
    
    def get_user_profile(self, user_id: int = 1) -> Optional[UserProfile]:
        """Get user profile"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            return None
        
        return UserProfile(
            name=row['name'],
            age=row['age'],
            diabetes_type=row['diabetes_type'],
            diagnosis_date=datetime.fromisoformat(row['diagnosis_date']).date(),
            current_medications=json.loads(row['current_medications'] or '[]'),
            target_blood_sugar_range=json.loads(row['target_blood_sugar_range'] or '{}'),
            dietary_restrictions=json.loads(row['dietary_restrictions'] or '[]'),
            allergies=json.loads(row['allergies'] or '[]'),
            preferences=json.loads(row['preferences'] or '{}')
        )
    
    def add_blood_sugar_level(self, reading: BloodSugarLevel, user_id: int = 1):
        """Add blood sugar reading"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO blood_sugar_levels 
            (user_id, timestamp, value, measurement_type, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            reading.timestamp.isoformat(),
            reading.value,
            reading.measurement_type,
            reading.notes
        ))
        
        conn.commit()
        conn.close()
    
    def get_blood_sugar_levels(self, user_id: int = 1, days: int = 30) -> List[BloodSugarLevel]:
        """Get blood sugar levels for a user within specified days"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute("""
            SELECT * FROM blood_sugar_levels 
            WHERE user_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC
        """, (user_id, cutoff_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            BloodSugarLevel(
                timestamp=datetime.fromisoformat(row['timestamp']),
                value=row['value'],
                measurement_type=row['measurement_type'],
                notes=row['notes']
            )
            for row in rows
        ]
    
    def add_meal_log(self, meal_log: MealLog, user_id: int = 1):
        """Add meal log"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        food_items_json = json.dumps([item.dict() for item in meal_log.food_items])
        
        cursor.execute("""
            INSERT INTO meal_logs 
            (user_id, timestamp, meal_type, total_calories, total_carbs, 
             total_protein, total_fat, food_items, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            meal_log.timestamp.isoformat(),
            meal_log.meal_type,
            meal_log.total_calories,
            meal_log.total_carbs,
            meal_log.total_protein,
            meal_log.total_fat,
            food_items_json,
            meal_log.notes
        ))
        
        conn.commit()
        conn.close()
    
    def get_meal_logs(self, user_id: int = 1, days: int = 30) -> List[MealLog]:
        """Get meal logs for a user within specified days"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute("""
            SELECT * FROM meal_logs 
            WHERE user_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC
        """, (user_id, cutoff_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        meal_logs = []
        for row in rows:
            food_items_data = json.loads(row['food_items'])
            food_items = [FoodItem(**item) for item in food_items_data]
            
            meal_logs.append(MealLog(
                timestamp=datetime.fromisoformat(row['timestamp']),
                meal_type=row['meal_type'],
                food_items=food_items,
                total_calories=row['total_calories'],
                total_carbs=row['total_carbs'],
                total_protein=row['total_protein'],
                total_fat=row['total_fat'],
                notes=row['notes']
            ))
        
        return meal_logs
    
    def add_insulin_dose(self, dose: InsulinDose, user_id: int = 1):
        """Add insulin dose"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO insulin_doses 
            (user_id, timestamp, insulin_type, units, injection_site, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            dose.timestamp.isoformat(),
            dose.insulin_type,
            dose.units,
            dose.injection_site,
            dose.notes
        ))
        
        conn.commit()
        conn.close()
    
    def get_insulin_doses(self, user_id: int = 1, days: int = 30) -> List[InsulinDose]:
        """Get insulin doses for a user within specified days"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute("""
            SELECT * FROM insulin_doses 
            WHERE user_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC
        """, (user_id, cutoff_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            InsulinDose(
                timestamp=datetime.fromisoformat(row['timestamp']),
                insulin_type=row['insulin_type'],
                units=row['units'],
                injection_site=row['injection_site'],
                notes=row['notes']
            )
            for row in rows
        ]
    
    def add_health_stats(self, stats: HealthStats, user_id: int = 1):
        """Add health statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO health_stats 
            (user_id, date, steps, weight, height, workout_duration, 
             workout_type, sleep_hours, stress_level, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            stats.date.isoformat(),
            stats.steps,
            stats.weight,
            stats.height,
            stats.workout_duration,
            stats.workout_type,
            stats.sleep_hours,
            stats.stress_level,
            stats.notes
        ))
        
        conn.commit()
        conn.close()
    
    def get_health_stats(self, user_id: int = 1, days: int = 30) -> List[HealthStats]:
        """Get health stats for a user within specified days"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).date().isoformat()
        
        cursor.execute("""
            SELECT * FROM health_stats 
            WHERE user_id = ? AND date >= ?
            ORDER BY date DESC
        """, (user_id, cutoff_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            HealthStats(
                date=datetime.fromisoformat(row['date']).date(),
                steps=row['steps'],
                weight=row['weight'],
                height=row['height'],
                workout_duration=row['workout_duration'],
                workout_type=row['workout_type'],
                sleep_hours=row['sleep_hours'],
                stress_level=row['stress_level'],
                notes=row['notes']
            )
            for row in rows
        ]
    
    def save_analysis_result(self, analysis: AnalysisResult, user_id: int = 1):
        """Save analysis result"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO analysis_results 
            (user_id, date_range, average_blood_sugar, time_in_range,
             patterns, recommendations, risk_factors, positive_trends, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            json.dumps({
                'start': analysis.date_range['start'].isoformat() if 'start' in analysis.date_range else None,
                'end': analysis.date_range['end'].isoformat() if 'end' in analysis.date_range else None
            }),
            analysis.average_blood_sugar,
            analysis.time_in_range,
            json.dumps([pattern.dict() for pattern in analysis.patterns]),
            json.dumps(analysis.recommendations),
            json.dumps(analysis.risk_factors),
            json.dumps(analysis.positive_trends),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def add_chat_message(self, message: ChatMessage, user_id: int = 1):
        """Add chat message"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO chat_messages 
            (user_id, timestamp, user_message, agent_response, message_type)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            message.timestamp.isoformat(),
            message.user_message,
            message.agent_response,
            message.message_type
        ))
        
        conn.commit()
        conn.close()

