"""Project Bite - Interactive Streamlit Test UI & API Dashboard."""

from datetime import datetime, timezone
import json
import uuid
import streamlit as st
import plotly.graph_objects as go

from api_client import BiteAPIClient

# Page configuration
st.set_page_config(
    page_title="Project Bite - Test Dashboard & AI UI",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }
    .meal-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize Session State
if "api_url" not in st.session_state:
    st.session_state["api_url"] = "http://localhost:8000"
if "auth_token" not in st.session_state:
    st.session_state["auth_token"] = ""
if "user_id" not in st.session_state:
    st.session_state["user_id"] = str(uuid.uuid4())
if "user_email" not in st.session_state:
    st.session_state["user_email"] = "developer@example.com"
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "conversation_id" not in st.session_state:
    st.session_state["conversation_id"] = str(uuid.uuid4())
if "analyzed_meal_data" not in st.session_state:
    st.session_state["analyzed_meal_data"] = None

# Initialize API Client
client = BiteAPIClient(
    base_url=st.session_state["api_url"],
    token=st.session_state["auth_token"],
)

# --- SIDEBAR: API CONNECTION & AUTHENTICATION ---
with st.sidebar:
    st.image("https://img.icons8.com/emoji/96/salad-emoji.png", width=64)
    st.title("Project Bite Studio")
    st.caption("AI-Powered Calorie & Macro Tracker UI")
    st.divider()

    st.subheader("⚙️ Server Configuration")
    api_url_input = st.text_input(
        "Backend API Base URL", value=st.session_state["api_url"]
    )
    if api_url_input != st.session_state["api_url"]:
        st.session_state["api_url"] = api_url_input
        client.base_url = api_url_input

    # Health Check Button
    is_healthy, health_info = client.check_health()
    if is_healthy:
        st.success("🟢 API Server: Online", icon="✅")
    else:
        st.error(f"🔴 API Offline: {health_info.get('error', 'Unreachable')}")
        st.info("Make sure FastAPI server is running on http://localhost:8000")

    st.divider()
    st.subheader("🔐 User Authentication")

    with st.expander(
        "🔑 Generate Dev Token", expanded=not bool(st.session_state["auth_token"])
    ):
        email_in = st.text_input("Email", value=st.session_state["user_email"])
        user_id_in = st.text_input("User UUID", value=st.session_state["user_id"])

        if st.button(
            "Generate & Authenticate", use_container_width=True, type="primary"
        ):
            try:
                token_resp = client.generate_dev_token(
                    email=email_in, user_id=user_id_in
                )
                st.session_state["auth_token"] = token_resp["access_token"]
                st.session_state["user_email"] = token_resp.get("email", email_in)
                st.session_state["user_id"] = str(token_resp.get("user_id", user_id_in))
                st.success("Authenticated successfully!")
                st.rerun()
            except Exception as err:
                st.error(f"Token generation failed: {err}")

    if st.session_state["auth_token"]:
        st.success(f"👤 Logged in as: {st.session_state['user_email']}")
        if st.button("Logout", use_container_width=True):
            st.session_state["auth_token"] = ""
            st.rerun()
    else:
        st.warning("Please generate a dev token to test authenticated APIs.")


# --- MAIN HEADER ---
st.markdown(
    '<div class="main-header">🥗 Project Bite Dashboard & Test UI</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-header">Test vision meal logging, real-time AI nutritionist chat, daily macro analytics, and user profile management.</div>',
    unsafe_allow_html=True,
)

# Navigation Tabs
tab_dashboard, tab_meal_vision, tab_chat, tab_profile = st.tabs(
    [
        "📊 Daily Dashboard",
        "📸 Log Meal (Vision AI)",
        "💬 AI Nutritionist Chat",
        "👤 Profile & Goals",
    ]
)


# ==========================================
# TAB 1: DAILY DASHBOARD
# ==========================================
with tab_dashboard:
    col_date, col_refresh = st.columns([3, 1])
    with col_date:
        selected_date = st.date_input(
            "Select Target Date", value=datetime.now(timezone.utc).date()
        )
    with col_refresh:
        st.write("")
        st.write("")
        if st.button("🔄 Refresh Dashboard", use_container_width=True):
            st.rerun()

    date_str = selected_date.strftime("%Y-%m-%d")

    if not st.session_state["auth_token"]:
        st.warning(
            "⚠️ Please authenticate via the sidebar to view your personalized dashboard."
        )
    else:
        try:
            dashboard_data = client.get_daily_dashboard(target_date=date_str)

            # Key Macro Metrics
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)

            cal_consumed = dashboard_data.get("consumed_calories", 0.0)
            cal_target = dashboard_data.get("target_calories", 2000.0)
            cal_rem = dashboard_data.get("remaining_calories", 0.0)

            m_col1.metric(
                "🔥 Calories",
                f"{cal_consumed} / {cal_target} kcal",
                delta=f"-{cal_rem} kcal remaining",
                delta_color="inverse",
            )

            prot = dashboard_data.get("protein", {})
            m_col2.metric(
                "🥩 Protein",
                f"{prot.get('consumed', 0.0)} / {prot.get('target', 150.0)} g",
                delta=f"-{prot.get('remaining', 0.0)} g remaining",
            )

            carbs = dashboard_data.get("carbs", {})
            m_col3.metric(
                "🍞 Carbs",
                f"{carbs.get('consumed', 0.0)} / {carbs.get('target', 200.0)} g",
                delta=f"-{carbs.get('remaining', 0.0)} g remaining",
            )

            fat = dashboard_data.get("fat", {})
            m_col4.metric(
                "🥑 Fat",
                f"{fat.get('consumed', 0.0)} / {fat.get('target', 65.0)} g",
                delta=f"-{fat.get('remaining', 0.0)} g remaining",
            )

            st.divider()

            # Plotly Macro Progress Chart
            col_chart, col_micro = st.columns([3, 2])

            with col_chart:
                st.subheader("📈 Daily Macronutrient Target Progress")
                macros = ["Calories (kcal)", "Protein (g)", "Carbs (g)", "Fat (g)"]
                consumed_vals = [
                    cal_consumed,
                    prot.get("consumed", 0.0),
                    carbs.get("consumed", 0.0),
                    fat.get("consumed", 0.0),
                ]
                target_vals = [
                    cal_target,
                    prot.get("target", 150.0),
                    carbs.get("target", 200.0),
                    fat.get("target", 65.0),
                ]

                fig = go.Figure()
                fig.add_trace(
                    go.Bar(
                        name="Consumed",
                        x=macros,
                        y=consumed_vals,
                        marker_color="#10B981",
                    )
                )
                fig.add_trace(
                    go.Bar(
                        name="Target Goal",
                        x=macros,
                        y=target_vals,
                        marker_color="#94A3B8",
                    )
                )
                fig.update_layout(
                    barmode="group", height=320, margin=dict(l=20, r=20, t=20, b=20)
                )
                st.plotly_chart(fig, use_container_width=True)

            with col_micro:
                st.subheader("🧪 Micronutrients Aggregate")
                top_micros = dashboard_data.get("top_micronutrients", {})
                if top_micros:
                    for nut, val in list(top_micros.items())[:8]:
                        st.write(f"• **{nut}**: {val}")
                else:
                    st.info("No detailed micronutrient data logged for this date yet.")

            st.divider()

            # Logged Meals Cards Timeline
            st.subheader(f"🍽️ Logged Meals for {date_str}")
            meals_list = dashboard_data.get("meals", [])

            if not meals_list:
                st.info(
                    "No meals logged yet for this date. Go to the 'Log Meal' tab to record your first meal!"
                )
            else:
                for idx, meal in enumerate(meals_list):
                    with st.container():
                        c_img, c_info = st.columns([1, 4])
                        with c_img:
                            img_url = meal.get("image_url")
                            if img_url:
                                st.image(img_url, width=120)
                            else:
                                st.markdown("🥘 *No Image*")
                        with c_info:
                            m_type = str(meal.get("meal_type", "meal")).upper()
                            caption = (
                                meal.get("user_caption") or "No description provided"
                            )
                            logged_at = meal.get("logged_at", "")

                            st.markdown(f"### {m_type} - {caption}")
                            st.write(
                                f"🔥 **{meal.get('calories', 0)} kcal** | "
                                f"🥩 Protein: **{meal.get('protein_g', 0)}g** | "
                                f"🍞 Carbs: **{meal.get('carbs_g', 0)}g** | "
                                f"🥑 Fat: **{meal.get('fat_g', 0)}g**"
                            )
                            st.caption(f"Logged at: {logged_at}")
                        st.divider()

        except Exception as e:
            st.error(f"Failed to fetch daily dashboard: {e}")


# ==========================================
# TAB 2: LOG MEAL (VISION AI)
# ==========================================
with tab_meal_vision:
    st.subheader("📸 Upload Meal Photo or Enter Image URL")

    col_input_type, col_meal_type = st.columns([2, 1])
    with col_input_type:
        input_mode = st.radio(
            "Image Source", ["File Upload", "Image URL"], horizontal=True
        )
    with col_meal_type:
        meal_type_val = st.selectbox(
            "Meal Category", ["breakfast", "lunch", "dinner", "snack"], index=1
        )

    user_caption_val = st.text_input(
        "Meal Description / User Caption (Optional)",
        placeholder="e.g. Grilled salmon salad with olive oil and avocado",
    )

    image_bytes_upload = None
    image_url_upload = None

    if input_mode == "File Upload":
        uploaded_file = st.file_uploader(
            "Choose a food image (JPG, PNG)", type=["jpg", "jpeg", "png"]
        )
        if uploaded_file:
            image_bytes_upload = uploaded_file.read()
            st.image(image_bytes_upload, caption="Uploaded Image Preview", width=300)
    else:
        image_url_upload = st.text_input(
            "Enter Public Image URL",
            placeholder="https://images.unsplash.com/photo-1546069901-ba9599a7e63c",
        )
        if image_url_upload:
            st.image(image_url_upload, caption="Image URL Preview", width=300)

    if st.button(
        "🚀 Analyze Meal with Vision AI", type="primary", use_container_width=True
    ):
        if not st.session_state["auth_token"]:
            st.error(
                "Please authenticate in sidebar before running meal vision analysis."
            )
        elif not image_bytes_upload and not image_url_upload:
            st.warning("Please upload an image file or provide an image URL.")
        else:
            with st.spinner("🔍 Running LangGraph Vision & USDA Food Matcher..."):
                try:
                    analysis_res = client.analyze_meal(
                        image_bytes=image_bytes_upload,
                        image_url=image_url_upload,
                        user_caption=user_caption_val,
                        meal_type=meal_type_val,
                    )
                    st.session_state["analyzed_meal_data"] = {
                        "analysis": analysis_res,
                        "image_url": image_url_upload,
                        "user_caption": user_caption_val,
                        "meal_type": meal_type_val,
                    }
                    st.success("Meal analysis completed successfully!")
                except Exception as err:
                    st.error(f"Vision analysis failed: {err}")

    # Display Analysis Results & Confirmation Step
    if st.session_state["analyzed_meal_data"]:
        stored = st.session_state["analyzed_meal_data"]
        res = stored["analysis"]

        st.divider()
        st.subheader("📋 Analyzed Food Items & Nutrition Breakdown")

        conf = res.get("confidence_score", 1.0)
        st.progress(
            min(1.0, conf), text=f"AI Vision Confidence Score: {round(conf * 100, 1)}%"
        )

        st.markdown(
            f"**Total Summary**: 🔥 **{res.get('total_calories', 0)} kcal** | "
            f"🥩 Protein: **{res.get('total_protein_g', 0)}g** | "
            f"🍞 Carbs: **{res.get('total_carbs_g', 0)}g** | "
            f"🥑 Fat: **{res.get('total_fat_g', 0)}g**"
        )

        items = res.get("detected_items", [])
        if items:
            st.write("Review detected food items:")
            for idx, item in enumerate(items):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                c1.write(
                    f"• **{item.get('food_name')}** (FDC ID: {item.get('fdc_id') or 'N/A'})"
                )
                c2.write(f"Weight: {item.get('gram_weight')}g")
                c3.write(f"Calories: {item.get('calories')} kcal")
                c4.write(
                    f"P/C/F: {item.get('protein_g')}g / {item.get('carbs_g')}g / {item.get('fat_g')}g"
                )

        col_save, col_cancel = st.columns([2, 1])
        with col_save:
            if st.button(
                "💾 Confirm & Log Meal to Database",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Persisting meal log to database..."):
                    try:
                        confirm_res = client.confirm_meal(
                            items=items,
                            meal_type=stored["meal_type"],
                            user_caption=stored["user_caption"],
                            image_url=stored["image_url"],
                        )
                        st.success(
                            f"Meal logged successfully! Meal ID: {confirm_res.get('meal_id')}"
                        )
                        st.session_state["analyzed_meal_data"] = None
                    except Exception as err:
                        st.error(f"Failed to save meal: {err}")
        with col_cancel:
            if st.button("Discard Analysis", use_container_width=True):
                st.session_state["analyzed_meal_data"] = None
                st.rerun()


# ==========================================
# TAB 3: AI NUTRITIONIST CHAT
# ==========================================
with tab_chat:
    st.subheader("💬 AI Nutritionist Chat Assistant")
    st.caption(
        "Ask questions about your diet, request meal suggestions, or get personalized fitness advice."
    )

    col_clear, _ = st.columns([1, 4])
    with col_clear:
        if st.button("🧹 Clear Chat History"):
            st.session_state["chat_history"] = []
            st.session_state["conversation_id"] = str(uuid.uuid4())
            st.rerun()

    # Render Chat History
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input(
        "Type your message here (e.g., 'What can I eat for high-protein dinner?')"
    )

    if user_input:
        if not st.session_state["auth_token"]:
            st.error("Please authenticate via sidebar before starting chat.")
        else:
            # Append User Message to session state
            st.session_state["chat_history"].append(
                {"role": "user", "content": user_input}
            )

            # Display user message immediately
            with st.chat_message("user"):
                st.markdown(user_input)

            # Stream Assistant Response via SSE
            with st.chat_message("assistant"):
                status_placeholder = st.empty()
                response_placeholder = st.empty()
                full_response = ""

                try:
                    for chunk in client.stream_chat(
                        message=user_input,
                        conversation_id=st.session_state["conversation_id"],
                    ):
                        event_type = chunk.get("event")
                        event_data = chunk.get("data", {})

                        if event_type in (
                            "status",
                            "action_status",
                            "processing_prompt",
                        ):
                            if isinstance(event_data, dict):
                                status_msg = (
                                    event_data.get("message")
                                    or event_data.get("content")
                                    or "Processing request..."
                                )
                            else:
                                status_msg = str(event_data)
                            status_placeholder.info(f"⏳ {status_msg}")

                        elif event_type in ("message", "token"):
                            if isinstance(event_data, dict):
                                token = event_data.get("content", "")
                            else:
                                token = str(event_data)
                            if token:
                                full_response += token
                                response_placeholder.markdown(full_response + "▌")

                        elif event_type == "done":
                            status_placeholder.empty()
                            response_placeholder.markdown(full_response)

                        elif event_type == "error":
                            if isinstance(event_data, dict):
                                err_msg = (
                                    event_data.get("error")
                                    or event_data.get("content")
                                    or "Streaming error"
                                )
                            else:
                                err_msg = str(event_data)
                            st.error(f"Chat streaming error: {err_msg}")

                    status_placeholder.empty()
                    if full_response:
                        response_placeholder.markdown(full_response)
                        st.session_state["chat_history"].append(
                            {"role": "assistant", "content": full_response}
                        )
                    else:
                        st.warning("No text tokens were returned by assistant.")

                except Exception as err:
                    st.error(f"Chat communication error: {err}")


# ==========================================
# TAB 4: PROFILE & GOALS
# ==========================================
with tab_profile:
    st.subheader("👤 User Profile & Macro Targets")

    if not st.session_state["auth_token"]:
        st.warning("Please authenticate via sidebar to view and update your profile.")
    else:
        try:
            profile = client.get_profile()

            with st.form("profile_form"):
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    disp_name = st.text_input(
                        "Display Name", value=profile.get("display_name") or ""
                    )
                    height_cm = st.number_input(
                        "Height (cm)",
                        value=float(profile.get("height_cm") or 175.0),
                        min_value=50.0,
                        max_value=250.0,
                    )
                    weight_kg = st.number_input(
                        "Weight (kg)",
                        value=float(profile.get("weight_kg") or 70.0),
                        min_value=30.0,
                        max_value=300.0,
                    )
                    age_val = st.number_input(
                        "Age",
                        value=int(profile.get("age") or 25),
                        min_value=10,
                        max_value=120,
                    )

                with col_p2:
                    gender_val = st.selectbox(
                        "Gender",
                        ["male", "female", "other"],
                        index=0 if profile.get("gender") == "male" else 1,
                    )
                    activity_val = st.selectbox(
                        "Activity Level",
                        ["sedentary", "light", "moderate", "active", "extra"],
                        index=[
                            "sedentary",
                            "light",
                            "moderate",
                            "active",
                            "extra",
                        ].index(profile.get("activity_level", "moderate")),
                    )
                    goal_val = st.selectbox(
                        "Primary Goal",
                        ["weight_loss", "maintenance", "muscle_gain"],
                        index=["weight_loss", "maintenance", "muscle_gain"].index(
                            profile.get("primary_goal", "maintenance")
                        ),
                    )

                st.divider()
                st.subheader("🎯 Daily Target Macronutrients")
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)

                with col_m1:
                    target_cal = st.number_input(
                        "Target Calories (kcal)",
                        value=float(profile.get("target_calories") or 2000.0),
                    )
                with col_m2:
                    target_prot = st.number_input(
                        "Target Protein (g)",
                        value=float(profile.get("target_protein_g") or 150.0),
                    )
                with col_m3:
                    target_carb = st.number_input(
                        "Target Carbs (g)",
                        value=float(profile.get("target_carbs_g") or 200.0),
                    )
                with col_m4:
                    target_fat = st.number_input(
                        "Target Fat (g)",
                        value=float(profile.get("target_fat_g") or 65.0),
                    )

                submit_profile = st.form_submit_button(
                    "💾 Save Profile Changes", type="primary", use_container_width=True
                )

                if submit_profile:
                    update_payload = {
                        "display_name": disp_name,
                        "height_cm": height_cm,
                        "weight_kg": weight_kg,
                        "age": age_val,
                        "gender": gender_val,
                        "activity_level": activity_val,
                        "primary_goal": goal_val,
                        "target_calories": target_cal,
                        "target_protein_g": target_prot,
                        "target_carbs_g": target_carb,
                        "target_fat_g": target_fat,
                    }
                    try:
                        updated_resp = client.update_profile(update_payload)
                        st.success("Profile successfully updated!")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Failed to update profile: {err}")

            # Calculated BMR / TDEE information
            if profile.get("bmr") and profile.get("tdee"):
                st.info(
                    f"💡 Calculated BMR (Basal Metabolic Rate): **{profile['bmr']} kcal/day** | TDEE (Total Daily Energy Expenditure): **{profile['tdee']} kcal/day**"
                )

        except Exception as e:
            st.error(f"Error loading user profile: {e}")
