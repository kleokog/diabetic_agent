"""
Minimal Diabetic Agent - No external dependencies except Streamlit
"""

import streamlit as st
from datetime import datetime, date
import json
import os

# Simple data storage using JSON files
def load_data():
    """Load data from JSON file"""
    try:
        with open('diabetic_data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            'profile': None,
            'blood_sugar': [],
            'meals': [],
            'chat_history': []
        }

def save_data(data):
    """Save data to JSON file"""
    with open('diabetic_data.json', 'w') as f:
        json.dump(data, f, indent=2, default=str)

def initialize_session_state():
    """Initialize session state"""
    if 'data' not in st.session_state:
        st.session_state.data = load_data()
    
    if 'user_profile_set' not in st.session_state:
        st.session_state.user_profile_set = st.session_state.data['profile'] is not None

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
        
        with col2:
            medications = st.text_area(
                "Current Medications",
                placeholder="List your current diabetes medications (one per line)"
            )
            dietary_restrictions = st.multiselect(
                "Dietary Restrictions",
                ["Vegetarian", "Vegan", "Gluten-free", "Dairy-free", "Nut-free", "Low-carb"]
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
                
                # Create user profile
                profile = {
                    'name': name,
                    'age': age,
                    'diabetes_type': diabetes_type,
                    'medications': med_list,
                    'dietary_restrictions': dietary_restrictions,
                    'target_range': {
                        'fasting': fasting_target,
                        'post_meal': post_meal_target
                    },
                    'created_at': datetime.now().isoformat()
                }
                
                st.session_state.data['profile'] = profile
                st.session_state.user_profile_set = True
                save_data(st.session_state.data)
                st.success("Profile saved successfully!")
                st.rerun()
            else:
                st.error("Please fill in all required fields.")

def dashboard_page():
    """Main dashboard page"""
    st.title("📊 Diabetes Management Dashboard")
    
    # Get recent blood sugar data
    blood_sugar_data = st.session_state.data['blood_sugar']
    recent_data = [bs for bs in blood_sugar_data if bs.get('timestamp', '') >= (datetime.now().date().isoformat())]
    
    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if blood_sugar_data:
            avg_bs = sum(bs['value'] for bs in blood_sugar_data) / len(blood_sugar_data)
            st.metric("Average Blood Sugar", f"{avg_bs:.1f} mg/dL")
        else:
            st.metric("Average Blood Sugar", "No data")
    
    with col2:
        st.metric("Today's Readings", len(recent_data))
    
    with col3:
        if blood_sugar_data:
            in_range = sum(1 for bs in blood_sugar_data if 70 <= bs['value'] <= 180)
            tir = (in_range / len(blood_sugar_data)) * 100
            st.metric("Time in Range", f"{tir:.1f}%")
        else:
            st.metric("Time in Range", "No data")
    
    with col4:
        st.metric("Total Readings", len(blood_sugar_data))
    
    # Simple blood sugar display
    if blood_sugar_data:
        st.subheader("📈 Recent Blood Sugar Readings")
        for bs in blood_sugar_data[-10:]:  # Show last 10 readings
            timestamp = bs.get('timestamp', 'Unknown')
            value = bs['value']
            measurement_type = bs.get('measurement_type', 'Manual')
            
            # Color coding
            if value < 70:
                color = "🔴"
            elif value > 180:
                color = "🟠"
            else:
                color = "🟢"
            
            st.write(f"{color} **{value} mg/dL** ({measurement_type}) - {timestamp}")
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
            reading = {
                'timestamp': datetime.now().isoformat(),
                'value': value,
                'measurement_type': measurement_type,
                'notes': notes
            }
            
            st.session_state.data['blood_sugar'].append(reading)
            save_data(st.session_state.data)
            st.success(f"Added reading: {value} mg/dL")
            st.rerun()
    
    # Analysis
    st.subheader("📊 Blood Sugar Analysis")
    if st.button("Run Analysis"):
        blood_sugar_data = st.session_state.data['blood_sugar']
        
        if blood_sugar_data:
            values = [bs['value'] for bs in blood_sugar_data]
            avg = sum(values) / len(values)
            min_val = min(values)
            max_val = max(values)
            
            # Calculate time in range
            in_range = sum(1 for v in values if 70 <= v <= 180)
            tir = (in_range / len(values)) * 100
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Average Blood Sugar", f"{avg:.1f} mg/dL")
            with col2:
                st.metric("Time in Range", f"{tir:.1f}%")
            with col3:
                st.metric("Total Readings", len(values))
            
            # Simple analysis
            st.subheader("🔍 Analysis Results")
            
            if avg > 180:
                st.warning("⚠️ Your average blood sugar is above the target range. Consider reducing carb intake and checking with your doctor.")
            elif avg < 70:
                st.warning("⚠️ Your average blood sugar is below the target range. Monitor for hypoglycemia and consider reducing insulin doses.")
            else:
                st.success("✅ Your average blood sugar is within the target range. Keep up the good work!")
            
            if max_val > 300:
                st.error("🚨 Very high readings detected. Seek medical attention if this continues.")
            
            if min_val < 50:
                st.error("🚨 Very low readings detected. Keep glucose tablets available.")
            
            # Recommendations
            st.subheader("💡 Recommendations")
            if avg > 180:
                st.info("• Consider reducing carbohydrate intake")
                st.info("• Check with your doctor about insulin adjustments")
                st.info("• Focus on low-carb meals")
            elif avg < 70:
                st.info("• Monitor for hypoglycemia symptoms")
                st.info("• Consider reducing insulin doses")
                st.info("• Eat regular meals and snacks")
            else:
                st.info("• Continue with your current diabetes management routine")
                st.info("• Keep monitoring your blood sugar regularly")
        else:
            st.error("No blood sugar data available for analysis.")

def food_logging():
    """Food logging page"""
    st.title("🍽️ Food Logging")
    
    # Simple food database
    food_db = {
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
    
    # Add meal
    st.subheader("Log a Meal")
    with st.form("meal_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            meal_type = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"])
            notes = st.text_area("Notes (optional)")
        
        with col2:
            st.write("**Add Food Items**")
            food_name = st.selectbox("Food", list(food_db.keys()))
            quantity = st.number_input("Quantity (grams)", min_value=1, value=100)
        
        submitted = st.form_submit_button("Log Meal")
        
        if submitted:
            if food_name in food_db:
                nutrition = food_db[food_name]
                multiplier = quantity / 100  # Assuming quantity is in grams
                
                meal_log = {
                    'timestamp': datetime.now().isoformat(),
                    'meal_type': meal_type,
                    'food_name': food_name,
                    'quantity': quantity,
                    'calories': nutrition['calories'] * multiplier,
                    'carbs': nutrition['carbs'] * multiplier,
                    'protein': nutrition['protein'] * multiplier,
                    'fat': nutrition['fat'] * multiplier,
                    'notes': notes
                }
                
                st.session_state.data['meals'].append(meal_log)
                save_data(st.session_state.data)
                
                st.success(f"Logged {meal_type} with {food_name}")
                st.write("**Nutritional Summary:**")
                st.write(f"Calories: {meal_log['calories']:.1f}")
                st.write(f"Carbs: {meal_log['carbs']:.1f}g")
                st.write(f"Protein: {meal_log['protein']:.1f}g")
                st.write(f"Fat: {meal_log['fat']:.1f}g")
                st.rerun()
    
    # Show recent meals
    if st.session_state.data['meals']:
        st.subheader("📋 Recent Meals")
        for meal in st.session_state.data['meals'][-5:]:  # Show last 5 meals
            with st.expander(f"{meal['meal_type']} - {meal['food_name']} ({meal['timestamp'][:10]})"):
                st.write(f"**Quantity:** {meal['quantity']}g")
                st.write(f"**Calories:** {meal['calories']:.1f}")
                st.write(f"**Carbs:** {meal['carbs']:.1f}g")
                st.write(f"**Protein:** {meal['protein']:.1f}g")
                st.write(f"**Fat:** {meal['fat']:.1f}g")
                if meal.get('notes'):
                    st.write(f"**Notes:** {meal['notes']}")

def recipe_recommendations():
    """Recipe recommendations page"""
    st.title("👨‍🍳 Recipe Recommendations")
    
    # Simple recipe database
    recipes = [
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
    
    # Get recommendations
    col1, col2 = st.columns(2)
    
    with col1:
        max_carbs = st.slider("Max Carbs (g)", 10, 100, 30)
    
    with col2:
        if st.button("Get Recommendations"):
            filtered_recipes = [r for r in recipes if r['nutrition']['carbs'] <= max_carbs]
            
            if filtered_recipes:
                st.success(f"Found {len(filtered_recipes)} diabetes-friendly recipes!")
                
                for recipe in filtered_recipes:
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
        st.session_state.chat_history = st.session_state.data['chat_history']
    
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
        
        # Simple AI response
        response = generate_simple_response(user_input)
        
        # Add AI response to history
        st.session_state.chat_history.append({'role': 'assistant', 'content': response})
        
        # Save to data
        st.session_state.data['chat_history'] = st.session_state.chat_history
        save_data(st.session_state.data)
        
        st.rerun()

def generate_simple_response(message):
    """Generate simple AI response"""
    message_lower = message.lower()
    
    if "blood sugar" in message_lower or "glucose" in message_lower:
        blood_sugar_data = st.session_state.data['blood_sugar']
        if blood_sugar_data:
            values = [bs['value'] for bs in blood_sugar_data]
            avg = sum(values) / len(values)
            return f"Your average blood sugar is {avg:.1f} mg/dL. {'This is above target range - consider reducing carbs.' if avg > 180 else 'This is within target range - great job!' if avg >= 70 else 'This is below target range - monitor for lows.'}"
        else:
            return "I don't have enough blood sugar data to analyze. Please log some readings first."
    
    elif "recipe" in message_lower or "food" in message_lower:
        return "I recommend low-carb, high-protein meals like grilled chicken with vegetables, Greek yogurt parfait, or salmon with quinoa. These help maintain stable blood sugar levels."
    
    elif "help" in message_lower:
        return "I can help you with blood sugar tracking, meal planning, and recipe suggestions. What would you like to know?"
    
    else:
        return "I'm here to help with your diabetes management! I can assist with blood sugar analysis, meal planning, and recipe suggestions."

def emergency_guidance():
    """Emergency guidance page"""
    st.title("🚨 Emergency Guidance")
    
    st.subheader("Check Your Current Blood Sugar")
    current_bs = st.number_input("Current Blood Sugar (mg/dL)", min_value=20, max_value=600, value=100)
    
    if st.button("Get Emergency Guidance"):
        if current_bs < 70:
            st.error("🚨 **HYPOGLYCEMIA (Low Blood Sugar)**")
            st.write("**Immediate Actions:**")
            st.write("• Eat 15g of fast-acting carbs (4 glucose tablets, 4oz juice, or 1 tbsp honey)")
            st.write("• Wait 15 minutes and recheck blood sugar")
            st.write("• If still low, repeat with another 15g of carbs")
            st.write("• Once blood sugar is above 70, eat a protein snack to prevent rebound")
        elif current_bs > 300:
            st.error("🚨 **SEVERE HYPERGLYCEMIA**")
            st.write("**Immediate Actions:**")
            st.write("• Check for ketones if you have a meter")
            st.write("• Take correction insulin as prescribed")
            st.write("• Drink plenty of water")
            st.write("• **WARNING: If you have ketones or feel very ill, seek medical attention immediately**")
        elif current_bs > 180:
            st.warning("⚠️ **HYPERGLYCEMIA (High Blood Sugar)**")
            st.write("**Immediate Actions:**")
            st.write("• Take correction insulin if prescribed")
            st.write("• Drink water to stay hydrated")
            st.write("• Avoid high-carb foods")
            st.write("• Recheck blood sugar in 2 hours")
        else:
            st.success("✅ **NORMAL BLOOD SUGAR**")
            st.write("Your blood sugar is within the target range. Keep up the good work!")
            st.write("Continue with your regular diabetes management routine.")

def main():
    """Main application"""
    initialize_session_state()
    
    # Sidebar navigation
    st.sidebar.title("🏥 Diabetic Agent")
    
    if not st.session_state.user_profile_set:
        setup_user_profile()
    else:
        # Show user info
        profile = st.session_state.data['profile']
        st.sidebar.write(f"👤 **{profile['name']}**")
        st.sidebar.write(f"📊 {profile['diabetes_type']}")
        
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

