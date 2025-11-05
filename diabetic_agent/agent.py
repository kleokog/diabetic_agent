"""
Main Diabetic Agent class that coordinates all components
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import json
import os

from .models import (
    BloodSugarLevel, MealLog, InsulinDose, HealthStats, 
    UserProfile, AnalysisResult, Recipe, ChatMessage
)
from .database import DatabaseManager
from .image_analyzer import BloodSugarChartAnalyzer
from .food_tracker import FoodTracker
from .ai_analyzer import BloodSugarAnalyzer
from .recipe_recommender import RecipeRecommender


class DiabeticAgent:
    """Main AI agent for diabetes management"""
    
    def __init__(self, user_id: int = 1, db_path: str = "diabetic_agent.db"):
        self.user_id = user_id
        self.db = DatabaseManager(db_path)
        self.image_analyzer = BloodSugarChartAnalyzer()
        self.food_tracker = FoodTracker()
        self.ai_analyzer = BloodSugarAnalyzer()
        self.recipe_recommender = RecipeRecommender()
        
        # Load user profile
        self.user_profile = self.db.get_user_profile(user_id)
        if self.user_profile:
            self.ai_analyzer.user_profile = self.user_profile
            self.recipe_recommender.user_profile = self.user_profile
    
    def setup_user_profile(self, name: str, age: int, diabetes_type: str, 
                          diagnosis_date: str, **kwargs) -> UserProfile:
        """Set up user profile"""
        profile = UserProfile(
            name=name,
            age=age,
            diabetes_type=diabetes_type,
            diagnosis_date=datetime.strptime(diagnosis_date, "%Y-%m-%d").date(),
            current_medications=kwargs.get('medications', []),
            target_blood_sugar_range=kwargs.get('target_range', {
                'fasting': 70,
                'post_meal': 180
            }),
            dietary_restrictions=kwargs.get('dietary_restrictions', []),
            allergies=kwargs.get('allergies', []),
            preferences=kwargs.get('preferences', {})
        )
        
        # Save to database
        self.db.add_user_profile(profile, self.user_id)
        self.user_profile = profile
        self.ai_analyzer.user_profile = profile
        self.recipe_recommender.user_profile = profile
        
        return profile
    
    def add_blood_sugar_reading(self, value: float, measurement_type: str = "manual", 
                               notes: str = None) -> BloodSugarLevel:
        """Add a blood sugar reading"""
        reading = BloodSugarLevel(
            timestamp=datetime.now(),
            value=value,
            measurement_type=measurement_type,
            notes=notes
        )
        
        self.db.add_blood_sugar_level(reading, self.user_id)
        return reading
    
    def analyze_blood_sugar_chart(self, image_path: str) -> Tuple[List[BloodSugarLevel], Dict[str, Any]]:
        """Analyze blood sugar chart from image"""
        try:
            # Extract blood sugar data from image
            blood_sugar_data = self.image_analyzer.extract_blood_sugar_data(image_path)
            
            # Save extracted data to database
            for reading in blood_sugar_data:
                self.db.add_blood_sugar_level(reading, self.user_id)
            
            # Analyze patterns
            analysis = self.image_analyzer.analyze_chart_patterns(blood_sugar_data)
            
            return blood_sugar_data, analysis
            
        except Exception as e:
            return [], {"error": f"Failed to analyze chart: {str(e)}"}
    
    def log_meal(self, meal_type: str, food_items: List[Dict[str, Any]], 
                 notes: str = None) -> MealLog:
        """Log a meal with food items"""
        # Convert food items to FoodItem objects
        food_objects = []
        for item in food_items:
            food_item = self.food_tracker.add_food_item(
                name=item['name'],
                quantity=item['quantity'],
                unit=item.get('unit', 'grams')
            )
            food_objects.append(food_item)
        
        # Create meal log
        meal_log = self.food_tracker.create_meal_log(meal_type, food_objects, notes)
        
        # Save to database
        self.db.add_meal_log(meal_log, self.user_id)
        
        return meal_log
    
    def add_insulin_dose(self, insulin_type: str, units: float, 
                       injection_site: str, notes: str = None) -> InsulinDose:
        """Add insulin dose record"""
        dose = InsulinDose(
            timestamp=datetime.now(),
            insulin_type=insulin_type,
            units=units,
            injection_site=injection_site,
            notes=notes
        )
        
        self.db.add_insulin_dose(dose, self.user_id)
        return dose
    
    def add_health_stats(self, steps: int = None, weight: float = None, 
                        workout_duration: int = None, workout_type: str = None,
                        sleep_hours: float = None, stress_level: int = None,
                        notes: str = None) -> HealthStats:
        """Add health statistics"""
        stats = HealthStats(
            date=datetime.now().date(),
            steps=steps,
            weight=weight,
            workout_duration=workout_duration,
            workout_type=workout_type,
            sleep_hours=sleep_hours,
            stress_level=stress_level,
            notes=notes
        )
        
        self.db.add_health_stats(stats, self.user_id)
        return stats
    
    def get_comprehensive_analysis(self, days: int = 30) -> AnalysisResult:
        """Get comprehensive analysis of diabetes management"""
        # Get data from database
        blood_sugar_data = self.db.get_blood_sugar_levels(self.user_id, days)
        meal_logs = self.db.get_meal_logs(self.user_id, days)
        insulin_doses = self.db.get_insulin_doses(self.user_id, days)
        health_stats = self.db.get_health_stats(self.user_id, days)
        
        # Perform AI analysis
        analysis = self.ai_analyzer.analyze_patterns(
            blood_sugar_data, meal_logs, insulin_doses, health_stats
        )
        
        # Save analysis result
        self.db.save_analysis_result(analysis, self.user_id)
        
        return analysis
    
    def get_recipe_recommendations(self, meal_type: str = "any", 
                                 max_carbs: int = 30) -> List[Recipe]:
        """Get personalized recipe recommendations"""
        # Get recent blood sugar patterns
        blood_sugar_data = self.db.get_blood_sugar_levels(self.user_id, 7)
        analysis = self.ai_analyzer.analyze_patterns(blood_sugar_data)
        
        # Get dietary restrictions from user profile
        dietary_restrictions = []
        if self.user_profile:
            dietary_restrictions = self.user_profile.dietary_restrictions
        
        # Get recommendations
        recommendations = self.recipe_recommender.recommend_recipes(
            blood_sugar_patterns=analysis.patterns,
            meal_type=meal_type,
            max_carbs=max_carbs,
            dietary_restrictions=dietary_restrictions
        )
        
        return recommendations
    
    def get_meal_plan(self, days: int = 7) -> Dict[str, List[Recipe]]:
        """Get personalized meal plan"""
        return self.recipe_recommender.get_meal_plan_suggestions(days)
    
    def analyze_meal_impact(self, meal_log: MealLog) -> Dict[str, Any]:
        """Analyze potential impact of a meal on blood sugar"""
        return self.food_tracker.analyze_meal_impact(meal_log)
    
    def get_daily_summary(self, date: datetime = None) -> Dict[str, Any]:
        """Get daily summary of diabetes management"""
        if date is None:
            date = datetime.now()
        
        # Get daily data
        blood_sugar_data = self.db.get_blood_sugar_levels(self.user_id, 1)
        meal_logs = self.db.get_meal_logs(self.user_id, 1)
        insulin_doses = self.db.get_insulin_doses(self.user_id, 1)
        health_stats = self.db.get_health_stats(self.user_id, 1)
        
        # Calculate daily nutrition
        daily_nutrition = self.food_tracker.get_daily_nutrition_summary(date)
        
        # Get blood sugar statistics
        if blood_sugar_data:
            bs_values = [bs.value for bs in blood_sugar_data]
            bs_stats = {
                "average": sum(bs_values) / len(bs_values),
                "min": min(bs_values),
                "max": max(bs_values),
                "readings": len(bs_values)
            }
        else:
            bs_stats = {"average": 0, "min": 0, "max": 0, "readings": 0}
        
        # Get insulin summary
        total_insulin = sum(dose.units for dose in insulin_doses)
        
        # Get health stats
        health_summary = {}
        if health_stats:
            health = health_stats[0]
            health_summary = {
                "steps": health.steps,
                "weight": health.weight,
                "workout": health.workout_duration,
                "sleep": health.sleep_hours,
                "stress": health.stress_level
            }
        
        return {
            "date": date.strftime("%Y-%m-%d"),
            "blood_sugar": bs_stats,
            "nutrition": daily_nutrition,
            "insulin": {"total_units": total_insulin, "doses": len(insulin_doses)},
            "health": health_summary,
            "meals": len(meal_logs)
        }
    
    def chat_with_agent(self, message: str) -> str:
        """Chat with the AI agent"""
        # Get recent data for context
        blood_sugar_data = self.db.get_blood_sugar_levels(self.user_id, 7)
        analysis = self.ai_analyzer.analyze_patterns(blood_sugar_data)
        
        # Generate response based on message content
        response = self._generate_chat_response(message, analysis)
        
        # Save chat message
        chat_message = ChatMessage(
            timestamp=datetime.now(),
            user_message=message,
            agent_response=response,
            message_type="general"
        )
        self.db.add_chat_message(chat_message, self.user_id)
        
        return response
    
    def _generate_chat_response(self, message: str, analysis: AnalysisResult) -> str:
        """Generate AI response to user message"""
        message_lower = message.lower()
        
        # Blood sugar related questions
        if any(word in message_lower for word in ["blood sugar", "glucose", "reading"]):
            if analysis.average_blood_sugar > 180:
                return f"Your average blood sugar is {analysis.average_blood_sugar:.1f} mg/dL, which is above the target range. I recommend focusing on lower-carb meals and consistent insulin timing. Would you like me to suggest some recipes?"
            elif analysis.average_blood_sugar < 70:
                return f"Your average blood sugar is {analysis.average_blood_sugar:.1f} mg/dL, which is below the target range. Make sure to eat regular meals and consider reducing insulin doses. Do you need help with meal planning?"
            else:
                return f"Your average blood sugar is {analysis.average_blood_sugar:.1f} mg/dL, which is within the target range. Great job! Your time in range is {analysis.time_in_range:.1f}%. Keep up the good work!"
        
        # Pattern related questions
        elif any(word in message_lower for word in ["pattern", "trend", "why"]):
            if analysis.patterns:
                pattern_descriptions = [f"- {pattern.pattern_type}: {pattern.severity} severity" 
                                       for pattern in analysis.patterns]
                return f"I've identified these patterns in your blood sugar:\n" + "\n".join(pattern_descriptions) + "\n\nWould you like specific recommendations for managing these patterns?"
            else:
                return "I don't see any significant patterns in your recent blood sugar data. This is good! Keep monitoring and let me know if you notice any changes."
        
        # Recipe related questions
        elif any(word in message_lower for word in ["recipe", "food", "meal", "eat"]):
            recommendations = self.get_recipe_recommendations()
            if recommendations:
                recipe_names = [recipe.name for recipe in recommendations[:3]]
                return f"Here are some diabetes-friendly recipes I recommend: {', '.join(recipe_names)}. Would you like the full recipe details for any of these?"
            else:
                return "I'd be happy to suggest some recipes! What type of meal are you looking for (breakfast, lunch, dinner, or snack)?"
        
        # General health questions
        elif any(word in message_lower for word in ["exercise", "workout", "activity"]):
            return "Regular exercise is great for blood sugar control! Aim for at least 150 minutes of moderate activity per week. Remember to check your blood sugar before and after exercise, and have a carb snack if needed."
        
        # Default response
        else:
            return "I'm here to help you manage your diabetes! I can help with blood sugar analysis, meal planning, recipe suggestions, and general diabetes management advice. What would you like to know?"
    
    def get_emergency_guidance(self, current_blood_sugar: float) -> Dict[str, Any]:
        """Get emergency guidance based on current blood sugar"""
        if current_blood_sugar < 70:
            return {
                "situation": "Hypoglycemia (Low Blood Sugar)",
                "immediate_actions": [
                    "Eat 15g of fast-acting carbs (4 glucose tablets, 4oz juice, or 1 tbsp honey)",
                    "Wait 15 minutes and recheck blood sugar",
                    "If still low, repeat with another 15g of carbs",
                    "Once blood sugar is above 70, eat a protein snack to prevent rebound"
                ],
                "recipes": self.recipe_recommender.get_emergency_low_recipes(),
                "follow_up": "Monitor blood sugar every 15 minutes until stable"
            }
        elif current_blood_sugar > 300:
            return {
                "situation": "Severe Hyperglycemia",
                "immediate_actions": [
                    "Check for ketones if you have a meter",
                    "Take correction insulin as prescribed",
                    "Drink plenty of water",
                    "Avoid exercise until blood sugar is below 250"
                ],
                "warning": "If you have ketones or feel very ill, seek medical attention immediately",
                "follow_up": "Recheck blood sugar in 1 hour and contact your doctor if not improving"
            }
        elif current_blood_sugar > 180:
            return {
                "situation": "Hyperglycemia (High Blood Sugar)",
                "immediate_actions": [
                    "Take correction insulin if prescribed",
                    "Drink water to stay hydrated",
                    "Avoid high-carb foods",
                    "Consider light exercise if feeling well"
                ],
                "follow_up": "Recheck blood sugar in 2 hours"
            }
        else:
            return {
                "situation": "Normal Blood Sugar",
                "message": "Your blood sugar is within the target range. Keep up the good work!",
                "maintenance": "Continue with your regular diabetes management routine"
            }

