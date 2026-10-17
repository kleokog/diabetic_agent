#!/usr/bin/env python3
"""
Utility script to reset/clean the database for the new user identification system
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path

DB_PATH = "diabetic_agent.db"
BACKUP_PATH = f"diabetic_agent_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

def backup_database():
    """Create a backup of the existing database"""
    if not Path(DB_PATH).exists():
        print(f"❌ Database file not found: {DB_PATH}")
        return False
    
    import shutil
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"✅ Database backed up to: {BACKUP_PATH}")
    return True

def show_current_data():
    """Show current data in the database"""
    if not Path(DB_PATH).exists():
        print(f"❌ Database file not found: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n📊 Current Database Contents:")
    print("=" * 60)
    
    # Count records in each table
    tables = [
        'user_profiles',
        'blood_sugar_levels',
        'meal_logs',
        'insulin_doses',
        'health_stats',
        'analysis_results',
        'chat_messages'
    ]
    
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table:25s}: {count:5d} records")
        except sqlite3.OperationalError:
            print(f"  {table:25s}: Table does not exist")
    
    # Show user profiles
    cursor.execute("SELECT user_id, name, age, diabetes_type FROM user_profiles")
    users = cursor.fetchall()
    
    if users:
        print("\n👤 Current Users:")
        print("-" * 60)
        for user in users:
            print(f"  User ID: {user[0]}, Name: {user[1]}, Age: {user[2]}, Type: {user[3]}")
    
    conn.close()

def reset_database(keep_structure=True, create_backup=True):
    """Reset the database - delete all data but keep table structure"""
    if not Path(DB_PATH).exists():
        print(f"❌ Database file not found: {DB_PATH}")
        return False
    
    # Backup first (if requested)
    if create_backup:
        if not backup_database():
            return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n🗑️  Clearing database...")
    
    # Delete all data from tables (in reverse order of dependencies)
    tables = [
        'chat_messages',
        'analysis_results',
        'health_stats',
        'insulin_doses',
        'meal_logs',
        'blood_sugar_levels',
        'user_profiles'
    ]
    
    for table in tables:
        try:
            cursor.execute(f"DELETE FROM {table}")
            deleted = cursor.rowcount
            print(f"  ✅ Deleted {deleted} records from {table}")
        except sqlite3.OperationalError as e:
            print(f"  ⚠️  Could not delete from {table}: {e}")
    
    conn.commit()
    conn.close()
    
    print("\n✅ Database cleared successfully!")
    print("   All data has been removed. Table structure is intact.")
    print("   You can now start fresh with the new user identification system.")
    return True

def delete_database_completely(create_backup=True):
    """Completely delete the database file"""
    if not Path(DB_PATH).exists():
        print(f"❌ Database file not found: {DB_PATH}")
        return False
    
    # Backup first (if requested)
    if create_backup:
        if not backup_database():
            return False
    
    os.remove(DB_PATH)
    print(f"✅ Database file deleted: {DB_PATH}")
    print("   A new database will be created when you run the app.")
    return True

def main():
    """Main function"""
    print("🔄 Database Reset Utility")
    print("=" * 60)
    print("\nThis script will help you clean/reset the database for the new user system.")
    print("\n⚠️  WARNING: This will delete all existing data!")
    
    # Show current data
    show_current_data()
    
    print("\n" + "=" * 60)
    print("Options:")
    print("1. Reset database (clear all data, keep structure) - WITH backup")
    print("2. Reset database (clear all data, keep structure) - NO backup")
    print("3. Delete database completely (remove file) - WITH backup")
    print("4. Delete database completely (remove file) - NO backup")
    print("5. Show current data only (no changes)")
    print("6. Exit")
    
    choice = input("\nEnter your choice (1-6): ").strip()
    
    if choice == "1":
        confirm = input("\n⚠️  Are you sure you want to clear all data? (yes/no): ").strip().lower()
        if confirm == "yes":
            reset_database(create_backup=True)
        else:
            print("❌ Operation cancelled.")
    
    elif choice == "2":
        confirm = input("\n⚠️  Are you sure you want to clear all data WITHOUT backup? (yes/no): ").strip().lower()
        if confirm == "yes":
            reset_database(create_backup=False)
        else:
            print("❌ Operation cancelled.")
    
    elif choice == "3":
        confirm = input("\n⚠️  Are you sure you want to DELETE the database file? (yes/no): ").strip().lower()
        if confirm == "yes":
            delete_database_completely(create_backup=True)
        else:
            print("❌ Operation cancelled.")
    
    elif choice == "4":
        confirm = input("\n⚠️  Are you sure you want to DELETE the database file WITHOUT backup? (yes/no): ").strip().lower()
        if confirm == "yes":
            delete_database_completely(create_backup=False)
        else:
            print("❌ Operation cancelled.")
    
    elif choice == "5":
        print("\n✅ No changes made. Database remains unchanged.")
    
    elif choice == "6":
        print("👋 Exiting...")
    
    else:
        print("❌ Invalid choice. Please run the script again.")

if __name__ == "__main__":
    main()

