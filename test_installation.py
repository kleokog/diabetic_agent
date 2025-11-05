#!/usr/bin/env python3
"""
Test script to verify Diabetic Agent installation
"""

import sys
import importlib
from pathlib import Path

def test_imports():
    """Test if all required modules can be imported"""
    print("🧪 Testing Diabetic Agent Installation")
    print("=" * 40)
    
    # Core dependencies
    dependencies = [
        ("streamlit", "Web interface"),
        ("pandas", "Data processing"),
        ("numpy", "Numerical computing"),
        ("plotly", "Data visualization"),
        ("sklearn", "Machine learning"),
        ("cv2", "Computer vision (OpenCV)"),
        ("easyocr", "OCR functionality"),
        ("PIL", "Image processing"),
        ("sqlite3", "Database"),
    ]
    
    failed_imports = []
    
    for module, description in dependencies:
        try:
            if module == "cv2":
                import cv2
            elif module == "sqlite3":
                import sqlite3
            else:
                importlib.import_module(module)
            print(f"✅ {module} - {description}")
        except ImportError as e:
            print(f"❌ {module} - {description} (Error: {e})")
            failed_imports.append(module)
    
    return failed_imports

def test_diabetic_agent_modules():
    """Test if Diabetic Agent modules can be imported"""
    print("\n🏥 Testing Diabetic Agent Modules")
    print("=" * 40)
    
    modules = [
        "diabetic_agent.models",
        "diabetic_agent.database", 
        "diabetic_agent.image_analyzer",
        "diabetic_agent.food_tracker",
        "diabetic_agent.ai_analyzer",
        "diabetic_agent.recipe_recommender",
        "diabetic_agent.agent"
    ]
    
    failed_modules = []
    
    for module in modules:
        try:
            importlib.import_module(module)
            print(f"✅ {module}")
        except ImportError as e:
            print(f"❌ {module} (Error: {e})")
            failed_modules.append(module)
    
    return failed_modules

def test_database_creation():
    """Test if database can be created"""
    print("\n💾 Testing Database Creation")
    print("=" * 40)
    
    try:
        from diabetic_agent.database import DatabaseManager
        
        # Create a test database
        test_db = DatabaseManager("test_diabetic_agent.db")
        print("✅ Database created successfully")
        
        # Clean up test database
        import os
        if os.path.exists("test_diabetic_agent.db"):
            os.remove("test_diabetic_agent.db")
            print("✅ Test database cleaned up")
        
        return True
    except Exception as e:
        print(f"❌ Database creation failed: {e}")
        return False

def main():
    """Main test function"""
    print("🏥 Diabetic Agent - Installation Test")
    print("=" * 50)
    
    # Test basic imports
    failed_deps = test_imports()
    
    # Test diabetic agent modules
    failed_modules = test_diabetic_agent_modules()
    
    # Test database creation
    db_success = test_database_creation()
    
    # Summary
    print("\n📊 Test Summary")
    print("=" * 40)
    
    if not failed_deps and not failed_modules and db_success:
        print("🎉 All tests passed! Diabetic Agent is ready to use.")
        print("\n🚀 To start the application, run:")
        print("   python run.py")
        print("   or")
        print("   streamlit run app.py")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        if failed_deps:
            print(f"Missing dependencies: {', '.join(failed_deps)}")
            print("Run: pip install -r requirements.txt")
        if failed_modules:
            print(f"Failed modules: {', '.join(failed_modules)}")
        if not db_success:
            print("Database creation failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

