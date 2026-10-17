"""
LLM-powered diabetes management agent
Uses all user data as context for intelligent recommendations
"""

import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
import re

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from .models import BloodSugarLevel, MealLog, UserProfile
from .database import DatabaseManager


class LLMDiabeticAgent:
    """LLM-powered agent that uses all user data as context"""
    
    def __init__(self, user_id: int, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.user_id = user_id
        self.db = DatabaseManager()
        self.model = model
        
        if OPENAI_AVAILABLE:
            self.client = OpenAI(api_key=api_key) if api_key else None
        else:
            self.client = None
        
        # Get user profile for context
        self.user_profile = self.db.get_user_profile(user_id)
    
    def chat(self, message: str, conversation_history: List[Dict[str, str]] = None) -> str:
        """
        Chat with the LLM agent using all user data as context
        
        Args:
            message: User's message
            conversation_history: Previous conversation messages
        
        Returns:
            LLM response
        """
        if not self.client:
            return self._fallback_response(message)
        
        # Parse time window from message if mentioned
        time_window = self._parse_time_window(message)
        
        # Build comprehensive context
        context = self._build_context(time_window)
        
        # Build system prompt
        system_prompt = self._build_system_prompt(context)
        
        # Build conversation messages
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history[-10:])  # Last 10 messages for context
        
        # Add current user message
        messages.append({"role": "user", "content": message})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"I encountered an error: {str(e)}. Please check your API key and try again."
    
    def _parse_time_window(self, message: str) -> Optional[Tuple[datetime, datetime]]:
        """
        Parse time window from natural language
        
        Examples:
        - "last week" -> last 7 days
        - "yesterday" -> yesterday
        - "this month" -> this month
        - "October data" -> October 1-31
        - "last 3 days" -> last 3 days
        - "from January 1 to January 15" -> specific range
        """
        message_lower = message.lower()
        today = date.today()
        current_year = today.year
        
        # Month names mapping
        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        
        # Check for specific month (e.g., "October data", "October", "data from October")
        for month_name, month_num in months.items():
            if month_name in message_lower:
                # Check if year is explicitly mentioned
                year_match = re.search(r'(\d{4})', message_lower)
                if year_match:
                    # Year is explicitly mentioned, use it
                    year = int(year_match.group(1))
                else:
                    # No year mentioned - use the most recent occurrence of this month
                    # If the month hasn't happened yet this year, use last year
                    # If the month has already passed this year, use this year
                    if month_num > today.month:
                        # Month hasn't happened yet this year, use last year
                        year = current_year - 1
                    else:
                        # Month has already passed or is current month, use this year
                        year = current_year
                
                # Get first and last day of the month
                if month_num == 12:
                    last_day = 31
                elif month_num in [4, 6, 9, 11]:
                    last_day = 30
                elif month_num == 2:
                    # Check for leap year
                    last_day = 29 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 28
                else:
                    last_day = 31
                
                start_date = date(year, month_num, 1)
                end_date = date(year, month_num, last_day)
                
                return (datetime.combine(start_date, datetime.min.time()),
                       datetime.combine(end_date, datetime.max.time()))
        
        # Last N days
        days_match = re.search(r'last\s+(\d+)\s+days?', message_lower)
        if days_match:
            days = int(days_match.group(1))
            start_date = today - timedelta(days=days)
            end_date = today
            return (datetime.combine(start_date, datetime.min.time()),
                   datetime.combine(end_date, datetime.max.time()))
        
        # Last week
        if 'last week' in message_lower:
            start_date = today - timedelta(days=7)
            end_date = today
            return (datetime.combine(start_date, datetime.min.time()),
                   datetime.combine(end_date, datetime.max.time()))
        
        # Last month (previous calendar month)
        if 'last month' in message_lower:
            if today.month == 1:
                start_date = date(today.year - 1, 12, 1)
                end_date = date(today.year - 1, 12, 31)
            else:
                start_date = date(today.year, today.month - 1, 1)
                # Get last day of previous month
                if today.month - 1 in [4, 6, 9, 11]:
                    last_day = 30
                elif today.month - 1 == 2:
                    year = today.year
                    last_day = 29 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 28
                else:
                    last_day = 31
                end_date = date(today.year, today.month - 1, last_day)
            return (datetime.combine(start_date, datetime.min.time()),
                   datetime.combine(end_date, datetime.max.time()))
        
        # Yesterday
        if 'yesterday' in message_lower:
            yesterday = today - timedelta(days=1)
            return (datetime.combine(yesterday, datetime.min.time()),
                   datetime.combine(yesterday, datetime.max.time()))
        
        # This week
        if 'this week' in message_lower:
            start_date = today - timedelta(days=today.weekday())
            end_date = today
            return (datetime.combine(start_date, datetime.min.time()),
                   datetime.combine(end_date, datetime.max.time()))
        
        # This month
        if 'this month' in message_lower:
            start_date = today.replace(day=1)
            end_date = today
            return (datetime.combine(start_date, datetime.min.time()),
                   datetime.combine(end_date, datetime.max.time()))
        
        # Specific date range (e.g., "from October 1 to October 15")
        date_range_match = re.search(r'from\s+(\w+)\s+(\d+)\s+to\s+(\w+)\s+(\d+)', message_lower)
        if date_range_match:
            start_month_name, start_day, end_month_name, end_day = date_range_match.groups()
            start_month = months.get(start_month_name.lower())
            end_month = months.get(end_month_name.lower())
            
            if start_month and end_month:
                year_match = re.search(r'(\d{4})', message_lower)
                year = int(year_match.group(1)) if year_match else current_year
                
                try:
                    start_date = date(year, start_month, int(start_day))
                    end_date = date(year, end_month, int(end_day))
                    return (datetime.combine(start_date, datetime.min.time()),
                           datetime.combine(end_date, datetime.max.time()))
                except ValueError:
                    pass
        
        return None
    
    def _build_context(self, time_window: Optional[Tuple[datetime, datetime]] = None) -> Dict[str, Any]:
        """Build comprehensive context from all user data"""
        
        # Get data based on time window
        if time_window:
            start_date, end_date = time_window
            blood_sugar_data = self.db.get_blood_sugar_levels(
                self.user_id, days=30, start_date=start_date, end_date=end_date
            )
            meal_logs = self.db.get_meal_logs(
                self.user_id, days=30, start_date=start_date, end_date=end_date
            )
        else:
            # Default: last 30 days
            blood_sugar_data = self.db.get_blood_sugar_levels(self.user_id, days=30)
            meal_logs = self.db.get_meal_logs(self.user_id, days=30)
        
        # Build meal-to-blood-sugar correlations
        meal_bs_correlations = self._build_meal_blood_sugar_correlations(meal_logs, blood_sugar_data)
        
        # Calculate statistics
        context = {
            "user_profile": self._format_user_profile(),
            "blood_sugar": self._format_blood_sugar_data(blood_sugar_data),
            "meals": self._format_meal_data(meal_logs),
            "meal_bs_correlations": meal_bs_correlations,
            "patterns": self._identify_patterns(blood_sugar_data, meal_logs),
            "time_window": self._format_time_window(time_window)
        }
        
        return context
    
    def _format_user_profile(self) -> str:
        """Format user profile for context"""
        if not self.user_profile:
            return "No user profile available."
        
        profile_text = f"""
User Profile:
- Name: {self.user_profile.name}
- Age: {self.user_profile.age}
- Diabetes Type: {self.user_profile.diabetes_type}
- Diagnosis Date: {self.user_profile.diagnosis_date}
- Medications: {', '.join(self.user_profile.current_medications) if self.user_profile.current_medications else 'None'}
- Dietary Restrictions: {', '.join(self.user_profile.dietary_restrictions) if self.user_profile.dietary_restrictions else 'None'}
- Allergies: {', '.join(self.user_profile.allergies) if self.user_profile.allergies else 'None'}
- Target Blood Sugar Range: {self.user_profile.target_blood_sugar_range.get('fasting', 70)}-{self.user_profile.target_blood_sugar_range.get('post_meal', 180)} mg/dL
"""
        return profile_text
    
    def _format_blood_sugar_data(self, data: List[BloodSugarLevel]) -> str:
        """Format blood sugar data for context"""
        if not data:
            return "No blood sugar data available."
        
        values = [bs.value for bs in data]
        avg = sum(values) / len(values)
        min_val = min(values)
        max_val = max(values)
        
        # Time in range
        target_min = self.user_profile.target_blood_sugar_range.get('fasting', 70) if self.user_profile else 70
        target_max = self.user_profile.target_blood_sugar_range.get('post_meal', 180) if self.user_profile else 180
        in_range = sum(1 for v in values if target_min <= v <= target_max)
        tir = (in_range / len(values)) * 100
        
        # All readings sorted by date/time (for correlation analysis)
        sorted_data = sorted(data, key=lambda x: x.timestamp)
        all_readings_text = "\n".join([
            f"  - {bs.timestamp.strftime('%Y-%m-%d %H:%M')}: {bs.value} mg/dL ({bs.measurement_type})"
            for bs in sorted_data
        ])
        
        return f"""
Blood Sugar Summary:
- Total Readings: {len(data)}
- Average: {avg:.1f} mg/dL
- Range: {min_val:.0f} - {max_val:.0f} mg/dL
- Time in Range ({target_min}-{target_max} mg/dL): {tir:.1f}%

All Blood Sugar Readings (chronological):
{all_readings_text}
"""
    
    def _format_meal_data(self, meals: List[MealLog]) -> str:
        """Format meal data for context"""
        if not meals:
            return "No meal data available."
        
        # Daily nutrition summary
        daily_nutrition = {}
        for meal in meals:
            meal_date = meal.timestamp.date()
            if meal_date not in daily_nutrition:
                daily_nutrition[meal_date] = {
                    'calories': 0,
                    'carbs': 0,
                    'protein': 0,
                    'fat': 0,
                    'meals': []
                }
            daily_nutrition[meal_date]['calories'] += meal.total_calories
            daily_nutrition[meal_date]['carbs'] += meal.total_carbs
            daily_nutrition[meal_date]['protein'] += meal.total_protein
            daily_nutrition[meal_date]['fat'] += meal.total_fat
            daily_nutrition[meal_date]['meals'].append(meal)
        
        # Format summary
        days = len(daily_nutrition)
        total_calories = sum(d['calories'] for d in daily_nutrition.values())
        total_carbs = sum(d['carbs'] for d in daily_nutrition.values())
        total_protein = sum(d['protein'] for d in daily_nutrition.values())
        total_fat = sum(d['fat'] for d in daily_nutrition.values())
        
        avg_calories = total_calories / days if days > 0 else 0
        avg_carbs = total_carbs / days if days > 0 else 0
        avg_protein = total_protein / days if days > 0 else 0
        avg_fat = total_fat / days if days > 0 else 0
        
        # All meals sorted chronologically (for correlation analysis)
        sorted_meals = sorted(meals, key=lambda x: x.timestamp)
        all_meals_text = "\n".join([
            f"  - {meal.timestamp.strftime('%Y-%m-%d %H:%M')}: {meal.meal_type} - {meal.total_calories:.0f} cal, {meal.total_carbs:.1f}g carbs, {meal.total_protein:.1f}g protein, {meal.total_fat:.1f}g fat"
            for meal in sorted_meals
        ])
        
        return f"""
Meal & Nutrition Summary:
- Total Meals: {len(meals)}
- Days with meals: {days}
- Average Daily Calories: {avg_calories:.0f}
- Average Daily Carbs: {avg_carbs:.1f}g
- Average Daily Protein: {avg_protein:.1f}g
- Average Daily Fat: {avg_fat:.1f}g

All Meals (chronological):
{all_meals_text}
"""
    
    def _build_meal_blood_sugar_correlations(self, meal_logs: List[MealLog], 
                                            blood_sugar_data: List[BloodSugarLevel]) -> str:
        """Build correlations between meals and blood sugar readings"""
        if not meal_logs or not blood_sugar_data:
            return "No meal-blood sugar correlation data available (missing meals or blood sugar readings)."
        
        correlations = []
        
        # Sort both by timestamp
        sorted_meals = sorted(meal_logs, key=lambda x: x.timestamp)
        sorted_bs = sorted(blood_sugar_data, key=lambda x: x.timestamp)
        
        # For each meal, find blood sugar readings before and after
        for meal in sorted_meals:
            meal_time = meal.timestamp
            
            # Find readings within 2 hours before meal
            pre_meal_readings = [
                bs for bs in sorted_bs
                if meal_time - timedelta(hours=2) <= bs.timestamp < meal_time
            ]
            
            # Find readings within 2-4 hours after meal (post-meal spike window)
            post_meal_readings = [
                bs for bs in sorted_bs
                if meal_time < bs.timestamp <= meal_time + timedelta(hours=4)
            ]
            
            if pre_meal_readings or post_meal_readings:
                pre_avg = sum(bs.value for bs in pre_meal_readings) / len(pre_meal_readings) if pre_meal_readings else None
                post_avg = sum(bs.value for bs in post_meal_readings) / len(post_meal_readings) if post_meal_readings else None
                post_max = max(bs.value for bs in post_meal_readings) if post_meal_readings else None
                
                correlation_text = f"Meal: {meal.timestamp.strftime('%Y-%m-%d %H:%M')} - {meal.meal_type} ({meal.total_calories:.0f} cal, {meal.total_carbs:.1f}g carbs)"
                if pre_meal_readings:
                    correlation_text += f"\n  Pre-meal BS: {pre_avg:.1f} mg/dL (from {len(pre_meal_readings)} reading(s))"
                if post_meal_readings:
                    correlation_text += f"\n  Post-meal BS: {post_avg:.1f} mg/dL avg, {post_max:.1f} mg/dL max (from {len(post_meal_readings)} reading(s))"
                    if pre_avg:
                        change = post_avg - pre_avg
                        correlation_text += f"\n  Change: {change:+.1f} mg/dL"
                
                correlations.append(correlation_text)
        
        if not correlations:
            return "No meal-blood sugar correlations found (no overlapping time periods)."
        
        return "Meal-to-Blood Sugar Correlations:\n" + "\n\n".join(correlations)
    
    def _identify_patterns(self, blood_sugar_data: List[BloodSugarLevel], 
                          meal_logs: List[MealLog]) -> str:
        """Identify key patterns for context"""
        if not blood_sugar_data:
            return "No patterns identified (insufficient data)."
        
        patterns = []
        values = [bs.value for bs in blood_sugar_data]
        
        # High average
        avg = sum(values) / len(values)
        if avg > 180:
            patterns.append(f"High average blood sugar ({avg:.1f} mg/dL)")
        elif avg < 70:
            patterns.append(f"Low average blood sugar ({avg:.1f} mg/dL)")
        
        # High variability
        if len(values) > 1:
            std_dev = (sum((v - avg) ** 2 for v in values) / len(values)) ** 0.5
            if std_dev > 50:
                patterns.append(f"High variability (std dev: {std_dev:.1f})")
        
        # Time-based patterns
        morning_readings = [bs.value for bs in blood_sugar_data if 6 <= bs.timestamp.hour <= 10]
        if morning_readings:
            morning_avg = sum(morning_readings) / len(morning_readings)
            if morning_avg > 180:
                patterns.append("High morning readings (dawn phenomenon possible)")
        
        # Meal correlation (simplified)
        if meal_logs and blood_sugar_data:
            # Check if high-carb meals correlate with high blood sugar
            high_carb_meals = [m for m in meal_logs if m.total_carbs > 50]
            if high_carb_meals:
                patterns.append(f"{len(high_carb_meals)} high-carb meals (>50g) logged")
        
        if not patterns:
            return "No significant patterns identified. Blood sugar appears stable."
        
        return "Key Patterns:\n" + "\n".join(f"- {p}" for p in patterns)
    
    def _format_time_window(self, time_window: Optional[Tuple[datetime, datetime]]) -> str:
        """Format time window for context"""
        if not time_window:
            return "Analyzing last 30 days of data (default time window)."
        start_date, end_date = time_window
        days = (end_date.date() - start_date.date()).days + 1
        return f"IMPORTANT: User requested data from {start_date.date().strftime('%B %d, %Y')} to {end_date.date().strftime('%B %d, %Y')} ({days} days). All analysis should focus on this specific time period."
    
    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """Build comprehensive system prompt with all context"""
        prompt = f"""You are an expert diabetes management assistant. You have access to comprehensive data about the user's diabetes management.

{context['user_profile']}

{context['time_window']}

{context['blood_sugar']}

{context['meals']}

{context['meal_bs_correlations']}

{context['patterns']}

Your role:
1. Provide personalized, evidence-based recommendations based on the user's actual data
2. **CRITICAL**: Use the meal-to-blood sugar correlations provided above to answer questions about specific meals. When asked about a specific meal (e.g., "Did breakfast on 2025-10-25 lead to high blood sugar?"), look at the correlation data to find:
   - Pre-meal blood sugar readings (within 2 hours before the meal)
   - Post-meal blood sugar readings (2-4 hours after the meal)
   - Calculate the change and determine if there was a spike
3. Help identify patterns and correlations between meals and blood sugar
4. Suggest actionable improvements to diabetes management
5. Answer questions about their data in natural, conversational language
6. **CRITICAL**: Pay close attention to the time window specified above. If a specific time period is mentioned (e.g., "October", "last week", "yesterday"), ONLY analyze data from that exact period. Do not mix data from different time periods.
7. When the user asks about a specific month (e.g., "October data"), focus exclusively on that month's data
8. Be empathetic, supportive, and encouraging
9. Always prioritize safety - recommend consulting healthcare providers for medical decisions

Guidelines:
- Use the actual data provided to make recommendations
- Be specific about what you see in their data
- Suggest concrete, actionable steps
- Explain the reasoning behind your recommendations
- If data is insufficient, say so and suggest what would be helpful
- Never make definitive medical diagnoses - always recommend consulting healthcare providers for medical decisions
"""
        return prompt
    
    def _fallback_response(self, message: str) -> str:
        """Fallback response when LLM is not available"""
        return """I'm an LLM-powered diabetes assistant, but I need an OpenAI API key to function.

To enable me:
1. Get an API key from https://platform.openai.com/api-keys
2. Set it in the app settings or as an environment variable: OPENAI_API_KEY

Once configured, I'll be able to:
- Analyze all your blood sugar and meal data
- Understand natural language time windows (e.g., "last week", "yesterday")
- Provide personalized recommendations based on your actual data
- Have natural conversations about your diabetes management"""
