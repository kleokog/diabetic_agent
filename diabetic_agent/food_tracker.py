"""
Food logging and macro tracking system
"""

import json
import requests
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
from dataclasses import dataclass

from .models import FoodItem, MealLog


@dataclass
class NutritionalInfo:
    """Nutritional information for a food item"""
    calories: float
    carbohydrates: float
    protein: float
    fat: float
    fiber: float = 0.0
    sugar: float = 0.0
    sodium: float = 0.0


class FoodDatabase:
    """Database of common foods with nutritional information"""
    
    def __init__(self):
        self.food_db = self._load_food_database()
    
    def _load_food_database(self) -> Dict[str, NutritionalInfo]:
        """Load food database with common foods"""
        return {
            # Grains and Starches
            "white rice": NutritionalInfo(130, 28, 2.7, 0.3, 0.4, 0.1),
            "brown rice": NutritionalInfo(112, 22, 2.6, 0.9, 1.8, 0.4),
            "quinoa": NutritionalInfo(120, 22, 4.4, 1.9, 2.8, 0.9),
            "oats": NutritionalInfo(154, 27, 5.3, 2.6, 4.0, 1.0),
            "whole wheat bread": NutritionalInfo(81, 13.8, 4.0, 1.1, 1.9, 1.4),
            "white bread": NutritionalInfo(75, 14.2, 2.4, 0.9, 0.6, 1.4),
            
            # Proteins
            "chicken breast": NutritionalInfo(165, 0, 31, 3.6, 0, 0),
            "salmon": NutritionalInfo(208, 0, 25, 12, 0, 0),
            "eggs": NutritionalInfo(155, 1.1, 13, 11, 0, 1.1),
            "tofu": NutritionalInfo(76, 1.9, 8, 4.8, 0.3, 0.6),
            "greek yogurt": NutritionalInfo(100, 6, 10, 0.4, 0, 6),
            "cottage cheese": NutritionalInfo(98, 3.4, 11, 4.3, 0, 2.7),
            
            # Vegetables
            "broccoli": NutritionalInfo(34, 7, 2.8, 0.4, 2.6, 1.5),
            "spinach": NutritionalInfo(23, 3.6, 2.9, 0.4, 2.2, 0.4),
            "carrots": NutritionalInfo(41, 10, 0.9, 0.2, 2.8, 4.7),
            "sweet potato": NutritionalInfo(86, 20, 1.6, 0.1, 3.0, 4.2),
            "bell peppers": NutritionalInfo(31, 7, 1.0, 0.3, 2.5, 4.2),
            
            # Fruits
            "apple": NutritionalInfo(52, 14, 0.3, 0.2, 2.4, 10.4),
            "banana": NutritionalInfo(89, 23, 1.1, 0.3, 2.6, 12.2),
            "berries": NutritionalInfo(57, 14, 0.7, 0.3, 2.4, 10),
            "orange": NutritionalInfo(47, 12, 0.9, 0.1, 2.4, 9.4),
            
            # Fats and Oils
            "olive oil": NutritionalInfo(884, 0, 0, 100, 0, 0),
            "avocado": NutritionalInfo(160, 9, 2, 15, 7, 0.7),
            "almonds": NutritionalInfo(579, 22, 21, 50, 12, 4.4),
            "walnuts": NutritionalInfo(654, 14, 15, 65, 6.7, 2.6),
            
            # Dairy
            "milk": NutritionalInfo(42, 5, 3.4, 1, 0, 5),
            "cheese": NutritionalInfo(113, 1, 7, 9, 0, 0.1),
            
            # Legumes
            "black beans": NutritionalInfo(132, 24, 8.9, 0.5, 8.7, 0.3),
            "lentils": NutritionalInfo(116, 20, 9, 0.4, 7.9, 1.8),
            "chickpeas": NutritionalInfo(164, 27, 8.9, 2.6, 7.6, 4.8),
        }
    
    def search_food(self, query: str) -> List[Tuple[str, NutritionalInfo]]:
        """Search for foods in the database"""
        query = query.lower()
        results = []
        
        for food_name, nutrition in self.food_db.items():
            if query in food_name or any(word in food_name for word in query.split()):
                results.append((food_name, nutrition))
        
        return results[:10]  # Return top 10 matches
    
    def get_food_info(self, food_name: str) -> Optional[NutritionalInfo]:
        """Get nutritional information for a specific food"""
        return self.food_db.get(food_name.lower())


class FoodTracker:
    """Main food tracking system"""
    
    def __init__(self):
        self.food_db = FoodDatabase()
        self.meal_logs: List[MealLog] = []
    
    def add_food_item(self, name: str, quantity: float, unit: str = "grams") -> FoodItem:
        """Add a food item to the current meal"""
        # Get nutritional info from database
        nutrition = self.food_db.get_food_info(name)
        
        if not nutrition:
            # If not found, try to search for similar foods
            search_results = self.food_db.search_food(name)
            if search_results:
                # Use the first search result
                name, nutrition = search_results[0]
            else:
                # Create default nutritional info
                nutrition = NutritionalInfo(0, 0, 0, 0)
        
        # Convert quantity to grams if needed
        quantity_grams = self._convert_to_grams(quantity, unit)
        
        # Calculate nutritional values per 100g
        multiplier = quantity_grams / 100.0
        
        return FoodItem(
            name=name,
            quantity=quantity_grams,
            unit="grams",
            calories=nutrition.calories * multiplier,
            carbohydrates=nutrition.carbohydrates * multiplier,
            protein=nutrition.protein * multiplier,
            fat=nutrition.fat * multiplier,
            fiber=nutrition.fiber * multiplier,
            sugar=nutrition.sugar * multiplier
        )
    
    def _convert_to_grams(self, quantity: float, unit: str) -> float:
        """Convert various units to grams"""
        unit_conversions = {
            "grams": 1.0,
            "g": 1.0,
            "kg": 1000.0,
            "pounds": 453.6,
            "lbs": 453.6,
            "ounces": 28.35,
            "oz": 28.35,
            "cups": 240.0,  # Approximate for most foods
            "tablespoons": 15.0,
            "tbsp": 15.0,
            "teaspoons": 5.0,
            "tsp": 5.0,
            "pieces": 50.0,  # Approximate for fruits/vegetables
            "slices": 30.0,  # Approximate for bread
        }
        
        return quantity * unit_conversions.get(unit.lower(), 1.0)
    
    def create_meal_log(self, meal_type: str, food_items: List[FoodItem], 
                       notes: Optional[str] = None) -> MealLog:
        """Create a meal log with food items"""
        # Calculate totals
        total_calories = sum(item.calories for item in food_items)
        total_carbs = sum(item.carbohydrates for item in food_items)
        total_protein = sum(item.protein for item in food_items)
        total_fat = sum(item.fat for item in food_items)
        
        meal_log = MealLog(
            timestamp=datetime.now(),
            meal_type=meal_type,
            food_items=food_items,
            total_calories=total_calories,
            total_carbs=total_carbs,
            total_protein=total_protein,
            total_fat=total_fat,
            notes=notes
        )
        
        self.meal_logs.append(meal_log)
        return meal_log
    
    def get_daily_nutrition_summary(self, date: datetime = None) -> Dict[str, float]:
        """Get daily nutrition summary"""
        if date is None:
            date = datetime.now().date()
        
        daily_meals = [
            meal for meal in self.meal_logs 
            if meal.timestamp.date() == date
        ]
        
        if not daily_meals:
            return {
                "calories": 0,
                "carbohydrates": 0,
                "protein": 0,
                "fat": 0,
                "fiber": 0,
                "sugar": 0
            }
        
        return {
            "calories": sum(meal.total_calories for meal in daily_meals),
            "carbohydrates": sum(meal.total_carbs for meal in daily_meals),
            "protein": sum(meal.total_protein for meal in daily_meals),
            "fat": sum(meal.total_fat for meal in daily_meals),
            "fiber": sum(sum(item.fiber for item in meal.food_items) for meal in daily_meals),
            "sugar": sum(sum(item.sugar for item in meal.food_items) for meal in daily_meals)
        }
    
    def analyze_meal_impact(self, meal_log: MealLog) -> Dict[str, any]:
        """Analyze the potential impact of a meal on blood sugar"""
        analysis = {
            "carb_impact": "Low",
            "glycemic_load": "Low",
            "recommendations": []
        }
        
        total_carbs = meal_log.total_carbs
        total_fiber = sum(item.fiber for item in meal_log.food_items)
        total_sugar = sum(item.sugar for item in meal_log.food_items)
        
        # Calculate net carbs (carbs - fiber)
        net_carbs = total_carbs - total_fiber
        
        # Determine carb impact
        if net_carbs > 60:
            analysis["carb_impact"] = "High"
        elif net_carbs > 30:
            analysis["carb_impact"] = "Medium"
        
        # Calculate glycemic load (simplified)
        glycemic_load = net_carbs * 0.7  # Simplified calculation
        if glycemic_load > 20:
            analysis["glycemic_load"] = "High"
        elif glycemic_load > 10:
            analysis["glycemic_load"] = "Medium"
        
        # Generate recommendations
        if analysis["carb_impact"] == "High":
            analysis["recommendations"].append("Consider reducing portion size or choosing lower-carb alternatives")
        
        if total_fiber < 5:
            analysis["recommendations"].append("Add more fiber-rich foods to slow glucose absorption")
        
        if total_sugar > 20:
            analysis["recommendations"].append("Reduce added sugars in this meal")
        
        if meal_log.total_protein < 15:
            analysis["recommendations"].append("Add protein to help stabilize blood sugar")
        
        return analysis
    
    def suggest_food_substitutions(self, current_food: str, 
                                 target_carbs: float = None) -> List[Tuple[str, NutritionalInfo]]:
        """Suggest lower-carb alternatives for a food"""
        current_nutrition = self.food_db.get_food_info(current_food)
        if not current_nutrition:
            return []
        
        suggestions = []
        current_carbs = current_nutrition.carbohydrates
        
        for food_name, nutrition in self.food_db.food_db.items():
            if nutrition.carbohydrates < current_carbs:
                carb_reduction = current_carbs - nutrition.carbohydrates
                suggestions.append((food_name, nutrition, carb_reduction))
        
        # Sort by carb reduction and return top 5
        suggestions.sort(key=lambda x: x[2], reverse=True)
        return [(name, nutrition) for name, nutrition, _ in suggestions[:5]]
    
    def get_meal_suggestions(self, meal_type: str, 
                           max_carbs: float = 30) -> List[Dict[str, any]]:
        """Get meal suggestions based on carb limits"""
        suggestions = []
        
        # Define meal templates
        meal_templates = {
            "breakfast": [
                {"name": "Greek Yogurt Bowl", "carbs": 15, "protein": 20, "fat": 8},
                {"name": "Eggs with Vegetables", "carbs": 8, "protein": 18, "fat": 12},
                {"name": "Avocado Toast", "carbs": 20, "protein": 8, "fat": 15}
            ],
            "lunch": [
                {"name": "Grilled Chicken Salad", "carbs": 12, "protein": 35, "fat": 15},
                {"name": "Salmon with Vegetables", "carbs": 10, "protein": 25, "fat": 18},
                {"name": "Turkey Lettuce Wraps", "carbs": 8, "protein": 22, "fat": 10}
            ],
            "dinner": [
                {"name": "Baked Fish with Quinoa", "carbs": 25, "protein": 30, "fat": 12},
                {"name": "Stir-fried Tofu", "carbs": 15, "protein": 20, "fat": 14},
                {"name": "Grilled Steak with Vegetables", "carbs": 12, "protein": 35, "fat": 20}
            ]
        }
        
        if meal_type in meal_templates:
            for template in meal_templates[meal_type]:
                if template["carbs"] <= max_carbs:
                    suggestions.append(template)
        
        return suggestions

