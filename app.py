"""
Streamlit web interface for the Diabetic Agent
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import tempfile
import os
from typing import List, Dict, Any

# Import our diabetic agent components
from diabetic_agent.agent import DiabeticAgent
from diabetic_agent.models import UserProfile, BloodSugarLevel, MealLog, InsulinDose, HealthStats


def initialize_session_state():
    """Initialize session state variables"""
    if 'agent' not in st.session_state:
        st.session_state.agent = DiabeticAgent()
    
    if 'user_profile_set' not in st.session_state:
        st.session_state.user_profile_set = False


def setup_user_profile():
    """Setup user profile page"""
    st.title("🏥 Diabetic Agent - Profile Setup")
    st.markdown("Welcome! Let's set up your personalized diabetes management profile.")
    
    with st.form("user_profile_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Full Name", placeholder="Enter your full name")
            age = st.number_input("Age", min_value=1, max_value=120, value=30)
            diabetes_type = st.selectbox(
                "Diabetes Type",
                ["Type 1", "Type 2", "Gestational", "Pre-diabetes", "Other"]
            )
            diagnosis_date = st.date_input("Diagnosis Date", value=date.today())
        
        with col2:
            medications = st.text_area(
                "Current Medications",
                placeholder="List your current diabetes medications (one per line)"
            )
            dietary_restrictions = st.multiselect(
                "Dietary Restrictions",
                ["Vegetarian", "Vegan", "Gluten-free", "Dairy-free", "Nut-free", "Low-carb"]
            )
            allergies = st.text_area(
                "Allergies",
                placeholder="List any food allergies"
            )
        
        # Target blood sugar ranges
        st.subheader("Target Blood Sugar Ranges")
        col1, col2 = st.columns(2)
        with col1:
            fasting_target = st.number_input("Fasting Target (mg/dL)", value=70, min_value=60, max_value=120)
        with col2:
            post_meal_target = st.number_input("Post-Meal Target (mg/dL)", value=180, min_value=140, max_value=200)
        
        submitted = st.form_submit_button("Save Profile")
        
        if submitted:
            if name and age and diabetes_type:
                # Process medications
                med_list = [med.strip() for med in medications.split('\n') if med.strip()] if medications else []
                
                # Process allergies
                allergy_list = [allergy.strip() for allergy in allergies.split(',') if allergy.strip()] if allergies else []
                
                # Create user profile
                profile = st.session_state.agent.setup_user_profile(
                    name=name,
                    age=age,
                    diabetes_type=diabetes_type,
                    diagnosis_date=diagnosis_date.strftime("%Y-%m-%d"),
                    medications=med_list,
                    dietary_restrictions=dietary_restrictions,
                    allergies=allergy_list,
                    target_range={
                        'fasting': fasting_target,
                        'post_meal': post_meal_target
                    }
                )
                
                st.session_state.user_profile_set = True
                st.success("Profile saved successfully!")
                st.rerun()
            else:
                st.error("Please fill in all required fields.")


def dashboard_page():
    """Main dashboard page"""
    st.title("📊 Diabetes Management Dashboard")
    
    # Get recent data
    blood_sugar_data = st.session_state.agent.db.get_blood_sugar_levels(1, 7)
    meal_logs = st.session_state.agent.db.get_meal_logs(1, 7)
    
    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if blood_sugar_data:
            avg_bs = sum(bs.value for bs in blood_sugar_data) / len(blood_sugar_data)
            st.metric("Average Blood Sugar", f"{avg_bs:.1f} mg/dL")
        else:
            st.metric("Average Blood Sugar", "No data")
    
    with col2:
        st.metric("Today's Meals", len([m for m in meal_logs if m.timestamp.date() == date.today()]))
    
    with col3:
        st.metric("Time in Range", "85%")  # This would be calculated from actual data
    
    with col4:
        st.metric("Active Streak", "7 days")
    
    # Blood sugar chart
    if blood_sugar_data:
        st.subheader("📈 Blood Sugar Trends")
        
        # Prepare data for plotting
        df = pd.DataFrame([{
            'timestamp': bs.timestamp,
            'value': bs.value,
            'type': bs.measurement_type
        } for bs in blood_sugar_data])
        
        # Create plot
        fig = px.line(df, x='timestamp', y='value', 
                     title='Blood Sugar Over Time',
                     labels={'value': 'Blood Sugar (mg/dL)', 'timestamp': 'Time'})
        
        # Add target range
        fig.add_hline(y=70, line_dash="dash", line_color="red", 
                     annotation_text="Hypoglycemia")
        fig.add_hline(y=180, line_dash="dash", line_color="orange", 
                     annotation_text="Hyperglycemia")
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Recent meals
    if meal_logs:
        st.subheader("🍽️ Recent Meals")
        recent_meals = meal_logs[:5]  # Show last 5 meals
        
        for meal in recent_meals:
            with st.expander(f"{meal.meal_type} - {meal.timestamp.strftime('%Y-%m-%d %H:%M')}"):
                st.write(f"**Total Calories:** {meal.total_calories:.1f}")
                st.write(f"**Carbs:** {meal.total_carbs:.1f}g")
                st.write(f"**Protein:** {meal.total_protein:.1f}g")
                st.write(f"**Fat:** {meal.total_fat:.1f}g")
                
                if meal.food_items:
                    st.write("**Food Items:**")
                    for item in meal.food_items:
                        st.write(f"- {item.name}: {item.quantity:.1f}g")


def blood_sugar_tracking():
    """Blood sugar tracking page"""
    st.title("🩸 Blood Sugar Tracking")
    
    # Manual entry
    st.subheader("Add Blood Sugar Reading")
    with st.form("blood_sugar_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            value = st.number_input("Blood Sugar (mg/dL)", min_value=20, max_value=600, value=100)
            measurement_type = st.selectbox("Measurement Type", 
                                         ["Fasting", "Pre-meal", "Post-meal", "Random", "Bedtime"])
        
        with col2:
            notes = st.text_area("Notes (optional)")
        
        submitted = st.form_submit_button("Add Reading")
        
        if submitted:
            reading = st.session_state.agent.add_blood_sugar_reading(
                value=value,
                measurement_type=measurement_type,
                notes=notes
            )
            st.success(f"Added reading: {value} mg/dL")
            st.rerun()
    
    # Chart analysis
    st.subheader("📊 Analyze Blood Sugar Chart")
    uploaded_file = st.file_uploader("Upload Blood Sugar Chart Image", type=['png', 'jpg', 'jpeg'])
    
    if uploaded_file is not None:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        try:
            # Analyze the chart
            with st.spinner("Analyzing chart..."):
                blood_sugar_data, analysis = st.session_state.agent.analyze_blood_sugar_chart(tmp_path)
            
            if blood_sugar_data:
                st.success(f"Extracted {len(blood_sugar_data)} blood sugar readings from the chart!")
                
                # Show extracted data
                st.subheader("Extracted Data")
                df = pd.DataFrame([{
                    'Time': bs.timestamp.strftime('%H:%M'),
                    'Value': bs.value,
                    'Type': bs.measurement_type
                } for bs in blood_sugar_data])
                st.dataframe(df)
                
                # Show analysis
                if 'error' not in analysis:
                    st.subheader("Analysis Results")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.metric("Average Blood Sugar", f"{analysis['average_blood_sugar']:.1f} mg/dL")
                        st.metric("Time in Range", f"{analysis['time_in_range']:.1f}%")
                    
                    with col2:
                        st.metric("Min Reading", f"{analysis['min_blood_sugar']:.1f} mg/dL")
                        st.metric("Max Reading", f"{analysis['max_blood_sugar']:.1f} mg/dL")
                    
                    # Show patterns
                    if analysis['patterns']:
                        st.subheader("Identified Patterns")
                        for pattern in analysis['patterns']:
                            st.warning(f"⚠️ {pattern}")
                    
                    # Show recommendations
                    if analysis['recommendations']:
                        st.subheader("Recommendations")
                        for rec in analysis['recommendations']:
                            st.info(f"💡 {rec}")
            else:
                st.error("Could not extract blood sugar data from the image. Please try a clearer image.")
        
        finally:
            # Clean up temporary file
            os.unlink(tmp_path)


def food_logging():
    """Food logging page"""
    st.title("🍽️ Food Logging")
    
    # Add meal
    st.subheader("Log a Meal")
    with st.form("meal_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            meal_type = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"])
            notes = st.text_area("Notes (optional)")
        
        with col2:
            st.write("**Add Food Items**")
            # This is a simplified version - in a real app, you'd have a more sophisticated food search
            food_name = st.text_input("Food Name", placeholder="e.g., chicken breast")
            quantity = st.number_input("Quantity", min_value=0.1, value=100.0)
            unit = st.selectbox("Unit", ["grams", "cups", "pieces", "tablespoons"])
        
        submitted = st.form_submit_button("Log Meal")
        
        if submitted and food_name:
            food_items = [{
                'name': food_name,
                'quantity': quantity,
                'unit': unit
            }]
            
            meal_log = st.session_state.agent.log_meal(meal_type, food_items, notes)
            st.success(f"Logged {meal_type} with {food_name}")
            st.rerun()
    
    # Daily nutrition summary
    st.subheader("📊 Daily Nutrition Summary")
    daily_nutrition = st.session_state.agent.food_tracker.get_daily_nutrition_summary()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Calories", f"{daily_nutrition['calories']:.0f}")
    with col2:
        st.metric("Carbs", f"{daily_nutrition['carbohydrates']:.1f}g")
    with col3:
        st.metric("Protein", f"{daily_nutrition['protein']:.1f}g")
    with col4:
        st.metric("Fat", f"{daily_nutrition['fat']:.1f}g")


def recipe_recommendations():
    """Recipe recommendations page"""
    st.title("👨‍🍳 Recipe Recommendations")
    
    # Get recommendations
    col1, col2 = st.columns(2)
    
    with col1:
        meal_type = st.selectbox("Meal Type", ["any", "breakfast", "lunch", "dinner", "snack"])
        max_carbs = st.slider("Max Carbs (g)", 10, 100, 30)
    
    with col2:
        if st.button("Get Recommendations"):
            with st.spinner("Finding personalized recipes..."):
                recommendations = st.session_state.agent.get_recipe_recommendations(
                    meal_type=meal_type,
                    max_carbs=max_carbs
                )
            
            if recommendations:
                st.success(f"Found {len(recommendations)} personalized recipes!")
                
                for i, recipe in enumerate(recommendations):
                    with st.expander(f"{recipe.name} (Score: {recipe.diabetes_friendly_score}/10)"):
                        st.write(f"**Description:** {recipe.description}")
                        st.write(f"**Prep Time:** {recipe.prep_time} min | **Cook Time:** {recipe.cook_time} min | **Servings:** {recipe.servings}")
                        
                        # Nutritional info
                        st.write("**Nutritional Information:**")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Calories", f"{recipe.nutritional_info['calories']}")
                        with col2:
                            st.metric("Carbs", f"{recipe.nutritional_info['carbohydrates']}g")
                        with col3:
                            st.metric("Protein", f"{recipe.nutritional_info['protein']}g")
                        with col4:
                            st.metric("Fat", f"{recipe.nutritional_info['fat']}g")
                        
                        # Ingredients
                        st.write("**Ingredients:**")
                        for ingredient in recipe.ingredients:
                            st.write(f"- {ingredient}")
                        
                        # Instructions
                        st.write("**Instructions:**")
                        for j, instruction in enumerate(recipe.instructions, 1):
                            st.write(f"{j}. {instruction}")
            else:
                st.info("No recipes found matching your criteria. Try adjusting the filters.")


def ai_chat():
    """AI chat page"""
    st.title("🤖 AI Diabetes Assistant")
    st.markdown("Chat with your personalized diabetes management assistant!")
    
    # Chat history
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Display chat history
    for message in st.session_state.chat_history:
        if message['role'] == 'user':
            st.write(f"**You:** {message['content']}")
        else:
            st.write(f"**Assistant:** {message['content']}")
    
    # Chat input
    user_input = st.text_input("Ask me anything about your diabetes management:", key="chat_input")
    
    if st.button("Send") and user_input:
        # Add user message to history
        st.session_state.chat_history.append({'role': 'user', 'content': user_input})
        
        # Get AI response
        with st.spinner("Thinking..."):
            response = st.session_state.agent.chat_with_agent(user_input)
        
        # Add AI response to history
        st.session_state.chat_history.append({'role': 'assistant', 'content': response})
        
        st.rerun()


def analysis_page():
    """Comprehensive analysis page"""
    st.title("🔍 Comprehensive Analysis")
    
    if st.button("Run Analysis"):
        with st.spinner("Analyzing your diabetes data..."):
            analysis = st.session_state.agent.get_comprehensive_analysis()
        
        # Display analysis results
        st.subheader("📊 Analysis Results")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Average Blood Sugar", f"{analysis.average_blood_sugar:.1f} mg/dL")
        with col2:
            st.metric("Time in Range", f"{analysis.time_in_range:.1f}%")
        with col3:
            st.metric("Total Readings", f"{len(analysis.patterns)} patterns identified")
        
        # Patterns
        if analysis.patterns:
            st.subheader("🔍 Identified Patterns")
            for pattern in analysis.patterns:
                with st.expander(f"{pattern.pattern_type} - {pattern.severity} severity"):
                    st.write(f"**Frequency:** {pattern.frequency}")
                    st.write("**Potential Causes:**")
                    for cause in pattern.potential_causes:
                        st.write(f"- {cause}")
                    st.write("**Recommendations:**")
                    for rec in pattern.recommendations:
                        st.write(f"- {rec}")
        
        # Recommendations
        if analysis.recommendations:
            st.subheader("💡 Personalized Recommendations")
            for rec in analysis.recommendations:
                st.info(f"💡 {rec}")
        
        # Risk factors
        if analysis.risk_factors:
            st.subheader("⚠️ Risk Factors")
            for risk in analysis.risk_factors:
                st.warning(f"⚠️ {risk}")
        
        # Positive trends
        if analysis.positive_trends:
            st.subheader("✅ Positive Trends")
            for trend in analysis.positive_trends:
                st.success(f"✅ {trend}")


def main():
    """Main application"""
    initialize_session_state()
    
    # Sidebar navigation
    st.sidebar.title("🏥 Diabetic Agent")
    
    if not st.session_state.user_profile_set:
        setup_user_profile()
    else:
        # Navigation menu
        page = st.sidebar.selectbox(
            "Navigate",
            ["Dashboard", "Blood Sugar Tracking", "Food Logging", "Recipe Recommendations", 
             "AI Chat", "Analysis"]
        )
        
        if page == "Dashboard":
            dashboard_page()
        elif page == "Blood Sugar Tracking":
            blood_sugar_tracking()
        elif page == "Food Logging":
            food_logging()
        elif page == "Recipe Recommendations":
            recipe_recommendations()
        elif page == "AI Chat":
            ai_chat()
        elif page == "Analysis":
            analysis_page()


if __name__ == "__main__":
    main()

