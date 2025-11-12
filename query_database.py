#!/usr/bin/env python3
"""
Helper script to query the diabetic agent database using SQL
"""

import sqlite3
import sys
from pathlib import Path
import pandas as pd

# Database path
DB_PATH = "diabetic_agent.db"

def connect_db():
    """Connect to the database"""
    if not Path(DB_PATH).exists():
        print(f"❌ Database file not found: {DB_PATH}")
        print("   Make sure you're running this from the project directory")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

def list_tables():
    """List all tables in the database"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("📊 Database Tables:")
    print("=" * 50)
    for table in tables:
        print(f"  - {table[0]}")
    
    conn.close()

def show_table_structure(table_name):
    """Show the structure of a table"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    print(f"📋 Table Structure: {table_name}")
    print("=" * 50)
    print(f"{'Column':<20} {'Type':<15} {'Nullable':<10}")
    print("-" * 50)
    for col in columns:
        nullable = "YES" if col[3] == 0 else "NO"
        print(f"{col[1]:<20} {col[2]:<15} {nullable:<10}")
    
    conn.close()

def query(sql_query, output_format='table'):
    """Execute a SQL query and display results"""
    conn = connect_db()
    
    try:
        df = pd.read_sql_query(sql_query, conn)
        
        if output_format == 'table':
            print(f"📊 Query Results ({len(df)} rows):")
            print("=" * 80)
            print(df.to_string(index=False))
        elif output_format == 'csv':
            print(df.to_csv(index=False))
        elif output_format == 'json':
            print(df.to_json(orient='records', indent=2))
        
        return df
    except Exception as e:
        print(f"❌ Error executing query: {e}")
        return None
    finally:
        conn.close()

def get_blood_sugar_summary():
    """Get summary of blood sugar data"""
    sql = """
    SELECT 
        COUNT(*) as total_readings,
        AVG(value) as avg_blood_sugar,
        MIN(value) as min_value,
        MAX(value) as max_value,
        COUNT(DISTINCT DATE(timestamp)) as days_with_data
    FROM blood_sugar_levels
    """
    return query(sql)

def get_meal_summary():
    """Get summary of meal data"""
    sql = """
    SELECT 
        COUNT(*) as total_meals,
        SUM(total_calories) as total_calories,
        AVG(total_calories) as avg_calories_per_meal,
        SUM(total_carbs) as total_carbs,
        SUM(total_protein) as total_protein,
        SUM(total_fat) as total_fat,
        COUNT(DISTINCT DATE(timestamp)) as days_with_meals
    FROM meal_logs
    """
    return query(sql)

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("📖 Usage Examples:")
        print("=" * 50)
        print("  python query_database.py tables                    # List all tables")
        print("  python query_database.py structure <table_name>    # Show table structure")
        print("  python query_database.py query '<SQL query>'       # Execute SQL query")
        print("  python query_database.py blood_sugar               # Blood sugar summary")
        print("  python query_database.py meals                     # Meal summary")
        print("\n📝 Example Queries:")
        print("  python query_database.py query 'SELECT * FROM blood_sugar_levels LIMIT 10'")
        print("  python query_database.py query 'SELECT * FROM meal_logs ORDER BY timestamp DESC LIMIT 5'")
        print("  python query_database.py query 'SELECT meal_type, COUNT(*) FROM meal_logs GROUP BY meal_type'")
        return
    
    command = sys.argv[1]
    
    if command == "tables":
        list_tables()
    
    elif command == "structure":
        if len(sys.argv) < 3:
            print("❌ Please specify a table name")
            print("   Usage: python query_database.py structure <table_name>")
            return
        show_table_structure(sys.argv[2])
    
    elif command == "query":
        if len(sys.argv) < 3:
            print("❌ Please provide a SQL query")
            print("   Usage: python query_database.py query '<SQL query>'")
            return
        query(sys.argv[2])
    
    elif command == "blood_sugar":
        get_blood_sugar_summary()
    
    elif command == "meals":
        get_meal_summary()
    
    else:
        print(f"❌ Unknown command: {command}")
        print("   Run without arguments to see usage examples")

if __name__ == "__main__":
    main()

