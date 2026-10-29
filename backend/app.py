"""
RoadWatch AI - Open-Source Municipal Road Damage Intelligence Platform
Built for AI Hackathons. Powered by local Ollama vision AI, Streamlit, and SQLite.
"""

import os
import sys
import types
import uuid
from datetime import datetime
from PIL import Image

# Ensure graceful operation even if OS security policy blocks pandas C-extensions
try:
    import pandas as pd
    _has_real_pandas = True
except Exception:
    pd = types.ModuleType("pandas")
    pd.__path__ = []

    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass

    pd.DataFrame = _Dummy
    pd.Series = _Dummy
    pd.Index = _Dummy

    api_mod = types.ModuleType("pandas.api")
    api_mod.__path__ = []
    types_mod = types.ModuleType("pandas.api.types")
    def _infer_dtype(val, skipna=True):
        return "string"
    types_mod.infer_dtype = _infer_dtype

    ext_mod = types.ModuleType("pandas.api.extensions")
    ext_mod.ExtensionArray = _Dummy

    api_mod.types = types_mod
    api_mod.extensions = ext_mod
    pd.api = api_mod

    sys.modules["pandas"] = pd
    sys.modules["pandas.api"] = api_mod
    sys.modules["pandas.api.types"] = types_mod
    sys.modules["pandas.api.extensions"] = ext_mod
    _has_real_pandas = False

import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

try:
    from streamlit_geolocation import streamlit_geolocation
except ImportError:
    streamlit_geolocation = None

import ai
import db

# ---------------------------------------------------------
# Page Configuration & Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="RoadWatch AI - Road Damage Intelligence",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database
db.init_db()

# Auto-seed if database is empty (e.g. on fresh cloud deployments like Streamlit Cloud)
try:
    if db.get_report_counts()["total"] == 0:
        import seed
        seed.seed_database()
except Exception:
    pass

# Uploads directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Admin authentication password
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# Custom CSS for polished, mobile-friendly aesthetics
st.markdown(
    """
    <style>
    /* Main container and headings */
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    /* Severity Badges */
    .badge-low {
        background-color: #28a745;
        color: white;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.85rem;
        display: inline-block;
    }
    .badge-medium {
        background-color: #fd7e14;
        color: white;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.85rem;
        display: inline-block;
    }
    .badge-high {
        background-color: #dc3545;
        color: white;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.85rem;
        display: inline-block;
    }
    .badge-status {
        background-color: #0284c7;
        color: white;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
    .badge-status-fixed {
        background-color: #059669;
        color: white;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
    /* Metric Cards */
    .kpi-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .kpi-val {
        font-size: 2rem;
        font-weight: 800;
        color: #0F172A;
    }
    .kpi-lbl {
        font-size: 0.85rem;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    /* Analysis Result Card */
    .analysis-box {
        background: #F8FAFC;
        border-left: 5px solid #2563EB;
        border-radius: 8px;
        padding: 16px;
        margin-top: 15px;
        margin-bottom: 15px;
        border: 1px solid #E2E8F0;
        border-left-width: 5px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_severity_badge_html(severity: str) -> str:
    """Returns colored HTML badge for severity."""
    sev = severity.capitalize()
    if sev == "High":
        return f'<span class="badge-high">HIGH SEVERITY</span>'
    elif sev == "Medium":
        return f'<span class="badge-medium">MEDIUM SEVERITY</span>'
    return f'<span class="badge-low">LOW SEVERITY</span>'


def get_status_badge_html(status: str) -> str:
    """Returns colored HTML badge for status."""
    if status == "Fixed":
        return f'<span class="badge-status-fixed">✓ FIXED</span>'
    return f'<span class="badge-status">{status.upper()}</span>'


# ---------------------------------------------------------
# Session State Defaults
# ---------------------------------------------------------
if "selected_lat" not in st.session_state:
    st.session_state.selected_lat = 20.2961  # Bhubaneswar default
if "selected_lng" not in st.session_state:
    st.session_state.selected_lng = 85.8245
if "current_analysis" not in st.session_state:
    st.session_state.current_analysis = None
if "current_image_bytes" not in st.session_state:
    st.session_state.current_image_bytes = None
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "force_mock_ai" not in st.session_state:
    st.session_state.force_mock_ai = False

# ---------------------------------------------------------
# Sidebar: System Health & Ollama Status
# ---------------------------------------------------------
with st.sidebar:
    st.title("🛣️ RoadWatch AI")
    st.caption("Open-Source Road Damage Inspection & Municipal Action Platform")

    st.markdown("---")
    st.subheader("🤖 AI Engine Health")

    # Perform Ollama status check
    ollama_stat = ai.check_ollama_status()
    if ollama_stat["online"]:
        if ollama_stat["model_installed"]:
            st.success(f"🟢 Ollama Online: `{ai.OLLAMA_MODEL}`")
        else:
            st.warning(f"🟡 Ollama Online, but model `{ai.OLLAMA_MODEL}` missing!")
            st.code(ollama_stat["fix_command"], language="bash")
    else:
        st.error("🔴 Ollama Server Offline")
        st.info("Start Ollama locally with:")
        st.code("ollama serve", language="bash")
        if ollama_stat["fix_command"] and "pull" in ollama_stat["fix_command"]:
            st.code(ollama_stat["fix_command"], language="bash")

    # Hackathon Demo / Offline Toggle
    st.markdown("---")
    st.session_state.force_mock_ai = st.checkbox(
        "Offline Demo Mode (Fallback)",
        value=st.session_state.force_mock_ai,
        help="Simulates Ollama vision inspection when running offline without a local GPU.",
    )

    # Quick Stats in Sidebar
    counts = db.get_report_counts()
    st.markdown("---")
    st.subheader("📊 Network Pulse")
    col_sb1, col_sb2 = st.columns(2)
    with col_sb1:
        st.metric("Total Reports", counts["total"])
        st.metric("Fixed Repairs", counts["fixed"])
    with col_sb2:
        st.metric("Open Hazards", counts["open"])
        st.metric("High Severity", counts["high_severity"])

    st.markdown("---")
    st.caption("Built with Streamlit • Ollama • SQLite • Folium")


# ---------------------------------------------------------
# Header Banner
# ---------------------------------------------------------
st.markdown('<div class="main-title">RoadWatch AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Empowering citizens and municipal engineers with local open-source vision AI to detect, report, and repair road hazards.</div>',
    unsafe_allow_html=True,
)

# Startup Warning Banner if Ollama is offline and mock mode isn't explicitly active
if not ollama_stat["online"] and not st.session_state.force_mock_ai:
    st.warning(
        f"⚠️ **Ollama is not running at {ai.OLLAMA_HOST}.** Start it with `ollama serve` and ensure the vision model is installed with `ollama pull {ai.OLLAMA_MODEL}`. (Tip: You can enable 'Offline Demo Mode' in the sidebar for offline testing)."
    )
elif ollama_stat["online"] and not ollama_stat["model_installed"] and not st.session_state.force_mock_ai:
    st.warning(
        f"⚠️ **Model '{ai.OLLAMA_MODEL}' not found in Ollama.** Run this command in your terminal: `ollama pull {ai.OLLAMA_MODEL}`"
    )

# ---------------------------------------------------------
# Tabs Navigation
# ---------------------------------------------------------
tab_report, tab_map, tab_dashboard = st.tabs([
    "📷 Report Damage",
    "🗺️ Public Map",
    "🛡️ Authority Dashboard",
])


# =========================================================
# TAB 1: REPORT ROAD DAMAGE
# =========================================================
with tab_report:
    st.markdown("### 📷 Step 1: Capture Road Surface Photo")
    st.write("Take a direct photo of the damaged pavement or upload an existing photo.")

    col_cam, col_upload = st.columns(2)
    image_source = None

    with col_cam:
        cam_photo = st.camera_input("Open Camera (Mobile / Laptop)")
        if cam_photo is not None:
            image_source = cam_photo

    with col_upload:
        uploaded_file = st.file_uploader(
            "Or upload from photo gallery",
            type=["jpg", "jpeg", "png", "webp"],
            help="Accepted formats: JPG, PNG, WEBP",
        )
        if uploaded_file is not None and cam_photo is None:
            image_source = uploaded_file

    # Process and preview chosen image
    if image_source is not None:
        try:
            image_bytes = image_source.getvalue()
            # Verify valid image
            pil_img = Image.open(image_source)
            st.session_state.current_image_bytes = image_bytes

            st.image(
                pil_img,
                caption="Captured Road Surface (Preview)",
                use_container_width=True,
            )

            # AI Analysis Trigger Button
            st.markdown("### 🤖 Step 2: AI Damage Analysis")
            col_ai_btn, col_ai_info = st.columns([1, 2])
            with col_ai_btn:
                analyze_btn = st.button("🔍 Analyze Road with Ollama AI", type="primary", use_container_width=True)

            if analyze_btn:
                with st.spinner("🤖 RoadWatch AI is analyzing pavement surface with local Ollama..."):
                    try:
                        analysis = ai.analyze_road_image(
                            image_bytes,
                            allow_mock_fallback=st.session_state.force_mock_ai,
                        )
                        st.session_state.current_analysis = analysis
                        st.success("Analysis complete!")
                    except Exception as exc:
                        st.error(f"AI Inspection Error: {str(exc)}")
                        st.info(
                            f"Make sure Ollama is running (`ollama serve`) and the model is pulled (`ollama pull {ai.OLLAMA_MODEL}`)."
                        )

        except Exception as err:
            st.error(f"Invalid image format: {err}")

    # Display Analysis Results
    analysis = st.session_state.current_analysis
    if analysis:
        st.markdown("---")
        st.subheader("📋 AI Inspection Findings")

        if not analysis["damage_detected"]:
            st.info("✅ **No Road Damage Detected**: The pavement surface appears intact and free of significant defects.")
        else:
            # Cards and Badges layout
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown("**Damage Severity:**")
                st.markdown(get_severity_badge_html(analysis["severity"]), unsafe_allow_html=True)
            with c2:
                st.metric("Damage Type", analysis["damage_type"].title())
            with c3:
                st.metric("Potholes Count", analysis["pothole_count"])
            with c4:
                st.metric("Model Confidence", f"{int(analysis['confidence'] * 100)}%")

            # Damage share progress bar
            st.markdown(f"**Road Surface Damage Extent: {analysis['damage_percent']}%**")
            st.progress(float(analysis["damage_percent"]) / 100.0)

            # Summary and Repair recommendation
            st.markdown(
                f"""
                <div class="analysis-box">
                    <p style="margin-bottom: 6px;"><strong>AI Inspection Summary:</strong> {analysis['summary']}</p>
                    <p style="margin-bottom: 0;"><strong>Recommended Repair Action:</strong> {analysis['recommended_action']}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Step 3: Location Selection
    st.markdown("---")
    st.markdown("### 📍 Step 3: Road Location (GPS or Pin Drop)")

    loc_col1, loc_col2 = st.columns([1, 1])

    with loc_col1:
        st.write("**Option A: Browser GPS Detection**")
        if streamlit_geolocation:
            geo_data = streamlit_geolocation()
            if geo_data and geo_data.get("latitude") is not None:
                st.session_state.selected_lat = round(float(geo_data["latitude"]), 6)
                st.session_state.selected_lng = round(float(geo_data["longitude"]), 6)
                st.success(f"GPS locked: ({st.session_state.selected_lat}, {st.session_state.selected_lng})")
        else:
            st.caption("Geolocation component ready. Click below or pick on the map.")

        st.write("**Option B: Coordinate Inputs / Presets**")
        preset_cols = st.columns(3)
        with preset_cols[0]:
            if st.button("📍 KIIT Patia", use_container_width=True):
                st.session_state.selected_lat, st.session_state.selected_lng = 20.3540, 85.8175
        with preset_cols[1]:
            if st.button("📍 Janpath", use_container_width=True):
                st.session_state.selected_lat, st.session_state.selected_lng = 20.2885, 85.8420
        with preset_cols[2]:
            if st.button("📍 Khandagiri", use_container_width=True):
                st.session_state.selected_lat, st.session_state.selected_lng = 20.2598, 85.7865

        cur_lat = st.number_input("Latitude", value=float(st.session_state.selected_lat), format="%.6f")
        cur_lng = st.number_input("Longitude", value=float(st.session_state.selected_lng), format="%.6f")
        st.session_state.selected_lat = cur_lat
        st.session_state.selected_lng = cur_lng

    with loc_col2:
        st.write("**Click on map to drop / move pin:**")
        # Map picker
        picker_map = folium.Map(
            location=[st.session_state.selected_lat, st.session_state.selected_lng],
            zoom_start=13,
        )
        folium.Marker(
            [st.session_state.selected_lat, st.session_state.selected_lng],
            tooltip="Selected Incident Location",
            icon=folium.Icon(color="red", icon="crosshairs", prefix="fa"),
        ).add_to(picker_map)

        picker_data = st_folium(
            picker_map,
            height=280,
            width=None,
            key="location_picker_map",
            returned_objects=["last_clicked"],
        )
        if picker_data and picker_data.get("last_clicked"):
            clicked = picker_data["last_clicked"]
            if clicked.get("lat") and clicked.get("lng"):
                st.session_state.selected_lat = round(float(clicked["lat"]), 6)
                st.session_state.selected_lng = round(float(clicked["lng"]), 6)
                st.rerun()

    # Step 4: Submission
    st.markdown("---")
    st.markdown("### 🚀 Step 4: Submit Road Damage Report")

    user_notes = st.text_area(
        "Citizen Notes / Landmark description (optional)",
        placeholder="e.g. Near traffic signal, left lane heading towards airport...",
    )

    can_submit = True
    submission_warning = None

    if st.session_state.current_image_bytes is None:
        can_submit = False
        submission_warning = "Please take or upload a road damage photo first."
    elif analysis is None:
        can_submit = False
        submission_warning = "Please run the AI Damage Analysis before submitting."
    elif not analysis.get("damage_detected", False):
        can_submit = False
        submission_warning = "Submission is disabled: AI detected no damage on this road surface."

    if submission_warning:
        st.info(f"ℹ️ {submission_warning}")

    submit_button = st.button(
        "🚀 Submit Incident Report to Municipal Authorities",
        type="primary",
        disabled=not can_submit,
        use_container_width=True,
    )

    if submit_button and can_submit:
        # Save image file to uploads/
        img_id = str(uuid.uuid4())[:8]
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{img_id}.jpg"
        file_path = os.path.join(UPLOAD_DIR, filename)

        with open(file_path, "wb") as f:
            f.write(st.session_state.current_image_bytes)

        # Insert into SQLite
        new_id = db.insert_report(
            image_path=file_path,
            latitude=st.session_state.selected_lat,
            longitude=st.session_state.selected_lng,
            damage_type=analysis["damage_type"],
            pothole_count=analysis["pothole_count"],
            damage_percent=analysis["damage_percent"],
            severity=analysis["severity"],
            confidence=analysis["confidence"],
            summary=analysis["summary"],
            recommended_action=analysis["recommended_action"],
            user_description=user_notes,
            status="Reported",
        )

        st.success(f"🎉 Report #{new_id} submitted successfully! It has been dispatched to the Municipal Public Map and Authority Dashboard.")
        st.balloons()
        # Reset current analysis state
        st.session_state.current_analysis = None
        st.session_state.current_image_bytes = None


# =========================================================
# TAB 2: PUBLIC DAMAGE MAP
# =========================================================
with tab_map:
    st.markdown("### 🗺️ Live Municipal Road Damage Map")
    st.write("Transparent citizen map of reported road defects with AI severity classification.")

    all_reports = db.get_all_reports()

    # Filter Bar
    filt_col1, filt_col2, filt_col3 = st.columns([1, 1, 2])
    with filt_col1:
        map_status_filter = st.selectbox(
            "Filter by Status",
            options=["All", "Reported", "Assigned", "In Progress", "Fixed"],
            index=0,
            key="map_filter_status",
        )
    with filt_col2:
        map_sev_filter = st.selectbox(
            "Filter by Severity",
            options=["All", "High", "Medium", "Low"],
            index=0,
            key="map_filter_sev",
        )
    with filt_col3:
        st.markdown(
            """
            <div style="padding-top: 28px;">
                <span style="color:#dc3545; font-weight:bold;">● Red: High</span> &nbsp;|&nbsp;
                <span style="color:#fd7e14; font-weight:bold;">● Orange: Medium</span> &nbsp;|&nbsp;
                <span style="color:#28a745; font-weight:bold;">● Green: Low</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Apply filters
    filtered_map_reports = [
        r for r in all_reports
        if (map_status_filter == "All" or r["status"] == map_status_filter)
        and (map_sev_filter == "All" or r["severity"] == map_sev_filter)
    ]

    st.write(f"Showing **{len(filtered_map_reports)}** of **{len(all_reports)}** incident reports.")

    # Calculate map center
    if filtered_map_reports:
        center_lat = sum(r["latitude"] for r in filtered_map_reports) / len(filtered_map_reports)
        center_lng = sum(r["longitude"] for r in filtered_map_reports) / len(filtered_map_reports)
    else:
        center_lat, center_lng = 20.2961, 85.8245

    # Create Folium Map
    m = folium.Map(location=[center_lat, center_lng], zoom_start=12, tiles="OpenStreetMap")
    marker_cluster = MarkerCluster(name="Road Hazards").add_to(m)

    for rep in filtered_map_reports:
        # Determine color
        sev = rep["severity"].capitalize()
        color = "red" if sev == "High" else ("orange" if sev == "Medium" else "green")

        # Prepare popup HTML
        popup_html = f"""
        <div style="width: 260px; font-family: sans-serif; font-size: 13px;">
            <div style="margin-bottom: 6px;">
                <span style="background-color: {'#dc3545' if sev == 'High' else ('#fd7e14' if sev == 'Medium' else '#28a745')};
                             color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">
                    {sev.upper()} SEVERITY
                </span>
                <span style="background-color: #0284c7; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">
                    {rep['status']}
                </span>
            </div>
            <h4 style="margin: 4px 0 6px 0; color: #1e293b;">Report #{rep['id']}: {rep['damage_type'].title()}</h4>
            <p style="margin: 2px 0;"><strong>Damage Extent:</strong> {rep['damage_percent']}%</p>
            <p style="margin: 2px 0;"><strong>Potholes:</strong> {rep['pothole_count']}</p>
            <p style="margin: 2px 0;"><strong>Reported:</strong> {rep['created_at']}</p>
            <p style="margin: 6px 0 2px 0; color: #334155;"><strong>AI Summary:</strong> {rep['summary']}</p>
            <p style="margin: 4px 0 2px 0; color: #0f766e; font-style: italic;"><strong>Repair:</strong> {rep['recommended_action']}</p>
        </div>
        """

        folium.Marker(
            location=[rep["latitude"], rep["longitude"]],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"Report #{rep['id']} - {rep['damage_type'].title()} ({rep['severity']})",
            icon=folium.Icon(color=color, icon="exclamation-sign"),
        ).add_to(marker_cluster)

    # Render folium map
    st_folium(m, width=None, height=520, returned_objects=[])

    # Recent Feed Table beneath map
    st.markdown("#### 📋 Recent Reports Log")
    if filtered_map_reports:
        display_rows = [
            {
                "ID": r["id"],
                "Timestamp": r["created_at"],
                "Damage Type": r["damage_type"].title(),
                "Severity": r["severity"],
                "Damage %": f"{r['damage_percent']}%",
                "Potholes": r["pothole_count"],
                "Status": r["status"],
                "AI Summary": r["summary"],
            }
            for r in filtered_map_reports
        ]
        if _has_real_pandas:
            st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)
        else:
            st.dataframe(display_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No reports match current filters.")



# =========================================================
# TAB 3: AUTHORITY DASHBOARD
# =========================================================
with tab_dashboard:
    st.markdown("### 🛡️ Municipal Works & Road Maintenance Authority")
    st.caption("Authorized engineering portal for reviewing AI damage surveys, assigning crews, and marking repairs.")

    # Password Protection Check
    if not st.session_state.admin_logged_in:
        auth_col1, auth_col2 = st.columns([1, 1])
        with auth_col1:
            st.markdown("#### 🔒 Authority Authentication")
            entered_pwd = st.text_input(
                "Enter Authority Access Password",
                type="password",
                help="Default password is configured via ADMIN_PASSWORD (default: admin123)",
            )
            login_btn = st.button("Unlock Authority Dashboard", type="primary")

            if login_btn:
                if entered_pwd == ADMIN_PASSWORD:
                    st.session_state.admin_logged_in = True
                    st.success("Authenticated successfully!")
                    st.rerun()
                else:
                    st.error("Incorrect password. Please verify your credentials.")
        with auth_col2:
            st.info(
                """
                **Departmental Access Only**
                - Review citizen road defect submissions
                - Inspect AI visual defect classifications
                - Dispatch road maintenance contractors
                - Update status to *Assigned*, *In Progress*, or *Fixed*
                """
            )
    else:
        # Logout button
        col_hdr1, col_hdr2 = st.columns([4, 1])
        with col_hdr2:
            if st.button("🚪 Logout of Authority", use_container_width=True):
                st.session_state.admin_logged_in = False
                st.rerun()

        # Summary KPIs
        counts = db.get_report_counts()
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-val">{counts['total']}</div>
                    <div class="kpi-lbl">Total Incidents</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with kpi2:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-val" style="color: #0284c7;">{counts['open']}</div>
                    <div class="kpi-lbl">Active / Open</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with kpi3:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-val" style="color: #dc3545;">{counts['high_severity']}</div>
                    <div class="kpi-lbl">High Severity Hazards</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with kpi4:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-val" style="color: #059669;">{counts['fixed']}</div>
                    <div class="kpi-lbl">Repairs Completed</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Visual Analytics
        st.markdown("---")
        st.markdown("#### 📊 Damage Distribution & Urgency Analytics")

        all_reports = db.get_all_reports()
        if all_reports:
            # Count severity
            sev_counts = {"High": 0, "Medium": 0, "Low": 0}
            for r in all_reports:
                sev = r["severity"].capitalize()
                if sev in sev_counts:
                    sev_counts[sev] += 1

            # Count status
            stat_counts = {"Reported": 0, "Assigned": 0, "In Progress": 0, "Fixed": 0}
            for r in all_reports:
                stt = r["status"]
                if stt in stat_counts:
                    stat_counts[stt] += 1

            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.write("**Reports by Severity**")
                if _has_real_pandas:
                    df = pd.DataFrame(all_reports)
                    sc = df["severity"].value_counts().reindex(["High", "Medium", "Low"], fill_value=0)
                    st.bar_chart(sc, color="#2563EB")
                else:
                    st.bar_chart(sev_counts, color="#2563EB")

            with col_chart2:
                st.write("**Reports by Status**")
                if _has_real_pandas:
                    df = pd.DataFrame(all_reports)
                    stc = df["status"].value_counts().reindex(["Reported", "Assigned", "In Progress", "Fixed"], fill_value=0)
                    st.bar_chart(stc, color="#059669")
                else:
                    st.bar_chart(stat_counts, color="#059669")

        # Filterable Reports Table
        st.markdown("---")
        st.markdown("#### 🔍 Filter & Triage Incident Reports")

        f_col1, f_col2 = st.columns(2)
        with f_col1:
            t_status = st.selectbox("Status Filter", ["All", "Reported", "Assigned", "In Progress", "Fixed"], key="dash_f_status")
        with f_col2:
            t_sev = st.selectbox("Severity Filter", ["All", "High", "Medium", "Low"], key="dash_f_sev")

        filtered_dash_reports = db.filter_reports(status=t_status, severity=t_sev)

        if filtered_dash_reports:
            dash_rows = [
                {
                    "ID": r["id"],
                    "Report Date": r["created_at"],
                    "Type": r["damage_type"].title(),
                    "Severity": r["severity"],
                    "Damage %": f"{r['damage_percent']}%",
                    "Potholes": r["pothole_count"],
                    "Status": r["status"],
                    "Lat": r["latitude"],
                    "Lng": r["longitude"],
                }
                for r in filtered_dash_reports
            ]
            if _has_real_pandas:
                st.dataframe(pd.DataFrame(dash_rows), use_container_width=True, hide_index=True)
            else:
                st.dataframe(dash_rows, use_container_width=True, hide_index=True)
        else:
            st.info("No reports match the selected filters.")


        # Report Detail & Status Management Section
        st.markdown("---")
        st.markdown("#### 🛠️ Manage Incident & Update Maintenance Status")

        if all_reports:
            report_options = [f"#{r['id']} - {r['damage_type'].title()} ({r['severity']}) - {r['status']}" for r in all_reports]
            selected_option = st.selectbox("Select Incident Report to Inspect", report_options)
            selected_id = int(selected_option.split(" ")[0].replace("#", ""))

            report = db.get_report_by_id(selected_id)
            if report:
                col_det1, col_det2 = st.columns([1, 1])

                with col_det1:
                    st.write("**Incident Photograph**")
                    if os.path.exists(report["image_path"]):
                        st.image(report["image_path"], caption=f"Report #{report['id']} Road Surface", use_container_width=True)
                    else:
                        st.warning("Photograph file not found on disk.")

                with col_det2:
                    st.markdown(f"### Incident #{report['id']}")
                    st.markdown(
                        f"""
                        <div>
                            {get_severity_badge_html(report['severity'])} &nbsp;
                            {get_status_badge_html(report['status'])}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    st.markdown(f"**Reported On:** {report['created_at']}")
                    st.markdown(f"**Coordinates:** `{report['latitude']}, {report['longitude']}`")
                    st.markdown(f"**Defect Type:** {report['damage_type'].title()}")
                    st.markdown(f"**Potholes Observed:** {report['pothole_count']}")
                    st.markdown(f"**Damage Extent:** {report['damage_percent']}%")
                    st.markdown(f"**AI Confidence:** {int(report['confidence'] * 100)}%")

                    st.markdown(
                        f"""
                        <div class="analysis-box">
                            <p style="margin-bottom: 4px;"><strong>AI Inspection Summary:</strong> {report['summary']}</p>
                            <p style="margin-bottom: 4px;"><strong>Recommended Repair:</strong> {report['recommended_action']}</p>
                            <p style="margin-bottom: 0;"><strong>Citizen Description:</strong> {report['user_description'] or 'None provided.'}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # Status Updater
                    st.markdown("##### Change Work Order Status")
                    status_choices = ["Reported", "Assigned", "In Progress", "Fixed"]
                    current_idx = status_choices.index(report["status"]) if report["status"] in status_choices else 0

                    new_status = st.selectbox("Workflow Status", status_choices, index=current_idx)

                    if st.button("💾 Update Incident Status", type="primary"):
                        db.update_report_status(report["id"], new_status)
                        st.success(f"Status for Report #{report['id']} updated to **{new_status}**!")
                        st.rerun()
