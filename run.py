#!/usr/bin/env python3
"""
Simple launcher script for the Diabetic Agent
"""

import subprocess
import sys
import os
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import streamlit
        import pandas
        import plotly
        import opencv_python
        import easyocr
        import sklearn
        print("✅ All dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def main():
    """Main launcher function"""
    print("🏥 Diabetic Agent - AI-Powered Diabetes Management")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("app.py").exists():
        print("❌ Error: app.py not found. Please run this script from the project directory.")
        sys.exit(1)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    print("🚀 Starting Diabetic Agent...")
    print("📱 The web interface will open in your browser")
    print("🔗 URL: http://localhost:8501")
    print("=" * 50)
    
    try:
        # Run the Streamlit app
        subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"], check=True)
    except KeyboardInterrupt:
        print("\n👋 Diabetic Agent stopped. Thank you for using our service!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting the application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

