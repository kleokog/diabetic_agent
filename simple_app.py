"""
Simplified Streamlit app for the Diabetic Agent
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from typing import List, Dict, Any

# Import our simplified diabetic agent
from diabetic_agent.simple_agent import SimpleDiabeticAgent
from diabetic_agent.models import UserProfile


def initialize_session_state():
    """Initialize session state variables"""
    if 'agent' not in st.session_state:
        st.session_state.agent = SimpleDiabeticAgent()
    
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
    
    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if blood_sugar_data:
            avg_bs = sum(bs.value for bs in blood_sugar_data) / len(blood_sugar_data)
            st.metric("Average Blood Sugar", f"{avg_bs:.1f} mg/dL")
        else:
            st.metric("Average Blood Sugar", "No data")
    
    with col2:
        st.metric("Today's Readings", len([bs for bs in blood_sugar_data if bs.timestamp.date() == date.today()]))
    
    with col3:
        if blood_sugar_data:
            in_range = sum(1 for bs in blood_sugar_data if 70 <= bs.value <= 180)
            tir = (in_range / len(blood_sugar_data)) * 100
            st.metric("Time in Range", f"{tir:.1f}%")
        else:
            st.metric("Time in Range", "No data")
    
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
    else:
        st.info("No blood sugar data available. Start logging your readings!")


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
    
    # Analysis
    st.subheader("📊 Blood Sugar Analysis")
    if st.button("Run Analysis"):
        analysis = st.session_state.agent.get_blood_sugar_analysis()
        
        if "error" not in analysis:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Average Blood Sugar", f"{analysis['average']:.1f} mg/dL")
            with col2:
                st.metric("Time in Range", f"{analysis['time_in_range']:.1f}%")
            with col3:
                st.metric("Total Readings", analysis['total_readings'])
            
            # Show patterns
            if analysis['patterns']:
                st.subheader("🔍 Identified Patterns")
                for pattern in analysis['patterns']:
                    st.warning(f"⚠️ {pattern}")
            
            # Show recommendations
            if analysis['recommendations']:
                st.subheader("💡 Recommendations")
                for rec in analysis['recommendations']:
                    st.info(f"💡 {rec}")
        else:
            st.error(analysis['error'])


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
            food_name = st.text_input("Food Name", placeholder="e.g., chicken breast")
            quantity = st.number_input("Quantity (grams)", min_value=1, value=100)
        
        submitted = st.form_submit_button("Log Meal")
        
        if submitted and food_name:
            meal_log = st.session_state.agent.log_meal(
                meal_type, [food_name], [quantity], notes
            )
            
            st.success(f"Logged {meal_type} with {food_name}")
            st.write("**Nutritional Summary:**")
            st.write(f"Calories: {meal_log['total_calories']:.1f}")
            st.write(f"Carbs: {meal_log['total_carbs']:.1f}g")
            st.write(f"Protein: {meal_log['total_protein']:.1f}g")
            st.write(f"Fat: {meal_log['total_fat']:.1f}g")
            st.rerun()


def recipe_recommendations():
    """Recipe recommendations page"""
    st.title("👨‍🍳 Recipe Recommendations")
    
    # Get recommendations
    col1, col2 = st.columns(2)
    
    with col1:
        max_carbs = st.slider("Max Carbs (g)", 10, 100, 30)
    
    with col2:
        if st.button("Get Recommendations"):
            recommendations = st.session_state.agent.get_recipe_recommendations(max_carbs)
            
            if recommendations:
                st.success(f"Found {len(recommendations)} diabetes-friendly recipes!")
                
                for recipe in recommendations:
                    with st.expander(f"{recipe['name']} (Score: {recipe['diabetes_score']}/10)"):
                        st.write(f"**Description:** {recipe['description']}")
                        
                        # Nutritional info
                        st.write("**Nutritional Information:**")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Calories", f"{recipe['nutrition']['calories']}")
                        with col2:
                            st.metric("Carbs", f"{recipe['nutrition']['carbs']}g")
                        with col3:
                            st.metric("Protein", f"{recipe['nutrition']['protein']}g")
                        with col4:
                            st.metric("Fat", f"{recipe['nutrition']['fat']}g")
                        
                        # Ingredients
                        st.write("**Ingredients:**")
                        for ingredient in recipe['ingredients']:
                            st.write(f"- {ingredient}")
                        
                        # Instructions
                        st.write("**Instructions:**")
                        for i, instruction in enumerate(recipe['instructions'], 1):
                            st.write(f"{i}. {instruction}")
            else:
                st.info("No recipes found matching your criteria. Try adjusting the carb limit.")


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


def emergency_guidance():
    """Emergency guidance page"""
    st.title("🚨 Emergency Guidance")
    
    st.subheader("Check Your Current Blood Sugar")
    current_bs = st.number_input("Current Blood Sugar (mg/dL)", min_value=20, max_value=600, value=100)
    
    if st.button("Get Emergency Guidance"):
        guidance = st.session_state.agent.get_emergency_guidance(current_bs)
        
        st.subheader(f"📋 {guidance['situation']}")
        
        if 'immediate_actions' in guidance:
            st.write("**Immediate Actions:**")
            for action in guidance['immediate_actions']:
                st.write(f"• {action}")
        
        if 'warning' in guidance:
            st.error(f"⚠️ {guidance['warning']}")
        
        if 'follow_up' in guidance:
            st.info(f"📝 {guidance['follow_up']}")
        
        if 'message' in guidance:
            st.success(guidance['message'])


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
             "AI Chat", "Emergency Guidance"]
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
        elif page == "Emergency Guidance":
            emergency_guidance()


if __name__ == "__main__":
    main()

