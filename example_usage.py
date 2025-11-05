#!/usr/bin/env python3
"""
Example usage of the Diabetic Agent
This script demonstrates how to use the agent programmatically
"""

from datetime import datetime, timedelta
from diabetic_agent.agent import DiabeticAgent
from diabetic_agent.models import BloodSugarLevel, MealLog, InsulinDose, HealthStats

def main():
    """Demonstrate Diabetic Agent usage"""
    print("🏥 Diabetic Agent - Example Usage")
    print("=" * 50)
    
    # Initialize the agent
    print("1. Initializing Diabetic Agent...")
    agent = DiabeticAgent(user_id=1)
    
    # Setup user profile
    print("2. Setting up user profile...")
    profile = agent.setup_user_profile(
        name="John Doe",
        age=45,
        diabetes_type="Type 2",
        diagnosis_date="2020-01-15",
        medications=["Metformin 500mg twice daily"],
        dietary_restrictions=["Low-carb"],
        allergies=["Nuts"],
        target_range={'fasting': 70, 'post_meal': 180}
    )
    print(f"✅ Profile created for {profile.name}")
    
    # Add some sample blood sugar readings
    print("3. Adding sample blood sugar readings...")
    sample_readings = [
        (85, "Fasting", "Morning reading"),
        (120, "Pre-meal", "Before breakfast"),
        (180, "Post-meal", "2 hours after breakfast"),
        (95, "Pre-meal", "Before lunch"),
        (140, "Post-meal", "2 hours after lunch"),
        (110, "Pre-meal", "Before dinner"),
        (160, "Post-meal", "2 hours after dinner"),
        (90, "Bedtime", "Evening reading")
    ]
    
    for value, measurement_type, notes in sample_readings:
        reading = agent.add_blood_sugar_reading(value, measurement_type, notes)
        print(f"   Added: {value} mg/dL ({measurement_type})")
    
    # Log a sample meal
    print("4. Logging a sample meal...")
    meal_items = [
        {"name": "chicken breast", "quantity": 150, "unit": "grams"},
        {"name": "broccoli", "quantity": 100, "unit": "grams"},
        {"name": "brown rice", "quantity": 80, "unit": "grams"}
    ]
    meal_log = agent.log_meal("Dinner", meal_items, "Balanced meal")
    print(f"   Logged meal: {meal_log.total_calories:.0f} calories, {meal_log.total_carbs:.1f}g carbs")
    
    # Add insulin dose
    print("5. Adding insulin dose...")
    insulin_dose = agent.add_insulin_dose("Rapid-acting", 8, "Abdomen", "Before dinner")
    print(f"   Added: {insulin_dose.units} units of {insulin_dose.insulin_type}")
    
    # Add health stats
    print("6. Adding health statistics...")
    health_stats = agent.add_health_stats(
        steps=8500,
        weight=75.5,
        workout_duration=30,
        workout_type="Walking",
        sleep_hours=7.5,
        stress_level=3
    )
    print(f"   Added: {health_stats.steps} steps, {health_stats.weight}kg, {health_stats.sleep_hours}h sleep")
    
    # Get comprehensive analysis
    print("7. Running comprehensive analysis...")
    analysis = agent.get_comprehensive_analysis(days=7)
    print(f"   Average blood sugar: {analysis.average_blood_sugar:.1f} mg/dL")
    print(f"   Time in range: {analysis.time_in_range:.1f}%")
    print(f"   Patterns identified: {len(analysis.patterns)}")
    print(f"   Recommendations: {len(analysis.recommendations)}")
    
    # Get recipe recommendations
    print("8. Getting recipe recommendations...")
    recipes = agent.get_recipe_recommendations(meal_type="dinner", max_carbs=30)
    print(f"   Found {len(recipes)} recommended recipes")
    if recipes:
        print(f"   Top recommendation: {recipes[0].name} (Score: {recipes[0].diabetes_friendly_score}/10)")
    
    # Chat with the agent
    print("9. Chatting with AI assistant...")
    chat_responses = [
        "What's my average blood sugar?",
        "Why is my blood sugar high after meals?",
        "Can you suggest some low-carb recipes?",
        "What should I do if my blood sugar is 60?"
    ]
    
    for question in chat_responses:
        print(f"   Q: {question}")
        response = agent.chat_with_agent(question)
        print(f"   A: {response[:100]}...")
        print()
    
    # Get daily summary
    print("10. Getting daily summary...")
    daily_summary = agent.get_daily_summary()
    print(f"   Blood sugar readings: {daily_summary['blood_sugar']['readings']}")
    print(f"   Total calories: {daily_summary['nutrition']['calories']:.0f}")
    print(f"   Total insulin: {daily_summary['insulin']['total_units']} units")
    
    # Emergency guidance example
    print("11. Emergency guidance example...")
    emergency_guidance = agent.get_emergency_guidance(65)  # Low blood sugar
    print(f"   Situation: {emergency_guidance['situation']}")
    print(f"   First action: {emergency_guidance['immediate_actions'][0]}")
    
    print("\n🎉 Example completed successfully!")
    print("🚀 To use the web interface, run: streamlit run app.py")

if __name__ == "__main__":
    main()

