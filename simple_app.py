"""
Simplified Streamlit app for the Diabetic Agent
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional

# Import our simplified diabetic agent
from diabetic_agent.simple_agent import SimpleDiabeticAgent
from diabetic_agent.models import UserProfile


def initialize_session_state():
    """Initialize session state variables"""
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    
    if 'user_name' not in st.session_state:
        st.session_state.user_name = None
    
    if 'agent' not in st.session_state:
        # Will be initialized after user selection
        st.session_state.agent = None
    
    if 'user_profile_set' not in st.session_state:
        st.session_state.user_profile_set = False
    
    # Track processed files to prevent duplicate imports
    if 'processed_files' not in st.session_state:
        st.session_state.processed_files = set()


def user_selection_page():
    """User selection/login page"""
    st.title("🏥 Diabetic Agent - User Selection")
    st.markdown("Select your profile or create a new one.")
    
    # Create a temporary agent to access database
    temp_agent = SimpleDiabeticAgent(user_id=1)
    all_users = temp_agent.db.get_all_users()
    
    # User selection options
    if all_users:
        st.subheader("👤 Select Existing User")
        
        user_options = [f"{user['name']} (Age: {user['age']}, {user['diabetes_type']})" for user in all_users]
        user_options.append("➕ Create New User")
        
        selected_user = st.selectbox("Choose a user profile:", user_options, key="user_select")
        
        if selected_user and selected_user != "➕ Create New User":
            # Extract user ID from selection
            selected_name = selected_user.split(" (Age:")[0]
            user_id = temp_agent.db.find_user_by_name(selected_name)
            
            if st.button("Login", key="login_btn"):
                # Initialize agent with this user_id
                st.session_state.user_id = user_id
                st.session_state.user_name = selected_name
                st.session_state.agent = SimpleDiabeticAgent(user_id=user_id)
                
                # Load existing profile
                profile = st.session_state.agent.db.get_user_profile(user_id)
                if profile:
                    st.session_state.user_profile_set = True
                    st.session_state.agent.user_profile = profile
                    st.success(f"Welcome back, {selected_name}!")
                    st.rerun()
    else:
        st.info("No existing users found. Please create a new user profile.")
    
    # Create new user option
    st.subheader("➕ Create New User")
    with st.form("new_user_form"):
        name = st.text_input("Full Name", placeholder="Enter your full name", key="new_user_name")
        create_user = st.form_submit_button("Create New User")
        
        if create_user:
            if name and name.strip():
                # Check if user already exists
                existing_user_id = temp_agent.db.find_user_by_name(name.strip())
                if existing_user_id:
                    st.error(f"User '{name.strip()}' already exists! Please select from existing users or use a different name.")
                else:
                    # Get next user ID
                    new_user_id = temp_agent.db.get_next_user_id()
                    
                    # Initialize agent with new user_id
                    st.session_state.user_id = new_user_id
                    st.session_state.user_name = name.strip()
                    st.session_state.agent = SimpleDiabeticAgent(user_id=new_user_id)
                    st.session_state.user_profile_set = False
                    
                    st.success(f"User '{name.strip()}' created! Please set up your profile.")
                    st.rerun()
            else:
                st.error("Please enter a name.")


def setup_user_profile():
    """Setup user profile page"""
    st.title("🏥 Diabetic Agent - Profile Setup")
    st.markdown(f"Welcome, **{st.session_state.user_name}**! Let's set up your personalized diabetes management profile.")
    
    with st.form("user_profile_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Full Name", value=st.session_state.user_name, disabled=True)
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
    
    # Date range filter
    st.subheader("⏱️ Date Range Filter")
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date.today() - timedelta(days=7),
            key="dashboard_start_date"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=date.today(),
            key="dashboard_end_date"
        )
    
    # Validate date range
    if start_date > end_date:
        st.error("⚠️ Start date must be before or equal to end date!")
        return
    
    # Convert dates to datetime for database query (end of day for end_date)
    start_datetime = datetime.combine(start_date, datetime.min.time())
    # Set end_datetime to end of day (23:59:59.999999)
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Calculate days for display
    days = (end_date - start_date).days + 1
    
    st.info(f"📅 Showing data from **{start_date.strftime('%Y-%m-%d')}** to **{end_date.strftime('%Y-%m-%d')}** ({days} days)")
    
    # Get data based on selected date range
    user_id = st.session_state.user_id
    blood_sugar_data = st.session_state.agent.db.get_blood_sugar_levels(
        user_id, days=30, start_date=start_datetime, end_date=end_datetime
    )
    meal_logs = st.session_state.agent.db.get_meal_logs(
        user_id, days=30, start_date=start_datetime, end_date=end_datetime
    )
    
    # Summary cards - Blood Sugar
    st.subheader("🩸 Blood Sugar Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if blood_sugar_data:
            avg_bs = sum(bs.value for bs in blood_sugar_data) / len(blood_sugar_data)
            st.metric("Average Blood Sugar", f"{avg_bs:.1f} mg/dL")
        else:
            st.metric("Average Blood Sugar", "No data")
    
    with col2:
        if start_date == end_date == date.today():
            st.metric("Today's Readings", len([bs for bs in blood_sugar_data if bs.timestamp.date() == date.today()]))
        else:
            st.metric("Total Readings", len(blood_sugar_data))
    
    with col3:
        if blood_sugar_data:
            in_range = sum(1 for bs in blood_sugar_data if 70 <= bs.value <= 180)
            tir = (in_range / len(blood_sugar_data)) * 100
            st.metric("Time in Range", f"{tir:.1f}%")
        else:
            st.metric("Time in Range", "No data")
    
    with col4:
        if blood_sugar_data:
            min_bs = min(bs.value for bs in blood_sugar_data)
            max_bs = max(bs.value for bs in blood_sugar_data)
            st.metric("Range", f"{min_bs:.0f}-{max_bs:.0f} mg/dL")
        else:
            st.metric("Range", "No data")
    
    # Summary cards - Meal/Nutrition
    st.subheader("🍽️ Meal & Nutrition Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    # Calculate metrics based on selected date range
    if start_date == end_date == date.today():
        period_meals = [m for m in meal_logs if m.timestamp.date() == date.today()]
        period_label = "Today's"
    else:
        period_meals = meal_logs
        period_label = "Total"
    
    with col1:
        st.metric(f"{period_label} Meals", len(period_meals))
    
    with col2:
        if period_meals:
            total_calories = sum(m.total_calories for m in period_meals)
            if start_date == end_date == date.today():
                st.metric(f"{period_label} Calories", f"{total_calories:.0f}")
            else:
                avg_calories = total_calories / days if days > 0 else 0
                st.metric(f"Avg Daily Calories", f"{avg_calories:.0f}")
        else:
            st.metric(f"{period_label} Calories", "No data")
    
    with col3:
        if period_meals:
            total_carbs = sum(m.total_carbs for m in period_meals)
            if start_date == end_date == date.today():
                st.metric(f"{period_label} Carbs", f"{total_carbs:.1f}g")
            else:
                avg_carbs = total_carbs / days if days > 0 else 0
                st.metric(f"Avg Daily Carbs", f"{avg_carbs:.1f}g")
        else:
            st.metric(f"{period_label} Carbs", "No data")
    
    with col4:
        if period_meals:
            total_protein = sum(m.total_protein for m in period_meals)
            if start_date == end_date == date.today():
                st.metric(f"{period_label} Protein", f"{total_protein:.1f}g")
            else:
                avg_protein = total_protein / days if days > 0 else 0
                st.metric(f"Avg Daily Protein", f"{avg_protein:.1f}g")
        else:
            st.metric(f"{period_label} Protein", "No data")
    
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
    
    # Recent meals section
    if meal_logs:
        st.subheader(f"🍽️ Recent Meals")
        
        # Show last 10 meals (or all if less than 10)
        recent_meals = sorted(meal_logs, key=lambda x: x.timestamp, reverse=True)[:10]
        
        for meal in recent_meals:
            with st.expander(f"{meal.meal_type} - {meal.timestamp.strftime('%Y-%m-%d %H:%M')}"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Calories", f"{meal.total_calories:.1f}")
                with col2:
                    st.metric("Carbs", f"{meal.total_carbs:.1f}g")
                with col3:
                    st.metric("Protein", f"{meal.total_protein:.1f}g")
                with col4:
                    st.metric("Fat", f"{meal.total_fat:.1f}g")
                
                if meal.food_items:
                    st.write("**Food Items:**")
                    for item in meal.food_items:
                        st.write(f"- {item.name}: {item.quantity:.1f}{item.unit}")
                
                if meal.notes:
                    st.write(f"**Notes:** {meal.notes}")
    else:
        st.info("No meal data available. Start logging your meals!")
    
    # Daily nutrition charts
    if meal_logs:
        # Group meals by date
        daily_nutrition = {}
        for meal in meal_logs:
            meal_date = meal.timestamp.date()
            if meal_date not in daily_nutrition:
                daily_nutrition[meal_date] = {
                    'calories': 0,
                    'carbs': 0,
                    'protein': 0,
                    'fat': 0
                }
            daily_nutrition[meal_date]['calories'] += meal.total_calories
            daily_nutrition[meal_date]['carbs'] += meal.total_carbs
            daily_nutrition[meal_date]['protein'] += meal.total_protein
            daily_nutrition[meal_date]['fat'] += meal.total_fat
        
        # Create dataframe for plotting
        nutrition_df = pd.DataFrame([
            {
                'date': date_key,
                'Calories': values['calories'],
                'Carbs (g)': values['carbs'],
                'Protein (g)': values['protein'],
                'Fat (g)': values['fat']
            }
            for date_key, values in sorted(daily_nutrition.items())
        ])
        
        if not nutrition_df.empty:
            # Chart 1: Daily Calories (separate chart due to different magnitude)
            st.subheader("📊 Daily Calories")
            fig_calories = px.line(nutrition_df, x='date', y='Calories',
                                 title='Daily Calorie Intake',
                                 labels={'Calories': 'Calories', 'date': 'Date'})
            fig_calories.update_traces(line_color='#FF6B6B', line_width=2)
            st.plotly_chart(fig_calories, use_container_width=True)
            
            # Chart 2: Daily Macros (Carbs, Protein, Fat) - separate chart
            st.subheader("📊 Daily Macronutrients (Carbs, Protein, Fat)")
            fig_macros = px.line(nutrition_df, x='date', y=['Carbs (g)', 'Protein (g)', 'Fat (g)'],
                                title='Daily Macronutrient Intake',
                                labels={'value': 'Grams', 'date': 'Date', 'variable': 'Macronutrient'})
            st.plotly_chart(fig_macros, use_container_width=True)
            
            # Chart 3: Average Macro Percentage Distribution
            st.subheader("🥗 Average Macronutrient Distribution")
            
            # Calculate total macros across all days
            total_carbs = nutrition_df['Carbs (g)'].sum()
            total_protein = nutrition_df['Protein (g)'].sum()
            total_fat = nutrition_df['Fat (g)'].sum()
            total_macros = total_carbs + total_protein + total_fat
            
            if total_macros > 0:
                # Calculate percentages
                carbs_pct = (total_carbs / total_macros) * 100
                protein_pct = (total_protein / total_macros) * 100
                fat_pct = (total_fat / total_macros) * 100
                
                # Create pie chart
                macro_percentages = pd.DataFrame({
                    'Macronutrient': ['Carbs', 'Protein', 'Fat'],
                    'Percentage': [carbs_pct, protein_pct, fat_pct],
                    'Grams': [total_carbs, total_protein, total_fat]
                })
                
                fig_pie = px.pie(macro_percentages, 
                                values='Percentage', 
                                names='Macronutrient',
                                title=f'Average Distribution: {carbs_pct:.1f}% Carbs, {protein_pct:.1f}% Protein, {fat_pct:.1f}% Fat',
                                hover_data=['Grams'])
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
                
                # Display summary
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Carbs", f"{carbs_pct:.1f}%", f"{total_carbs:.1f}g total")
                with col2:
                    st.metric("Protein", f"{protein_pct:.1f}%", f"{total_protein:.1f}g total")
                with col3:
                    st.metric("Fat", f"{fat_pct:.1f}%", f"{total_fat:.1f}g total")
            else:
                st.info("No macronutrient data available for the selected period.")


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
 
    st.subheader("📥 Import Blood Sugar CSV")
    uploaded_file = st.file_uploader(
        "Upload glucose CSV", type=["csv"], key="blood_sugar_csv_uploader"
    )

    # Create a unique identifier for this file
    if uploaded_file is not None:
        file_id = f"bs_{uploaded_file.name}_{uploaded_file.size}"
        
        # Check if file was already processed
        if file_id in st.session_state.processed_files:
            st.info("✅ This file has already been imported. Upload a new file to import more data.")
            if st.button("🔄 Re-import this file", key="reimport_bs_file"):
                st.session_state.processed_files.discard(file_id)
                # Clear cached import data
                import_key = f"bs_import_data_{file_id}"
                if import_key in st.session_state:
                    del st.session_state[import_key]
                st.rerun()
        else:
            # Store file data in session state to prevent re-reading on rerun
            import_key = f"bs_import_data_{file_id}"
            import_button_key = f"import_bs_button_{file_id}"
            
            # Load and validate file (only once)
            if import_key not in st.session_state:
                try:
                    df = pd.read_csv(uploaded_file)
                    st.session_state[import_key] = df
                except Exception as exc:
                    st.error(f"Failed to read CSV file: {exc}")
                    st.session_state[import_key] = None
            else:
                df = st.session_state[import_key]
            
            if df is not None and not df.empty:
                normalized = {col.strip().lower(): col for col in df.columns}

                value_candidates = [
                    "historic glucose mg/dl",
                    "scan glucose mg/dl"
                ]
                value_key = next((c for c in value_candidates if c in normalized), None)

                required_missing = [
                    col for col in ["device timestamp"] if col not in normalized
                ]
                if value_key is None:
                    required_missing.append("historic glucose mg/dl")

                if required_missing:
                    st.error(
                        "Missing required columns in CSV: "
                        + ", ".join(f"'{col}'" for col in required_missing)
                    )
                else:
                    rename_map = {
                        normalized["device timestamp"]: "timestamp",
                        normalized[value_key]: "value"
                    }

                    if "notes" in normalized:
                        rename_map[normalized["notes"]] = "notes"

                    preview_df = df.rename(columns=rename_map)
                    
                    # Show preview
                    st.info(f"📄 File loaded: **{uploaded_file.name}** ({len(preview_df)} rows)")
                    st.write("**Preview of data to be imported:**")
                    st.dataframe(preview_df.head(10)[["timestamp", "value"]])
                    
                    # Import button
                    if st.button("✅ Import Blood Sugar Readings", key=import_button_key, type="primary"):
                        df = preview_df.copy()
                        original_rows = len(df)

                        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
                        df["value"] = pd.to_numeric(df["value"], errors="coerce")

                        cleaned = df.dropna(subset=["timestamp", "value"]).copy()

                        # Keep only realistic glucose values
                        cleaned = cleaned[cleaned["value"].between(20, 600)]

                        if cleaned.empty:
                            st.warning("No valid blood sugar rows found in the uploaded file.")
                        else:
                            cleaned = cleaned.sort_values("timestamp")
                            imported = 0

                            with st.spinner("Importing blood sugar readings..."):
                                for _, row in cleaned.iterrows():
                                    note_value = row.get("notes")
                                    if note_value is not None and pd.isna(note_value):
                                        note_value = None
                                    elif note_value is not None:
                                        note_value = str(note_value)

                                    st.session_state.agent.add_blood_sugar_reading(
                                        value=float(row["value"]),
                                        measurement_type="Imported",
                                        notes=note_value,
                                        timestamp=row["timestamp"].to_pydatetime()
                                    )
                                    imported += 1

                            # Mark file as processed and clear cached data
                            st.session_state.processed_files.add(file_id)
                            if import_key in st.session_state:
                                del st.session_state[import_key]
                            
                            st.success(f"Imported {imported} blood sugar readings from CSV.")
                            skipped_total = original_rows - imported
                            if skipped_total > 0:
                                st.info(
                                    f"Skipped {skipped_total} rows due to missing, invalid, or out-of-range data."
                                )

                            st.rerun()
    
    # Add button to clear processed files (for re-importing same file)
    if any(fid.startswith("bs_") for fid in st.session_state.processed_files):
        if st.button("🔄 Clear Import History (to re-import files)", key="clear_bs_imports"):
            # Only clear blood sugar file IDs
            st.session_state.processed_files = {fid for fid in st.session_state.processed_files if not fid.startswith("bs_")}
            st.success("Import history cleared. You can now re-import files.")
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
            meal_date = st.date_input("Meal Date", value=date.today())
            meal_time = st.time_input("Meal Time", value=datetime.now().time())
            notes = st.text_area("Notes (optional)")
        
        with col2:
            st.write("**Add Food Items**")
            food_name = st.text_input("Food Name", placeholder="e.g., chicken breast")
            quantity = st.number_input("Quantity (grams)", min_value=1, value=100)
        
        submitted = st.form_submit_button("Log Meal")
        
        if submitted and food_name:
            # Combine date and time into datetime
            meal_datetime = datetime.combine(meal_date, meal_time)
            
            meal_log = st.session_state.agent.log_meal(
                meal_type, [food_name], [quantity], notes, timestamp=meal_datetime
            )
            
            st.success(f"Logged {meal_type} with {food_name}")
            st.write("**Nutritional Summary:**")
            st.write(f"Calories: {meal_log['total_calories']:.1f}")
            st.write(f"Carbs: {meal_log['total_carbs']:.1f}g")
            st.write(f"Protein: {meal_log['total_protein']:.1f}g")
            st.write(f"Fat: {meal_log['total_fat']:.1f}g")
            st.rerun()
    
    # CSV Import section
    st.subheader("📥 Import Meals from CSV (MyFitnessPal)")
    uploaded_meal_file = st.file_uploader(
        "Upload meal/nutrition CSV", type=["csv"], key="meal_csv_uploader"
    )
    
    # Create a unique identifier for this file
    if uploaded_meal_file is not None:
        file_id = f"{uploaded_meal_file.name}_{uploaded_meal_file.size}"
        
        # Check if file was already processed
        if file_id in st.session_state.processed_files:
            st.info("✅ This file has already been imported. Upload a new file to import more data.")
            if st.button("🔄 Re-import this file", key="reimport_meal_file"):
                st.session_state.processed_files.discard(file_id)
                st.rerun()
        else:
            # Store file data in session state to prevent re-reading on rerun
            import_key = f"meal_import_data_{file_id}"
            import_button_key = f"import_meal_button_{file_id}"
            
            # Load and validate file (only once)
            if import_key not in st.session_state:
                try:
                    df = pd.read_csv(uploaded_meal_file)
                    st.session_state[import_key] = df
                except Exception as exc:
                    st.error(f"Failed to read CSV file: {exc}")
                    st.session_state[import_key] = None
            else:
                df = st.session_state[import_key]
            
            if df is not None and not df.empty:
                # Normalize column names (handle variations and case-insensitive matching)
                # Create mapping of normalized names to original column names
                normalized = {}
                for col in df.columns:
                    col_lower = col.strip().lower()
                    normalized[col_lower] = col
                    # Also add version without parentheses content for flexibility
                    col_no_units = col_lower.split('(')[0].strip()
                    if col_no_units not in normalized:
                        normalized[col_no_units] = col
                
                # Required columns mapping
                date_key = None
                meal_key = None
                calories_key = None
                carbs_key = None
                protein_key = None
                fat_key = None
                
                # Find date column (try different variations)
                date_candidates = ["date", "meal date", "date/time"]
                for candidate in date_candidates:
                    if candidate in normalized:
                        date_key = normalized[candidate]
                        break
                
                # Find meal type column
                meal_candidates = ["meal", "meal type", "mealname"]
                for candidate in meal_candidates:
                    if candidate in normalized:
                        meal_key = normalized[candidate]
                        break
                
                # Find nutrition columns (check exact matches first, then variations)
                calories_candidates = ["calories", "calorie"]
                for candidate in calories_candidates:
                    if candidate in normalized:
                        calories_key = normalized[candidate]
                        break
                
                # Carbohydrates - check for exact match with (g) first
                carbs_candidates = [
                    "carbohydrates (g)", "carbohydrate (g)", 
                    "carbohydrates", "carbohydrate", 
                    "carbs (g)", "carbs", 
                    "total carbs", "carbohydrate"
                ]
                for candidate in carbs_candidates:
                    if candidate in normalized:
                        carbs_key = normalized[candidate]
                        break
                
                # Protein
                protein_candidates = ["protein (g)", "protein", "total protein"]
                for candidate in protein_candidates:
                    if candidate in normalized:
                        protein_key = normalized[candidate]
                        break
                
                # Fat
                fat_candidates = ["fat (g)", "fat", "total fat"]
                for candidate in fat_candidates:
                    if candidate in normalized:
                        fat_key = normalized[candidate]
                        break
                
                # Check for required columns
                required_missing = []
                if not date_key:
                    required_missing.append("Date")
                if not meal_key:
                    required_missing.append("Meal")
                if not calories_key:
                    required_missing.append("Calories")
                if not carbs_key:
                    required_missing.append("Carbohydrates (g)")
                if not protein_key:
                    required_missing.append("Protein (g)")
                if not fat_key:
                    required_missing.append("Fat (g)")
                
                if required_missing:
                    st.error(
                        f"Missing required columns in CSV: {', '.join(required_missing)}\n\n"
                        f"Found columns: {', '.join(df.columns)}"
                    )
                else:
                    # Show preview
                    st.info(f"📄 File loaded: **{uploaded_meal_file.name}** ({len(df)} rows)")
                    st.write("**Preview of data to be imported:**")
                    preview_df = df.head(5)[[date_key, meal_key, calories_key, carbs_key, protein_key, fat_key]]
                    st.dataframe(preview_df)
                    
                    # Import button
                    if st.button("✅ Import Meals", key=import_button_key, type="primary"):
                        # Optional columns (with variations)
                        fiber_candidates = ["fiber", "fiber (g)", "total fiber"]
                        fiber_key = next((normalized[k] for k in fiber_candidates if k in normalized), None)
                        
                        sugar_candidates = ["sugar", "sugar (g)", "total sugar"]
                        sugar_key = next((normalized[k] for k in sugar_candidates if k in normalized), None)
                        
                        notes_candidates = ["note", "notes"]
                        notes_key = next((normalized[k] for k in notes_candidates if k in normalized), None)
                        
                        # Additional optional nutrition columns
                        saturated_fat_key = next((normalized[k] for k in ["saturated fa", "saturated fat", "saturated fat (g)"] if k in normalized), None)
                        cholesterol_key = next((normalized[k] for k in ["cholesterol", "cholesterol (mg)"] if k in normalized), None)
                        sodium_key = next((normalized[k] for k in ["sodium (mg)", "sodium"] if k in normalized), None)
                        
                        # Process the data
                        original_rows = len(df)
                        imported = 0
                        skipped = 0
                        errors = []
                        
                        with st.spinner("Importing meals..."):
                            for idx, row in df.iterrows():
                                try:
                                    # Parse date (handle DD/MM/YYYY format)
                                    date_str = str(row[date_key]).strip()
                                    try:
                                        # Try DD/MM/YYYY format first
                                        meal_date_obj = pd.to_datetime(date_str, format='%d/%m/%Y', errors='coerce')
                                        if pd.isna(meal_date_obj):
                                            # Try other common formats
                                            meal_date_obj = pd.to_datetime(date_str, errors='coerce')
                                    except:
                                        meal_date_obj = pd.to_datetime(date_str, errors='coerce')
                                    
                                    if pd.isna(meal_date_obj):
                                        errors.append(f"Row {idx+1}: Invalid date format '{date_str}'")
                                        skipped += 1
                                        continue
                                    
                                    # Get meal type and normalize
                                    meal_type = str(row[meal_key]).strip().title()
                                    # Map variations to standard types
                                    meal_type_map = {
                                        "Breakfast": "Breakfast",
                                        "Lunch": "Lunch",
                                        "Dinner": "Dinner",
                                        "Snacks": "Snack",
                                        "Snack": "Snack"
                                    }
                                    meal_type = meal_type_map.get(meal_type, meal_type)
                                    
                                    # Parse nutrition values
                                    calories = pd.to_numeric(row[calories_key], errors='coerce')
                                    carbs = pd.to_numeric(row[carbs_key], errors='coerce')
                                    protein = pd.to_numeric(row[protein_key], errors='coerce')
                                    fat = pd.to_numeric(row[fat_key], errors='coerce')
                                    
                                    # Check for valid values
                                    if pd.isna(calories) or pd.isna(carbs) or pd.isna(protein) or pd.isna(fat):
                                        errors.append(f"Row {idx+1}: Missing or invalid nutrition values")
                                        skipped += 1
                                        continue
                                    
                                    # Optional fields
                                    fiber = pd.to_numeric(row[fiber_key], errors='coerce') if fiber_key else None
                                    sugar = pd.to_numeric(row[sugar_key], errors='coerce') if sugar_key else None
                                    
                                    note_value = None
                                    if notes_key:
                                        note_val = row[notes_key]
                                        if pd.notna(note_val):
                                            note_value = str(note_val)
                                    
                                    # Use noon as default time for imported meals
                                    meal_datetime = datetime.combine(meal_date_obj.date(), time(12, 0))
                                    
                                    # Import the meal
                                    st.session_state.agent.import_meal_from_nutrition_data(
                                        meal_type=meal_type,
                                        timestamp=meal_datetime,
                                        calories=float(calories),
                                        carbs=float(carbs),
                                        protein=float(protein),
                                        fat=float(fat),
                                        notes=note_value,
                                        fiber=float(fiber) if fiber is not None and not pd.isna(fiber) else None,
                                        sugar=float(sugar) if sugar is not None and not pd.isna(sugar) else None
                                    )
                                    imported += 1
                                    
                                except Exception as e:
                                    errors.append(f"Row {idx+1}: {str(e)}")
                                    skipped += 1
                        
                        # Mark file as processed and clear cached data
                        st.session_state.processed_files.add(file_id)
                        if import_key in st.session_state:
                            del st.session_state[import_key]
                        
                        # Show results
                        st.success(f"✅ Successfully imported {imported} meals from CSV!")
                        if skipped > 0:
                            st.warning(f"⚠️ Skipped {skipped} rows due to errors")
                            if errors:
                                with st.expander("View errors"):
                                    for error in errors[:10]:  # Show first 10 errors
                                        st.text(error)
                                    if len(errors) > 10:
                                        st.text(f"... and {len(errors) - 10} more errors")
                        
                        st.rerun()
    
    # Add button to clear processed files (for re-importing same file)
    meal_file_ids = [fid for fid in st.session_state.processed_files if not fid.startswith("bs_")]
    if meal_file_ids:
        if st.button("🔄 Clear Meal Import History (to re-import files)", key="clear_meal_imports"):
            # Only clear meal file IDs, keep blood sugar ones
            st.session_state.processed_files = {fid for fid in st.session_state.processed_files if fid.startswith("bs_")}
            # Clear cached import data
            keys_to_remove = [key for key in st.session_state.keys() if key.startswith("meal_import_data_")]
            for key in keys_to_remove:
                del st.session_state[key]
            st.success("Import history cleared. You can now re-import files.")
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
    
    # Check if user is selected
    if st.session_state.user_id is None:
        user_selection_page()
        return
    
    # Check if agent is initialized
    if st.session_state.agent is None:
        st.session_state.agent = SimpleDiabeticAgent(user_id=st.session_state.user_id)
        # Try to load existing profile
        profile = st.session_state.agent.db.get_user_profile(st.session_state.user_id)
        if profile:
            st.session_state.user_profile_set = True
            st.session_state.agent.user_profile = profile
    
    # Show current user in sidebar
    if st.session_state.user_name:
        st.sidebar.markdown(f"**User:** {st.session_state.user_name}")
        if st.sidebar.button("Switch User"):
            st.session_state.user_id = None
            st.session_state.user_name = None
            st.session_state.agent = None
            st.session_state.user_profile_set = False
            st.rerun()
    
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

