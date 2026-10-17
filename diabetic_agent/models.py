"""
Data models for the diabetic agent
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class BloodSugarLevel(BaseModel):
    """Blood sugar measurement"""
    timestamp: datetime
    value: float = Field(..., description="Blood sugar level in mg/dL")
    measurement_type: str = Field(..., description="Fasting, post-meal, random, etc.")
    notes: Optional[str] = None


class FoodItem(BaseModel):
    """Individual food item with nutritional information"""
    name: str
    quantity: float
    unit: str  # grams, cups, pieces, etc.
    calories: float
    carbohydrates: float
    protein: float
    fat: float
    fiber: Optional[float] = None
    sugar: Optional[float] = None


class MealLog(BaseModel):
    """Complete meal with timestamp and food items"""
    timestamp: datetime
    meal_type: str = Field(..., description="Breakfast, lunch, dinner, snack")
    food_items: List[FoodItem]
    total_calories: float
    total_carbs: float
    total_protein: float
    total_fat: float
    notes: Optional[str] = None


class InsulinDose(BaseModel):
    """Insulin injection record"""
    timestamp: datetime
    insulin_type: str = Field(..., description="Rapid-acting, long-acting, etc.")
    units: float
    injection_site: str = Field(..., description="Arm, thigh, abdomen, etc.")
    notes: Optional[str] = None


class HealthStats(BaseModel):
    """Daily health statistics"""
    date: date
    steps: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    workout_duration: Optional[int] = None  # minutes
    workout_type: Optional[str] = None
    sleep_hours: Optional[float] = None
    stress_level: Optional[int] = Field(None, ge=1, le=10, description="Stress level 1-10")
    notes: Optional[str] = None


class BloodSugarPattern(BaseModel):
    """Analyzed blood sugar pattern"""
    pattern_type: str = Field(..., description="High morning, post-meal spike, etc.")
    frequency: str = Field(..., description="Daily, weekly, occasional")
    severity: str = Field(..., description="Mild, moderate, severe")
    potential_causes: List[str]
    recommendations: List[str]


class Recipe(BaseModel):
    """Recipe recommendation"""
    name: str
    description: str
    ingredients: List[str]
    instructions: List[str]
    nutritional_info: Dict[str, float]
    diabetes_friendly_score: float = Field(..., ge=0, le=10)
    prep_time: int  # minutes
    cook_time: int  # minutes
    servings: int


class UserProfile(BaseModel):
    """User profile and preferences"""
    name: str
    age: int
    diabetes_type: str = Field(..., description="Type 1, Type 2, Gestational, etc.")
    diagnosis_date: date
    current_medications: List[str]
    target_blood_sugar_range: Dict[str, float] = Field(
        ..., description="Fasting and post-meal targets"
    )
    dietary_restrictions: List[str] = []
    allergies: List[str] = []
    preferences: Dict[str, Any] = {}


class AnalysisResult(BaseModel):
    """Result of blood sugar analysis"""
    date_range: Dict[str, datetime]
    average_blood_sugar: float
    time_in_range: float = Field(..., description="Percentage of time in target range")
    patterns: List[BloodSugarPattern]
    recommendations: List[str]
    risk_factors: List[str]
    positive_trends: List[str]


class ChatMessage(BaseModel):
    """Chat message for user interaction"""
    timestamp: datetime
    user_message: str
    agent_response: str
    message_type: str = Field(..., description="question, recommendation, analysis")

