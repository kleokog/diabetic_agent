"""
Recipe recommendation system based on blood sugar patterns and dietary needs
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import random

from .models import Recipe, BloodSugarPattern, UserProfile, MealLog


class RecipeRecommender:
    """AI-powered recipe recommendation system for diabetes management"""
    
    def __init__(self, user_profile: Optional[UserProfile] = None):
        self.user_profile = user_profile
        self.recipe_database = self._load_recipe_database()
    
    def _load_recipe_database(self) -> List[Recipe]:
        """Load comprehensive recipe database"""
        return [
            # Low-carb breakfast recipes
            Recipe(
                name="Greek Yogurt Parfait",
                description="Protein-rich breakfast with berries and nuts",
                ingredients=[
                    "1 cup Greek yogurt (unsweetened)",
                    "1/2 cup mixed berries",
                    "2 tbsp chopped almonds",
                    "1 tbsp chia seeds",
                    "1 tsp honey (optional)"
                ],
                instructions=[
                    "Layer Greek yogurt in a bowl",
                    "Top with mixed berries",
                    "Sprinkle with chopped almonds and chia seeds",
                    "Drizzle with honey if desired"
                ],
                nutritional_info={
                    "calories": 280,
                    "carbohydrates": 18,
                    "protein": 20,
                    "fat": 12,
                    "fiber": 8
                },
                diabetes_friendly_score=9.0,
                prep_time=5,
                cook_time=0,
                servings=1
            ),
            
            Recipe(
                name="Vegetable Omelet",
                description="Low-carb, high-protein breakfast",
                ingredients=[
                    "3 large eggs",
                    "1/4 cup diced bell peppers",
                    "1/4 cup spinach",
                    "2 tbsp diced onions",
                    "1 oz cheese (feta or cheddar)",
                    "1 tbsp olive oil",
                    "Salt and pepper to taste"
                ],
                instructions=[
                    "Heat olive oil in a non-stick pan",
                    "Sauté vegetables until tender",
                    "Beat eggs and pour over vegetables",
                    "Add cheese and cook until set",
                    "Season with salt and pepper"
                ],
                nutritional_info={
                    "calories": 320,
                    "carbohydrates": 8,
                    "protein": 22,
                    "fat": 22,
                    "fiber": 2
                },
                diabetes_friendly_score=9.5,
                prep_time=10,
                cook_time=8,
                servings=1
            ),
            
            # Low-carb lunch recipes
            Recipe(
                name="Grilled Chicken Caesar Salad",
                description="Protein-rich salad with healthy fats",
                ingredients=[
                    "6 oz grilled chicken breast",
                    "2 cups romaine lettuce",
                    "1/4 cup parmesan cheese",
                    "2 tbsp Caesar dressing (low-carb)",
                    "1 tbsp olive oil",
                    "1 tsp lemon juice"
                ],
                instructions=[
                    "Grill chicken breast and slice",
                    "Toss lettuce with dressing and olive oil",
                    "Top with chicken and parmesan",
                    "Drizzle with lemon juice"
                ],
                nutritional_info={
                    "calories": 380,
                    "carbohydrates": 6,
                    "protein": 45,
                    "fat": 18,
                    "fiber": 3
                },
                diabetes_friendly_score=9.0,
                prep_time=15,
                cook_time=12,
                servings=1
            ),
            
            Recipe(
                name="Salmon with Roasted Vegetables",
                description="Omega-3 rich meal with low glycemic vegetables",
                ingredients=[
                    "6 oz salmon fillet",
                    "1 cup broccoli florets",
                    "1 cup cauliflower florets",
                    "1/2 cup bell peppers",
                    "2 tbsp olive oil",
                    "1 tsp herbs (thyme, rosemary)",
                    "Salt and pepper to taste"
                ],
                instructions=[
                    "Preheat oven to 400°F",
                    "Season salmon with herbs, salt, and pepper",
                    "Toss vegetables with olive oil and seasonings",
                    "Roast vegetables for 20 minutes",
                    "Add salmon and cook for 12-15 minutes"
                ],
                nutritional_info={
                    "calories": 420,
                    "carbohydrates": 12,
                    "protein": 38,
                    "fat": 24,
                    "fiber": 6
                },
                diabetes_friendly_score=9.5,
                prep_time=15,
                cook_time=25,
                servings=1
            ),
            
            # Low-carb dinner recipes
            Recipe(
                name="Zucchini Noodles with Turkey Meatballs",
                description="Low-carb pasta alternative with lean protein",
                ingredients=[
                    "2 large zucchinis (spiralized)",
                    "1 lb ground turkey",
                    "1/2 cup marinara sauce (low-sugar)",
                    "1/4 cup parmesan cheese",
                    "1 egg",
                    "2 tbsp breadcrumbs (almond flour)",
                    "1 tsp Italian seasoning",
                    "Salt and pepper to taste"
                ],
                instructions=[
                    "Mix turkey with egg, breadcrumbs, and seasonings",
                    "Form into meatballs and bake at 375°F for 20 minutes",
                    "Sauté zucchini noodles for 3-4 minutes",
                    "Top with marinara sauce and meatballs",
                    "Sprinkle with parmesan cheese"
                ],
                nutritional_info={
                    "calories": 380,
                    "carbohydrates": 15,
                    "protein": 35,
                    "fat": 18,
                    "fiber": 4
                },
                diabetes_friendly_score=8.5,
                prep_time=20,
                cook_time=25,
                servings=2
            ),
            
            Recipe(
                name="Baked Cod with Asparagus",
                description="Light, protein-rich dinner",
                ingredients=[
                    "6 oz cod fillet",
                    "1 bunch asparagus",
                    "2 tbsp olive oil",
                    "1 tsp garlic powder",
                    "1 tsp lemon zest",
                    "1 tbsp fresh dill",
                    "Salt and pepper to taste"
                ],
                instructions=[
                    "Preheat oven to 425°F",
                    "Season cod with garlic powder, salt, and pepper",
                    "Toss asparagus with olive oil and seasonings",
                    "Bake cod for 12-15 minutes",
                    "Add asparagus and cook for 8-10 minutes",
                    "Garnish with lemon zest and dill"
                ],
                nutritional_info={
                    "calories": 280,
                    "carbohydrates": 8,
                    "protein": 32,
                    "fat": 12,
                    "fiber": 4
                },
                diabetes_friendly_score=9.5,
                prep_time=10,
                cook_time=20,
                servings=1
            ),
            
            # Snack recipes
            Recipe(
                name="Almond Butter Celery Sticks",
                description="Quick, protein-rich snack",
                ingredients=[
                    "4 celery stalks",
                    "2 tbsp almond butter",
                    "1 tsp chia seeds"
                ],
                instructions=[
                    "Cut celery into sticks",
                    "Spread almond butter on celery",
                    "Sprinkle with chia seeds"
                ],
                nutritional_info={
                    "calories": 180,
                    "carbohydrates": 8,
                    "protein": 8,
                    "fat": 14,
                    "fiber": 6
                },
                diabetes_friendly_score=9.0,
                prep_time=5,
                cook_time=0,
                servings=1
            ),
            
            Recipe(
                name="Cheese and Vegetable Plate",
                description="Low-carb, high-protein snack",
                ingredients=[
                    "2 oz cheddar cheese",
                    "1/2 cup cucumber slices",
                    "1/2 cup bell pepper strips",
                    "1/4 cup cherry tomatoes",
                    "2 tbsp hummus"
                ],
                instructions=[
                    "Arrange cheese and vegetables on a plate",
                    "Serve with hummus for dipping"
                ],
                nutritional_info={
                    "calories": 220,
                    "carbohydrates": 12,
                    "protein": 14,
                    "fat": 14,
                    "fiber": 4
                },
                diabetes_friendly_score=8.5,
                prep_time=5,
                cook_time=0,
                servings=1
            ),
            
            # High-fiber recipes for blood sugar control
            Recipe(
                name="Quinoa and Black Bean Bowl",
                description="High-fiber, plant-based protein meal",
                ingredients=[
                    "1/2 cup cooked quinoa",
                    "1/2 cup black beans",
                    "1/4 cup diced tomatoes",
                    "1/4 cup diced avocado",
                    "2 tbsp cilantro",
                    "1 tbsp lime juice",
                    "1 tsp cumin",
                    "Salt to taste"
                ],
                instructions=[
                    "Cook quinoa according to package directions",
                    "Mix quinoa with black beans",
                    "Add tomatoes, avocado, and cilantro",
                    "Season with lime juice, cumin, and salt"
                ],
                nutritional_info={
                    "calories": 320,
                    "carbohydrates": 45,
                    "protein": 14,
                    "fat": 8,
                    "fiber": 12
                },
                diabetes_friendly_score=8.0,
                prep_time=10,
                cook_time=15,
                servings=1
            ),
            
            Recipe(
                name="Lentil and Vegetable Soup",
                description="High-fiber, low-glycemic soup",
                ingredients=[
                    "1/2 cup red lentils",
                    "1 cup vegetable broth",
                    "1/2 cup diced carrots",
                    "1/2 cup diced celery",
                    "1/4 cup diced onions",
                    "1 tsp garlic",
                    "1 tsp turmeric",
                    "Salt and pepper to taste"
                ],
                instructions=[
                    "Sauté onions and garlic until soft",
                    "Add carrots and celery, cook for 5 minutes",
                    "Add lentils, broth, and seasonings",
                    "Simmer for 20-25 minutes until lentils are tender"
                ],
                nutritional_info={
                    "calories": 280,
                    "carbohydrates": 45,
                    "protein": 18,
                    "fat": 2,
                    "fiber": 15
                },
                diabetes_friendly_score=8.5,
                prep_time=10,
                cook_time=30,
                servings=2
            )
        ]
    
    def recommend_recipes(self, 
                         blood_sugar_patterns: List[BloodSugarPattern] = None,
                         meal_type: str = "any",
                         max_carbs: int = 30,
                         dietary_restrictions: List[str] = None) -> List[Recipe]:
        """Recommend recipes based on blood sugar patterns and preferences"""
        
        if dietary_restrictions is None:
            dietary_restrictions = []
        
        # Filter recipes based on criteria
        filtered_recipes = self._filter_recipes(
            meal_type, max_carbs, dietary_restrictions
        )
        
        # Score recipes based on blood sugar patterns
        if blood_sugar_patterns:
            scored_recipes = self._score_recipes_by_patterns(
                filtered_recipes, blood_sugar_patterns
            )
        else:
            scored_recipes = [(recipe, recipe.diabetes_friendly_score) for recipe in filtered_recipes]
        
        # Sort by score and return top recommendations
        scored_recipes.sort(key=lambda x: x[1], reverse=True)
        return [recipe for recipe, score in scored_recipes[:5]]
    
    def _filter_recipes(self, meal_type: str, max_carbs: int, 
                       dietary_restrictions: List[str]) -> List[Recipe]:
        """Filter recipes based on basic criteria"""
        filtered = []
        
        for recipe in self.recipe_database:
            # Check carb limit
            if recipe.nutritional_info.get('carbohydrates', 0) > max_carbs:
                continue
            
            # Check meal type
            if meal_type != "any":
                if meal_type == "breakfast" and "breakfast" not in recipe.name.lower():
                    continue
                elif meal_type == "lunch" and "lunch" not in recipe.name.lower():
                    continue
                elif meal_type == "dinner" and "dinner" not in recipe.name.lower():
                    continue
            
            # Check dietary restrictions
            if self._check_dietary_restrictions(recipe, dietary_restrictions):
                filtered.append(recipe)
        
        return filtered
    
    def _check_dietary_restrictions(self, recipe: Recipe, 
                                   dietary_restrictions: List[str]) -> bool:
        """Check if recipe meets dietary restrictions"""
        if not dietary_restrictions:
            return True
        
        recipe_text = " ".join(recipe.ingredients + recipe.instructions).lower()
        
        for restriction in dietary_restrictions:
            restriction = restriction.lower()
            if restriction == "vegetarian":
                if any(meat in recipe_text for meat in ["chicken", "beef", "pork", "turkey", "fish", "salmon", "cod"]):
                    return False
            elif restriction == "vegan":
                if any(animal in recipe_text for animal in ["cheese", "yogurt", "eggs", "milk", "butter"]):
                    return False
            elif restriction == "gluten-free":
                if any(gluten in recipe_text for gluten in ["bread", "pasta", "flour", "wheat"]):
                    return False
            elif restriction == "dairy-free":
                if any(dairy in recipe_text for dairy in ["cheese", "milk", "yogurt", "butter"]):
                    return False
            elif restriction == "nut-free":
                if any(nut in recipe_text for nut in ["almond", "walnut", "peanut", "cashew"]):
                    return False
        
        return True
    
    def _score_recipes_by_patterns(self, recipes: List[Recipe], 
                                  patterns: List[BloodSugarPattern]) -> List[tuple]:
        """Score recipes based on blood sugar patterns"""
        scored_recipes = []
        
        for recipe in recipes:
            base_score = recipe.diabetes_friendly_score
            pattern_bonus = 0
            
            # Adjust score based on patterns
            for pattern in patterns:
                if "Dawn Phenomenon" in pattern.pattern_type:
                    # Recommend low-carb breakfast options
                    if recipe.nutritional_info.get('carbohydrates', 0) < 20:
                        pattern_bonus += 1
                
                elif "Post-Meal Hyperglycemia" in pattern.pattern_type:
                    # Recommend high-fiber, low-glycemic options
                    if recipe.nutritional_info.get('fiber', 0) > 5:
                        pattern_bonus += 1
                    if recipe.nutritional_info.get('carbohydrates', 0) < 25:
                        pattern_bonus += 1
                
                elif "Nocturnal Hypoglycemia" in pattern.pattern_type:
                    # Recommend protein-rich evening snacks
                    if recipe.nutritional_info.get('protein', 0) > 15:
                        pattern_bonus += 1
                
                elif "High Blood Sugar Variability" in pattern.pattern_type:
                    # Recommend consistent, balanced meals
                    if (recipe.nutritional_info.get('protein', 0) > 10 and 
                        recipe.nutritional_info.get('fat', 0) > 5):
                        pattern_bonus += 1
            
            final_score = base_score + pattern_bonus
            scored_recipes.append((recipe, final_score))
        
        return scored_recipes
    
    def get_meal_plan_suggestions(self, days: int = 7) -> Dict[str, List[Recipe]]:
        """Generate a weekly meal plan"""
        meal_plan = {
            "breakfast": [],
            "lunch": [],
            "dinner": [],
            "snacks": []
        }
        
        # Get recommendations for each meal type
        for meal_type in meal_plan.keys():
            recommendations = self.recommend_recipes(
                meal_type=meal_type,
                max_carbs=30 if meal_type != "snacks" else 15
            )
            
            # Select recipes for the week
            for i in range(days):
                if recommendations:
                    recipe = random.choice(recommendations[:3])  # Choose from top 3
                    meal_plan[meal_type].append(recipe)
        
        return meal_plan
    
    def get_emergency_low_recipes(self) -> List[Recipe]:
        """Get recipes for treating hypoglycemia"""
        return [
            Recipe(
                name="Quick Glucose Recovery",
                description="Fast-acting carbs for hypoglycemia treatment",
                ingredients=[
                    "4 oz fruit juice",
                    "1 tbsp honey",
                    "2 glucose tablets (if available)"
                ],
                instructions=[
                    "Drink fruit juice immediately",
                    "Follow with honey if needed",
                    "Wait 15 minutes and recheck blood sugar"
                ],
                nutritional_info={
                    "calories": 120,
                    "carbohydrates": 30,
                    "protein": 0,
                    "fat": 0,
                    "fiber": 0
                },
                diabetes_friendly_score=10.0,
                prep_time=1,
                cook_time=0,
                servings=1
            ),
            
            Recipe(
                name="Stable Recovery Snack",
                description="Protein + carb combo to prevent rebound",
                ingredients=[
                    "1 slice whole grain bread",
                    "1 tbsp peanut butter",
                    "1 small apple"
                ],
                instructions=[
                    "Spread peanut butter on bread",
                    "Eat with apple slices",
                    "Monitor blood sugar for 1 hour"
                ],
                nutritional_info={
                    "calories": 280,
                    "carbohydrates": 35,
                    "protein": 12,
                    "fat": 12,
                    "fiber": 6
                },
                diabetes_friendly_score=9.0,
                prep_time=2,
                cook_time=0,
                servings=1
            )
        ]
    
    def analyze_recipe_impact(self, recipe: Recipe, 
                            current_blood_sugar: float) -> Dict[str, any]:
        """Analyze potential blood sugar impact of a recipe"""
        carbs = recipe.nutritional_info.get('carbohydrates', 0)
        fiber = recipe.nutritional_info.get('fiber', 0)
        protein = recipe.nutritional_info.get('protein', 0)
        fat = recipe.nutritional_info.get('fat', 0)
        
        # Calculate net carbs
        net_carbs = carbs - fiber
        
        # Estimate blood sugar impact
        estimated_rise = net_carbs * 3  # Rough estimate: 1g carb ≈ 3 mg/dL rise
        predicted_bs = current_blood_sugar + estimated_rise
        
        # Determine risk level
        if predicted_bs > 300:
            risk_level = "High - May cause dangerous hyperglycemia"
        elif predicted_bs > 180:
            risk_level = "Medium - Above target range"
        elif predicted_bs < 70:
            risk_level = "High - May cause hypoglycemia"
        else:
            risk_level = "Low - Within safe range"
        
        # Generate recommendations
        recommendations = []
        if net_carbs > 30:
            recommendations.append("Consider reducing portion size")
        if fiber < 5:
            recommendations.append("Add more fiber-rich foods")
        if protein < 15:
            recommendations.append("Add protein to slow glucose absorption")
        
        return {
            "estimated_blood_sugar_rise": estimated_rise,
            "predicted_blood_sugar": predicted_bs,
            "risk_level": risk_level,
            "recommendations": recommendations,
            "insulin_suggestion": f"Consider {net_carbs * 0.1:.1f} units of rapid-acting insulin"
        }

