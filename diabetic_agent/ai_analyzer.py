"""
AI analysis engine for blood sugar pattern recognition and recommendations
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
import warnings
warnings.filterwarnings('ignore')

from .models import (
    BloodSugarLevel, MealLog, InsulinDose, HealthStats, 
    BloodSugarPattern, AnalysisResult, UserProfile
)


class BloodSugarAnalyzer:
    """AI-powered blood sugar pattern analysis"""
    
    def __init__(self, user_profile: Optional[UserProfile] = None):
        self.user_profile = user_profile
        self.target_range = (70, 180)  # Default range, can be customized
        
        if user_profile and 'target_blood_sugar_range' in user_profile.preferences:
            targets = user_profile.preferences['target_blood_sugar_range']
            self.target_range = (targets.get('fasting', 70), targets.get('post_meal', 180))
    
    def analyze_patterns(self, blood_sugar_data: List[BloodSugarLevel], 
                        meal_logs: List[MealLog] = None,
                        insulin_doses: List[InsulinDose] = None,
                        health_stats: List[HealthStats] = None) -> AnalysisResult:
        """Comprehensive analysis of blood sugar patterns"""
        
        if not blood_sugar_data:
            return AnalysisResult(
                date_range={"start": datetime.now(), "end": datetime.now()},
                average_blood_sugar=0,
                time_in_range=0,
                patterns=[],
                recommendations=[],
                risk_factors=[],
                positive_trends=[]
            )
        
        # Convert to DataFrame for analysis
        df = self._prepare_dataframe(blood_sugar_data, meal_logs, insulin_doses, health_stats)
        
        # Calculate basic statistics
        avg_bs = df['value'].mean()
        time_in_range = self._calculate_time_in_range(df['value'])
        
        # Identify patterns
        patterns = self._identify_patterns(df)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(df, patterns)
        
        # Identify risk factors
        risk_factors = self._identify_risk_factors(df)
        
        # Identify positive trends
        positive_trends = self._identify_positive_trends(df)
        
        return AnalysisResult(
            date_range={
                "start": df['timestamp'].min(),
                "end": df['timestamp'].max()
            },
            average_blood_sugar=avg_bs,
            time_in_range=time_in_range,
            patterns=patterns,
            recommendations=recommendations,
            risk_factors=risk_factors,
            positive_trends=positive_trends
        )
    
    def _prepare_dataframe(self, blood_sugar_data: List[BloodSugarLevel],
                          meal_logs: List[MealLog] = None,
                          insulin_doses: List[InsulinDose] = None,
                          health_stats: List[HealthStats] = None) -> pd.DataFrame:
        """Prepare comprehensive DataFrame for analysis"""
        
        # Create base DataFrame
        df = pd.DataFrame([{
            'timestamp': bs.timestamp,
            'value': bs.value,
            'measurement_type': bs.measurement_type,
            'hour': bs.timestamp.hour,
            'day_of_week': bs.timestamp.weekday(),
            'date': bs.timestamp.date()
        } for bs in blood_sugar_data])
        
        # Add meal information
        if meal_logs:
            df = self._add_meal_context(df, meal_logs)
        
        # Add insulin information
        if insulin_doses:
            df = self._add_insulin_context(df, insulin_doses)
        
        # Add health stats
        if health_stats:
            df = self._add_health_context(df, health_stats)
        
        # Add derived features
        df = self._add_derived_features(df)
        
        return df
    
    def _add_meal_context(self, df: pd.DataFrame, meal_logs: List[MealLog]) -> pd.DataFrame:
        """Add meal context to blood sugar data"""
        df['meal_carbs_2h_before'] = 0
        df['meal_carbs_4h_before'] = 0
        df['meal_type'] = 'none'
        
        for _, row in df.iterrows():
            timestamp = row['timestamp']
            
            # Find meals within 2 hours before
            meals_2h = [meal for meal in meal_logs 
                       if timestamp - timedelta(hours=2) <= meal.timestamp <= timestamp]
            
            # Find meals within 4 hours before
            meals_4h = [meal for meal in meal_logs 
                       if timestamp - timedelta(hours=4) <= meal.timestamp <= timestamp]
            
            if meals_2h:
                df.loc[df['timestamp'] == timestamp, 'meal_carbs_2h_before'] = sum(meal.total_carbs for meal in meals_2h)
                df.loc[df['timestamp'] == timestamp, 'meal_type'] = meals_2h[-1].meal_type
            
            if meals_4h:
                df.loc[df['timestamp'] == timestamp, 'meal_carbs_4h_before'] = sum(meal.total_carbs for meal in meals_4h)
        
        return df
    
    def _add_insulin_context(self, df: pd.DataFrame, insulin_doses: List[InsulinDose]) -> pd.DataFrame:
        """Add insulin context to blood sugar data"""
        df['insulin_units_2h_before'] = 0
        df['insulin_units_4h_before'] = 0
        
        for _, row in df.iterrows():
            timestamp = row['timestamp']
            
            # Find insulin doses within 2 hours before
            insulin_2h = [dose for dose in insulin_doses 
                         if timestamp - timedelta(hours=2) <= dose.timestamp <= timestamp]
            
            # Find insulin doses within 4 hours before
            insulin_4h = [dose for dose in insulin_doses 
                         if timestamp - timedelta(hours=4) <= dose.timestamp <= timestamp]
            
            if insulin_2h:
                df.loc[df['timestamp'] == timestamp, 'insulin_units_2h_before'] = sum(dose.units for dose in insulin_2h)
            
            if insulin_4h:
                df.loc[df['timestamp'] == timestamp, 'insulin_units_4h_before'] = sum(dose.units for dose in insulin_4h)
        
        return df
    
    def _add_health_context(self, df: pd.DataFrame, health_stats: List[HealthStats]) -> pd.DataFrame:
        """Add health stats context to blood sugar data"""
        df['steps_today'] = 0
        df['workout_today'] = False
        df['sleep_hours'] = 8  # Default
        
        for _, row in df.iterrows():
            date = row['date']
            
            # Find health stats for the same date
            day_stats = [stat for stat in health_stats if stat.date == date]
            
            if day_stats:
                stat = day_stats[0]
                df.loc[df['date'] == date, 'steps_today'] = stat.steps or 0
                df.loc[df['date'] == date, 'workout_today'] = stat.workout_duration is not None
                df.loc[df['date'] == date, 'sleep_hours'] = stat.sleep_hours or 8
        
        return df
    
    def _add_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add derived features for analysis"""
        # Time-based features
        df['is_morning'] = df['hour'].between(6, 10)
        df['is_afternoon'] = df['hour'].between(12, 16)
        df['is_evening'] = df['hour'].between(18, 22)
        df['is_night'] = (df['hour'] >= 22) | (df['hour'] <= 6)
        
        # Blood sugar categories
        df['bs_category'] = pd.cut(df['value'], 
                                 bins=[0, 70, 180, 300, float('inf')],
                                 labels=['low', 'normal', 'high', 'very_high'])
        
        # Rolling averages
        df['bs_3h_avg'] = df['value'].rolling(window=3, min_periods=1).mean()
        df['bs_6h_avg'] = df['value'].rolling(window=6, min_periods=1).mean()
        
        # Variability
        df['bs_std_3h'] = df['value'].rolling(window=3, min_periods=1).std()
        
        return df
    
    def _calculate_time_in_range(self, values: pd.Series) -> float:
        """Calculate percentage of time in target range"""
        in_range = ((values >= self.target_range[0]) & (values <= self.target_range[1])).sum()
        return (in_range / len(values)) * 100
    
    def _identify_patterns(self, df: pd.DataFrame) -> List[BloodSugarPattern]:
        """Identify blood sugar patterns using ML techniques"""
        patterns = []
        
        # Dawn phenomenon (high morning readings)
        morning_bs = df[df['is_morning']]['value']
        if not morning_bs.empty and morning_bs.mean() > self.target_range[1]:
            patterns.append(BloodSugarPattern(
                pattern_type="Dawn Phenomenon",
                frequency="Daily",
                severity="Moderate" if morning_bs.mean() < 200 else "Severe",
                potential_causes=[
                    "Natural hormone release in early morning",
                    "Insufficient overnight insulin",
                    "High-carb dinner the night before"
                ],
                recommendations=[
                    "Consider adjusting overnight insulin timing",
                    "Eat a low-carb dinner",
                    "Monitor blood sugar more frequently in the morning"
                ]
            ))
        
        # Post-meal spikes
        post_meal_bs = df[df['is_afternoon']]['value']
        if not post_meal_bs.empty and post_meal_bs.mean() > self.target_range[1]:
            patterns.append(BloodSugarPattern(
                pattern_type="Post-Meal Hyperglycemia",
                frequency="Daily",
                severity="Moderate" if post_meal_bs.mean() < 250 else "Severe",
                potential_causes=[
                    "Insufficient pre-meal insulin",
                    "High-carb meals",
                    "Delayed insulin administration"
                ],
                recommendations=[
                    "Take insulin 15-20 minutes before meals",
                    "Choose lower-carb meal options",
                    "Consider insulin-to-carb ratio adjustments"
                ]
            ))
        
        # Nighttime hypoglycemia
        night_bs = df[df['is_night']]['value']
        if not night_bs.empty and night_bs.mean() < self.target_range[0]:
            patterns.append(BloodSugarPattern(
                pattern_type="Nocturnal Hypoglycemia",
                frequency="Occasional",
                severity="Moderate" if night_bs.mean() > 50 else "Severe",
                potential_causes=[
                    "Too much insulin at dinner",
                    "Insufficient bedtime snack",
                    "Exercise without carb adjustment"
                ],
                recommendations=[
                    "Reduce dinner insulin dose",
                    "Eat a protein-rich bedtime snack",
                    "Monitor blood sugar before bed"
                ]
            ))
        
        # High variability
        bs_std = df['value'].std()
        if bs_std > 50:
            patterns.append(BloodSugarPattern(
                pattern_type="High Blood Sugar Variability",
                frequency="Daily",
                severity="Moderate" if bs_std < 80 else "Severe",
                potential_causes=[
                    "Inconsistent meal timing",
                    "Variable insulin absorption",
                    "Stress and illness"
                ],
                recommendations=[
                    "Maintain consistent meal timing",
                    "Rotate injection sites regularly",
                    "Consider continuous glucose monitoring"
                ]
            ))
        
        # Exercise-related patterns
        if 'workout_today' in df.columns:
            workout_bs = df[df['workout_today']]['value']
            if not workout_bs.empty:
                if workout_bs.mean() < self.target_range[0]:
                    patterns.append(BloodSugarPattern(
                        pattern_type="Exercise-Induced Hypoglycemia",
                        frequency="Occasional",
                        severity="Moderate",
                        potential_causes=[
                            "Insufficient carb intake before exercise",
                            "Too much insulin before exercise",
                            "Long-duration exercise without fuel"
                        ],
                        recommendations=[
                            "Eat carbs before exercise",
                            "Reduce insulin before exercise",
                            "Monitor blood sugar during exercise"
                        ]
                    ))
        
        return patterns
    
    def _generate_recommendations(self, df: pd.DataFrame, patterns: List[BloodSugarPattern]) -> List[str]:
        """Generate personalized recommendations"""
        recommendations = []
        
        # Time in range recommendations
        time_in_range = self._calculate_time_in_range(df['value'])
        if time_in_range < 70:
            recommendations.append("Focus on improving time in range - aim for 70% or higher")
        
        # Meal timing recommendations
        if 'meal_carbs_2h_before' in df.columns:
            high_carb_meals = df[df['meal_carbs_2h_before'] > 50]
            if not high_carb_meals.empty:
                recommendations.append("Consider reducing carb portions or timing insulin better for high-carb meals")
        
        # Exercise recommendations
        if 'workout_today' in df.columns:
            workout_days = df[df['workout_today']]
            if not workout_days.empty and workout_days['value'].mean() < self.target_range[0]:
                recommendations.append("Consider eating a carb snack before exercise to prevent lows")
        
        # Sleep recommendations
        if 'sleep_hours' in df.columns:
            avg_sleep = df['sleep_hours'].mean()
            if avg_sleep < 7:
                recommendations.append("Improve sleep quality - aim for 7-9 hours per night")
        
        # Stress management
        if 'stress_level' in df.columns:
            high_stress = df[df['stress_level'] > 7]
            if not high_stress.empty:
                recommendations.append("Practice stress management techniques - stress affects blood sugar")
        
        return recommendations
    
    def _identify_risk_factors(self, df: pd.DataFrame) -> List[str]:
        """Identify risk factors for complications"""
        risk_factors = []
        
        # Very high blood sugar
        very_high = df[df['value'] > 300]
        if not very_high.empty:
            risk_factors.append("Frequent very high blood sugar readings (>300 mg/dL)")
        
        # Frequent lows
        lows = df[df['value'] < 70]
        if len(lows) > len(df) * 0.1:  # More than 10% of readings
            risk_factors.append("Frequent hypoglycemia episodes")
        
        # High variability
        if df['value'].std() > 60:
            risk_factors.append("High blood sugar variability increases complication risk")
        
        # Poor time in range
        time_in_range = self._calculate_time_in_range(df['value'])
        if time_in_range < 50:
            risk_factors.append("Low time in range increases long-term complication risk")
        
        return risk_factors
    
    def _identify_positive_trends(self, df: pd.DataFrame) -> List[str]:
        """Identify positive trends and improvements"""
        positive_trends = []
        
        # Improving time in range
        if len(df) > 7:  # At least a week of data
            recent_data = df.tail(7)
            older_data = df.head(7)
            
            recent_tir = self._calculate_time_in_range(recent_data['value'])
            older_tir = self._calculate_time_in_range(older_data['value'])
            
            if recent_tir > older_tir + 10:
                positive_trends.append("Improving time in range over the past week")
        
        # Consistent meal timing
        if 'meal_type' in df.columns:
            meal_consistency = df['meal_type'].value_counts()
            if len(meal_consistency) >= 3:  # Breakfast, lunch, dinner
                positive_trends.append("Consistent meal timing throughout the day")
        
        # Good exercise habits
        if 'workout_today' in df.columns:
            workout_frequency = df['workout_today'].sum() / len(df)
            if workout_frequency > 0.3:  # More than 30% of days
                positive_trends.append("Regular exercise routine")
        
        # Stable sleep patterns
        if 'sleep_hours' in df.columns:
            sleep_std = df['sleep_hours'].std()
            if sleep_std < 1.5:  # Consistent sleep schedule
                positive_trends.append("Consistent sleep schedule")
        
        return positive_trends
    
    def predict_blood_sugar_trend(self, df: pd.DataFrame, hours_ahead: int = 2) -> Dict[str, any]:
        """Predict blood sugar trend for the next few hours"""
        if len(df) < 3:
            return {"prediction": "Insufficient data for prediction"}
        
        # Simple trend analysis
        recent_values = df['value'].tail(3).values
        trend = np.polyfit(range(len(recent_values)), recent_values, 1)[0]
        
        # Predict based on trend
        current_value = df['value'].iloc[-1]
        predicted_value = current_value + (trend * hours_ahead)
        
        # Determine risk level
        if predicted_value < 70:
            risk_level = "High - Risk of hypoglycemia"
        elif predicted_value > 300:
            risk_level = "High - Risk of hyperglycemia"
        elif predicted_value > 180:
            risk_level = "Medium - Above target range"
        else:
            risk_level = "Low - Within target range"
        
        return {
            "predicted_value": round(predicted_value, 1),
            "trend_direction": "increasing" if trend > 0 else "decreasing",
            "risk_level": risk_level,
            "confidence": "Low" if len(df) < 10 else "Medium"
        }

