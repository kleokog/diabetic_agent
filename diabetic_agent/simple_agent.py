"""
Simplified Diabetic Agent - Works without complex dependencies
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import os

from .models import (
    BloodSugarLevel, MealLog, InsulinDose, HealthStats, 
    UserProfile, AnalysisResult, Recipe, ChatMessage
)
from .database import DatabaseManager


class SimpleDiabeticAgent:
    """Simplified diabetic agent without complex dependencies"""
    
    def __init__(self, user_id: int = 1, db_path: str = "diabetic_agent.db"):
        self.user_id = user_id
        self.db = DatabaseManager(db_path)
        self.user_profile = None
        
        # Simple food database
        self.food_db = {
            "chicken breast": {"calories": 165, "carbs": 0, "protein": 31, "fat": 3.6},
            "brown rice": {"calories": 112, "carbs": 22, "protein": 2.6, "fat": 0.9},
            "broccoli": {"calories": 34, "carbs": 7, "protein": 2.8, "fat": 0.4},
            "salmon": {"calories": 208, "carbs": 0, "protein": 25, "fat": 12},
            "eggs": {"calories": 155, "carbs": 1.1, "protein": 13, "fat": 11},
            "apple": {"calories": 52, "carbs": 14, "protein": 0.3, "fat": 0.2},
            "banana": {"calories": 89, "carbs": 23, "protein": 1.1, "fat": 0.3},
            "greek yogurt": {"calories": 100, "carbs": 6, "protein": 10, "fat": 0.4},
            "quinoa": {"calories": 120, "carbs": 22, "protein": 4.4, "fat": 1.9},
            "sweet potato": {"calories": 86, "carbs": 20, "protein": 1.6, "fat": 0.1}
        }
        
        # Simple recipe database
        self.recipes = [
            {
                "name": "Grilled Chicken with Vegetables",
                "description": "Low-carb, high-protein meal",
                "ingredients": ["chicken breast", "broccoli", "bell peppers"],
                "instructions": [
                    "Season chicken with herbs and grill for 6-8 minutes per side",
                    "Steam broccoli until tender",
                    "Sauté bell peppers until soft",
                    "Serve together"
                ],
                "nutrition": {"calories": 300, "carbs": 12, "protein": 35, "fat": 8},
                "diabetes_score": 9.0
            },
            {
                "name": "Greek Yogurt Parfait",
                "description": "Protein-rich breakfast",
                "ingredients": ["greek yogurt", "berries", "almonds"],
                "instructions": [
                    "Layer Greek yogurt in a bowl",
                    "Top with fresh berries",
                    "Sprinkle with chopped almonds"
                ],
                "nutrition": {"calories": 250, "carbs": 18, "protein": 20, "fat": 12},
                "diabetes_score": 8.5
            },
            {
                "name": "Salmon with Quinoa",
                "description": "Omega-3 rich meal",
                "ingredients": ["salmon", "quinoa", "spinach"],
                "instructions": [
                    "Bake salmon at 400°F for 12-15 minutes",
                    "Cook quinoa according to package directions",
                    "Sauté spinach with garlic",
                    "Serve together"
                ],
                "nutrition": {"calories": 420, "carbs": 25, "protein": 30, "fat": 18},
                "diabetes_score": 9.0
            }
        ]
    
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
        
        self.user_profile = profile
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
    
    def log_meal(self, meal_type: str, food_items: List[str], 
                 quantities: List[float], notes: str = None) -> Dict[str, Any]:
        """Log a meal with food items"""
        total_calories = 0
        total_carbs = 0
        total_protein = 0
        total_fat = 0
        
        meal_details = []
        
        for food, quantity in zip(food_items, quantities):
            if food.lower() in self.food_db:
                nutrition = self.food_db[food.lower()]
                multiplier = quantity / 100  # Assuming quantity is in grams
                
                calories = nutrition["calories"] * multiplier
                carbs = nutrition["carbs"] * multiplier
                protein = nutrition["protein"] * multiplier
                fat = nutrition["fat"] * multiplier
                
                total_calories += calories
                total_carbs += carbs
                total_protein += protein
                total_fat += fat
                
                meal_details.append({
                    "food": food,
                    "quantity": quantity,
                    "calories": calories,
                    "carbs": carbs,
                    "protein": protein,
                    "fat": fat
                })
        
        meal_log = {
            "timestamp": datetime.now(),
            "meal_type": meal_type,
            "food_items": meal_details,
            "total_calories": total_calories,
            "total_carbs": total_carbs,
            "total_protein": total_protein,
            "total_fat": total_fat,
            "notes": notes
        }
        
        return meal_log
    
    def get_blood_sugar_analysis(self, days: int = 7) -> Dict[str, Any]:
        """Get blood sugar analysis"""
        blood_sugar_data = self.db.get_blood_sugar_levels(self.user_id, days)
        
        if not blood_sugar_data:
            return {"error": "No blood sugar data available"}
        
        values = [bs.value for bs in blood_sugar_data]
        
        analysis = {
            "total_readings": len(values),
            "average": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "time_in_range": self._calculate_time_in_range(values),
            "patterns": self._identify_simple_patterns(values),
            "recommendations": self._generate_simple_recommendations(values)
        }
        
        return analysis
    
    def _calculate_time_in_range(self, values: List[float]) -> float:
        """Calculate percentage of time in target range"""
        target_min, target_max = 70, 180
        in_range = sum(1 for v in values if target_min <= v <= target_max)
        return (in_range / len(values)) * 100
    
    def _identify_simple_patterns(self, values: List[float]) -> List[str]:
        """Identify simple patterns in blood sugar data"""
        patterns = []
        
        avg = sum(values) / len(values)
        
        if avg > 180:
            patterns.append("High average blood sugar")
        elif avg < 70:
            patterns.append("Low average blood sugar")
        
        if max(values) > 300:
            patterns.append("Very high readings detected")
        
        if min(values) < 50:
            patterns.append("Very low readings detected")
        
        return patterns
    
    def _generate_simple_recommendations(self, values: List[float]) -> List[str]:
        """Generate simple recommendations"""
        recommendations = []
        
        avg = sum(values) / len(values)
        
        if avg > 180:
            recommendations.append("Consider reducing carb intake")
            recommendations.append("Check with your doctor about insulin adjustments")
        elif avg < 70:
            recommendations.append("Monitor for hypoglycemia")
            recommendations.append("Consider reducing insulin doses")
        
        if max(values) > 300:
            recommendations.append("Seek immediate medical attention for very high readings")
        
        if min(values) < 50:
            recommendations.append("Keep glucose tablets available for low readings")
        
        return recommendations
    
    def get_recipe_recommendations(self, max_carbs: int = 30) -> List[Dict[str, Any]]:
        """Get recipe recommendations"""
        recommendations = []
        
        for recipe in self.recipes:
            if recipe["nutrition"]["carbs"] <= max_carbs:
                recommendations.append(recipe)
        
        return recommendations[:3]  # Return top 3
    
    def chat_with_agent(self, message: str) -> str:
        """Simple chat with the agent"""
        message_lower = message.lower()
        
        if "blood sugar" in message_lower or "glucose" in message_lower:
            analysis = self.get_blood_sugar_analysis()
            if "error" not in analysis:
                return f"Your average blood sugar is {analysis['average']:.1f} mg/dL. Time in range: {analysis['time_in_range']:.1f}%"
            else:
                return "I don't have enough blood sugar data to analyze. Please log some readings first."
        
        elif "recipe" in message_lower or "food" in message_lower:
            recipes = self.get_recipe_recommendations()
            if recipes:
                recipe_names = [r["name"] for r in recipes]
                return f"Here are some diabetes-friendly recipes: {', '.join(recipe_names)}"
            else:
                return "I can suggest some low-carb recipes. What type of meal are you looking for?"
        
        elif "help" in message_lower:
            return "I can help you with blood sugar tracking, meal planning, and recipe suggestions. What would you like to know?"
        
        else:
            return "I'm here to help with your diabetes management! I can assist with blood sugar analysis, meal planning, and recipe suggestions."
    
    def get_emergency_guidance(self, current_blood_sugar: float) -> Dict[str, Any]:
        """Get emergency guidance based on current blood sugar"""
        if current_blood_sugar < 70:
            return {
                "situation": "Hypoglycemia (Low Blood Sugar)",
                "immediate_actions": [
                    "Eat 15g of fast-acting carbs (4 glucose tablets, 4oz juice, or 1 tbsp honey)",
                    "Wait 15 minutes and recheck blood sugar",
                    "If still low, repeat with another 15g of carbs"
                ],
                "follow_up": "Monitor blood sugar every 15 minutes until stable"
            }
        elif current_blood_sugar > 300:
            return {
                "situation": "Severe Hyperglycemia",
                "immediate_actions": [
                    "Check for ketones if you have a meter",
                    "Take correction insulin as prescribed",
                    "Drink plenty of water"
                ],
                "warning": "If you have ketones or feel very ill, seek medical attention immediately"
            }
        elif current_blood_sugar > 180:
            return {
                "situation": "Hyperglycemia (High Blood Sugar)",
                "immediate_actions": [
                    "Take correction insulin if prescribed",
                    "Drink water to stay hydrated",
                    "Avoid high-carb foods"
                ],
                "follow_up": "Recheck blood sugar in 2 hours"
            }
        else:
            return {
                "situation": "Normal Blood Sugar",
                "message": "Your blood sugar is within the target range. Keep up the good work!"
            }

