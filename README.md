# 🏥 Diabetic Agent - AI-Powered Diabetes Management Assistant

A comprehensive AI-powered diabetes management system that acts as your personalized doctor, helping you track, analyze, and manage your diabetes effectively.

## 🌟 Features

### 📊 **Blood Sugar Tracking & Analysis**
- Manual blood sugar entry with categorization
- **AI-powered image analysis** of blood sugar charts using computer vision
- Pattern recognition for dawn phenomenon, post-meal spikes, and nocturnal hypoglycemia
- Time-in-range calculations and trend analysis

### 🍽️ **Food Logging & Nutrition**
- Comprehensive food database with nutritional information
- Macro tracking (carbs, protein, fat, fiber)
- Meal impact analysis on blood sugar
- Food substitution suggestions

### 👨‍🍳 **Personalized Recipe Recommendations**
- AI-powered recipe suggestions based on blood sugar patterns
- Diabetes-friendly scoring system
- Meal planning for different times of day
- Emergency low/high blood sugar recipes

### 🤖 **AI Chat Assistant**
- Personalized diabetes management advice
- Pattern explanation and recommendations
- Emergency guidance for critical blood sugar levels
- Natural language interaction

### 📈 **Comprehensive Analytics**
- Blood sugar pattern analysis using machine learning
- Risk factor identification
- Positive trend recognition
- Personalized recommendations

### 💾 **Data Management**
- SQLite database for data persistence
- User profile management
- Historical data analysis
- Export capabilities

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Installation

1. **Clone or download the project**
   ```bash
   cd /Users/kleomeniskogias/Cursor\ Code
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   streamlit run app.py
   ```

4. **Open your browser**
   - The app will automatically open at `http://localhost:8501`
   - If it doesn't open automatically, navigate to the URL manually

## 📱 How to Use

### 1. **Initial Setup**
- Set up your user profile with diabetes type, medications, and preferences
- Configure target blood sugar ranges
- Set dietary restrictions and allergies

### 2. **Daily Tracking**
- **Blood Sugar**: Log readings manually or upload chart images for AI analysis
- **Food**: Log meals with detailed nutritional information
- **Health Stats**: Track steps, weight, workouts, sleep, and stress levels
- **Insulin**: Record insulin doses and injection sites

### 3. **AI Analysis**
- Get comprehensive analysis of your diabetes patterns
- Receive personalized recommendations
- Chat with the AI assistant for guidance

### 4. **Recipe Recommendations**
- Get personalized recipe suggestions based on your blood sugar patterns
- Access emergency recipes for low/high blood sugar situations
- Plan weekly meal menus

## 🏗️ Architecture

```
diabetic_agent/
├── __init__.py              # Package initialization
├── models.py                # Data models and schemas
├── database.py              # Database operations
├── image_analyzer.py       # Blood sugar chart analysis
├── food_tracker.py         # Food logging and nutrition
├── ai_analyzer.py          # AI pattern recognition
├── recipe_recommender.py   # Recipe recommendations
└── agent.py                # Main agent coordinator

app.py                      # Streamlit web interface
requirements.txt            # Python dependencies
README.md                   # This file
```

## 🔧 Key Components

### **Image Analyzer** (`image_analyzer.py`)
- Uses OpenCV and EasyOCR for blood sugar chart analysis
- Extracts blood sugar values and timestamps from images
- Identifies patterns and generates recommendations

### **Food Tracker** (`food_tracker.py`)
- Comprehensive food database with nutritional information
- Macro tracking and meal impact analysis
- Food substitution suggestions

### **AI Analyzer** (`ai_analyzer.py`)
- Machine learning-powered pattern recognition
- Risk factor identification
- Personalized recommendation generation

### **Recipe Recommender** (`recipe_recommender.py`)
- AI-powered recipe suggestions
- Diabetes-friendly scoring system
- Emergency recipe collection

### **Database Manager** (`database.py`)
- SQLite database operations
- Data persistence and retrieval
- User profile management

## 📊 Data Models

The system tracks several key data types:

- **Blood Sugar Levels**: Timestamp, value, measurement type, notes
- **Meal Logs**: Food items, nutritional information, meal type
- **Insulin Doses**: Type, units, injection site, timing
- **Health Stats**: Steps, weight, workouts, sleep, stress
- **User Profile**: Personal information, preferences, restrictions

## 🎯 AI Features

### **Pattern Recognition**
- Dawn phenomenon detection
- Post-meal hyperglycemia identification
- Nocturnal hypoglycemia patterns
- High variability detection

### **Personalized Recommendations**
- Meal timing suggestions
- Insulin adjustment recommendations
- Exercise guidance
- Stress management tips

### **Emergency Guidance**
- Hypoglycemia treatment protocols
- Hyperglycemia management
- Emergency contact information
- Medication reminders

## 🔒 Privacy & Security

- All data is stored locally in SQLite database
- No cloud storage or external data transmission
- User data remains private and secure
- HIPAA-compliant data handling practices

## 🛠️ Customization

### **Target Ranges**
- Customizable blood sugar targets
- Personalized meal timing
- Individual insulin sensitivity

### **Dietary Preferences**
- Vegetarian/vegan options
- Gluten-free alternatives
- Allergy management
- Cultural food preferences

## 📈 Analytics Dashboard

The web interface provides:
- Real-time blood sugar trends
- Nutritional summaries
- Pattern visualization
- Progress tracking
- Goal setting and monitoring

## 🚨 Emergency Features

### **Hypoglycemia Management**
- Quick glucose recovery recipes
- Stable recovery snacks
- Monitoring protocols

### **Hyperglycemia Response**
- Correction insulin guidance
- Hydration reminders
- Medical contact protocols

## 🔮 Future Enhancements

- Integration with continuous glucose monitors
- Smartphone app development
- Healthcare provider integration
- Advanced machine learning models
- Wearable device connectivity

## 📞 Support

For questions or issues:
1. Check the documentation in each module
2. Review the error messages in the console
3. Ensure all dependencies are properly installed
4. Verify your Python version compatibility

## ⚠️ Medical Disclaimer

This application is for informational purposes only and should not replace professional medical advice. Always consult with your healthcare provider for medical decisions and emergency situations.

## 📄 License

This project is for educational and personal use. Please consult with healthcare professionals for medical advice.

---

**Built with ❤️ for better diabetes management**

