import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
import datetime
import json
import re
import os
import sys

# Import core modules
from modules.file_reader import read_telecom_file, inspect_excel_sheets, select_best_sheet
from modules.column_mapper import (
    CDR_CANONICAL_ALIASES,
    IPDR_CANONICAL_ALIASES,
    detect_file_type,
    map_dataset_columns
)
from modules.data_standardizer import (
    standardize_cdr_dataset,
    standardize_ipdr_dataset,
    clean_phone_number
)
from engine import (
    to_excel_bytes,
    process_assistant_query
)

# ==============================================================================
# 1. PAGE CONFIGURATION & THEME
# ==============================================================================
st.set_page_config(
    page_title="CDR/IPDR Intelligence Platform",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    /* Metric Card Styling */
    div[data-testid="stMetric"] {
        background-color: #0e1726;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 12px 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    div[data-testid="stMetricLabel"] p {
        font-size: 0.85rem;
        color: #94a3b8;
        font-weight: 500;
    }
    div[data-testid="stMetricValue"] div {
        font-size: 1.6rem;
        color: #38bdf8;
        font-weight: 700;
    }
    
    /* Header Badges */
    .status-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 6px;
    }
    .badge-valid { background-color: #065f46; color: #34d399; }
    .badge-review { background-color: #7f1d1d; color: #f87171; }
    .badge-proto { background-color: #1e3a8a; color: #60a5fa; }
    .badge-cdr { background-color: #312e81; color: #a5b4fc; }
    .badge-ipdr { background-color: #064e3b; color: #6ee7b7; }
    
    /* Notice Banners */
    .responsible-notice {
        background-color: #1e293b;
        border-left: 4px solid #38bdf8;
        padding: 10px 14px;
        border-radius: 4px;
        font-size: 0.82rem;
        color: #cbd5e1;
        margin-bottom: 15px;
    }
    
    .stat-card {
        background-color: #0f172a;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. DATA INITIALIZATION & SESSION STATE
# ==============================================================================
def init_session_state():
    """Loads default demonstration datasets into Streamlit session state."""
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        reload_bundled_data()

def reload_bundled_data():
    """Forces reload of default synthetic or test datasets."""
    # Check for actual test files first, fallback to synthetic samples
    cdr_actual = os.path.join("data", "CDR_test_20_records.xlsx")
    cdr_sample = os.path.join("data", "sample_cdr.csv")
    
    ipdr_actual = os.path.join("data", "IPDR_test_20_records.xlsx")
    ipdr_sample = os.path.join("data", "sample_ipdr.csv")
    
    # Load CDR
    if os.path.exists(cdr_actual):
        with open(cdr_actual, "rb") as f:
            raw_cdr, _, _ = read_telecom_file(f, "CDR_test_20_records.xlsx")
        res_cdr = standardize_cdr_dataset(raw_cdr)
        st.session_state.cdr_df = res_cdr.standardized_df
        st.session_state.cdr_raw_df = raw_cdr
        st.session_state.cdr_source = "Actual Test Dataset (CDR_test_20_records.xlsx)"
        st.session_state.cdr_res = res_cdr
    elif os.path.exists(cdr_sample):
        raw_cdr = pd.read_csv(cdr_sample)
        res_cdr = standardize_cdr_dataset(raw_cdr)
        st.session_state.cdr_df = res_cdr.standardized_df
        st.session_state.cdr_raw_df = raw_cdr
        st.session_state.cdr_source = "Bundled Synthetic Sample (sample_cdr.csv)"
        st.session_state.cdr_res = res_cdr
    else:
        st.session_state.cdr_df = pd.DataFrame()
        st.session_state.cdr_raw_df = pd.DataFrame()
        st.session_state.cdr_source = "None"
        st.session_state.cdr_res = None
        
    # Load IPDR
    if os.path.exists(ipdr_actual):
        with open(ipdr_actual, "rb") as f:
            raw_ipdr, _, _ = read_telecom_file(f, "IPDR_test_20_records.xlsx")
        res_ipdr = standardize_ipdr_dataset(raw_ipdr)
        st.session_state.ipdr_df = res_ipdr.standardized_df
        st.session_state.ipdr_raw_df = raw_ipdr
        st.session_state.ipdr_source = "Actual Test Dataset (IPDR_test_20_records.xlsx)"
        st.session_state.ipdr_res = res_ipdr
    elif os.path.exists(ipdr_sample):
        raw_ipdr = pd.read_csv(ipdr_sample)
        res_ipdr = standardize_ipdr_dataset(raw_ipdr)
        st.session_state.ipdr_df = res_ipdr.standardized_df
        st.session_state.ipdr_raw_df = raw_ipdr
        st.session_state.ipdr_source = "Bundled Synthetic Sample (sample_ipdr.csv)"
        st.session_state.ipdr_res = res_ipdr
    else:
        st.session_state.ipdr_df = pd.DataFrame()
        st.session_state.ipdr_raw_df = pd.DataFrame()
        st.session_state.ipdr_source = "None"
        st.session_state.ipdr_res = None
        
    st.session_state.load_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

init_session_state()

# ==============================================================================
# 3. SIDEBAR NAVIGATION & DATA STATUS
# ==============================================================================
with st.sidebar:
    st.markdown("### 📡 CDR/IPDR Intelligence")
    st.markdown("<span class='status-badge badge-proto'>STANDARDIZATION ENGINE v2.0</span>", unsafe_allow_html=True)
    
    st.markdown("---")
    page = st.radio(
        "Navigation Modules",
        [
            "📊 1. Overview Dashboard",
            "⚙️ 2. Data Standardization",
            "📈 3. Pattern Analysis",
            "🕸️ 4. Relationship Graph",
            "⏱️ 5. Activity Timeline",
            "🤖 6. AI Assistant",
            "💾 7. Evidence & Export"
        ],
        index=0
    )
    
    st.markdown("---")
    st.markdown("#### 📁 Active Standardized Dataset")
    cdr_rows = len(st.session_state.cdr_df)
    ipdr_rows = len(st.session_state.ipdr_df)
    st.write(f"• **CDR Records**: `{cdr_rows:,}`")
    st.caption(f"Source: {st.session_state.cdr_source}")
    st.write(f"• **IPDR Sessions**: `{ipdr_rows:,}`")
    st.caption(f"Source: {st.session_state.ipdr_source}")
    st.caption(f"Last updated: {st.session_state.load_time}")
    
    if st.button("🔄 Reload Demonstration Datasets", use_container_width=True):
        reload_bundled_data()
        st.success("Reloaded sample datasets!")
        st.rerun()
        
    st.markdown("---")
    st.caption("🔒 **Security Notice**: Local, deterministic offline analysis. Metadata preserved without external API transmission.")

# ==============================================================================
# 4. MODULE 1: OVERVIEW DASHBOARD
# ==============================================================================
if page == "📊 1. Overview Dashboard":
    st.title("📊 Platform Overview & Intelligence Dashboard")
    st.markdown("""
    <div class='responsible-notice'>
        <b>Active Telecom Intelligence Engine:</b> Monitoring standardized CDR/IPDR communications and network sessions with automated quality validation.
    </div>
    """, unsafe_allow_html=True)
    
    cdr_df = st.session_state.cdr_df
    ipdr_df = st.session_state.ipdr_df
    
    # High-level KPIs
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    
    total_cdr = len(cdr_df)
    valid_cdr = len(cdr_df[cdr_df["validation_status"] == "VALID"]) if total_cdr > 0 else 0
    review_cdr = total_cdr - valid_cdr
    
    total_ipdr = len(ipdr_df)
    valid_ipdr = len(ipdr_df[ipdr_df["validation_status"] == "VALID"]) if total_ipdr > 0 else 0
    review_ipdr = total_ipdr - valid_ipdr
    
    if total_cdr > 0:
        phone_set = set(cdr_df["caller_number"].dropna().unique()).union(set(cdr_df["receiver_number"].dropna().unique()))
        phone_set.discard("")
        unique_phones = len(phone_set)
    else:
        unique_phones = 0
        
    unique_subs = ipdr_df["subscriber_id"].nunique() if total_ipdr > 0 else 0
    overall_health = round(((valid_cdr + valid_ipdr) / (total_cdr + total_ipdr) * 100), 1) if (total_cdr + total_ipdr) > 0 else 100
    
    kpi1.metric("Total CDR Records", f"{total_cdr:,}", f"{valid_cdr} Valid / {review_cdr} Review")
    kpi2.metric("Total IPDR Sessions", f"{total_ipdr:,}", f"{valid_ipdr} Valid / {review_ipdr} Review")
    kpi3.metric("Phone Identifiers", f"{unique_phones:,}", "Distinct entities")
    kpi4.metric("IPDR Subscribers", f"{unique_subs:,}", "Unique accounts")
    kpi5.metric("Data Quality Score", f"{overall_health}%", "Standardised & Valid")
    
    st.markdown("---")
    
    # Overview Charts Row 1: Daily CDR Volume & Protocol Distribution
    c1, c2 = st.columns([3, 2])
    
    with c1:
        st.subheader("📅 Daily Communication Event Volume (CDR)")
        if not cdr_df.empty and "parsed_timestamp" in cdr_df.columns:
            valid_events = cdr_df[cdr_df["validation_status"] == "VALID"].copy()
            if not valid_events.empty and not valid_events["parsed_timestamp"].isna().all():
                valid_events["event_date"] = valid_events["parsed_timestamp"].dt.date
                type_col = "call_type" if "call_type" in valid_events.columns else "direction"
                daily_counts = valid_events.groupby(["event_date", type_col]).size().reset_index(name="count")
                daily_counts["event_date"] = pd.to_datetime(daily_counts["event_date"])
                
                fig_daily = px.bar(
                    daily_counts,
                    x="event_date",
                    y="count",
                    color=type_col,
                    title="Daily Communication Events",
                    labels={"event_date": "Date", "count": "Event Count"},
                    barmode="stack",
                    color_discrete_sequence=px.colors.qualitative.Safe
                )
                fig_daily.update_layout(xaxis_title="", yaxis_title="Records Count", margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_daily, use_container_width=True)
            else:
                st.info("No valid CDR records with parsed timestamps available.")
        else:
            st.info("No CDR dataset currently standardized.")
            
    with c2:
        st.subheader("🌐 IPDR Volume by Protocol")
        if not ipdr_df.empty:
            valid_ipdr_df = ipdr_df[ipdr_df["validation_status"] == "VALID"].copy()
            if not valid_ipdr_df.empty:
                valid_ipdr_df["total_bytes"] = valid_ipdr_df["upload_bytes"] + valid_ipdr_df["download_bytes"]
                proto_df = valid_ipdr_df.groupby("protocol")["total_bytes"].sum().reset_index()
                proto_df["Total MB"] = (proto_df["total_bytes"] / (1024 * 1024)).round(2)
                
                fig_proto = px.pie(
                    proto_df,
                    names="protocol",
                    values="Total MB",
                    title="Total Data Volume (MB) by Protocol",
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_proto.update_traces(textposition='inside', textinfo='percent+label')
                fig_proto.update_layout(margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_proto, use_container_width=True)
            else:
                st.info("No valid IPDR records.")
        else:
            st.info("No IPDR dataset currently standardized.")
            
    # Overview Charts Row 2: Status Breakdown & Review Alerts
    r2_c1, r2_c2 = st.columns(2)
    
    with r2_c1:
        st.subheader("📞 Call Disposition & Status Breakdown")
        if not cdr_df.empty:
            valid_cdr_df = cdr_df[cdr_df["validation_status"] == "VALID"]
            status_col = "call_status" if "call_status" in valid_cdr_df.columns else "direction"
            status_counts = valid_cdr_df[status_col].value_counts().reset_index()
            status_counts.columns = ["Call Status", "Count"]
            
            fig_status = px.bar(
                status_counts,
                x="Call Status",
                y="Count",
                color="Call Status",
                text="Count",
                title=f"Distribution by {status_col}"
            )
            fig_status.update_layout(showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_status, use_container_width=True)
        else:
            st.info("No CDR records available.")
            
    with r2_c2:
        st.subheader("⚠️ Data Quality & Review Flags")
        st.write("Records requiring analyst inspection due to format or schema issues:")
        
        tab_v1, tab_v2 = st.tabs(["CDR Review Ledger", "IPDR Review Ledger"])
        with tab_v1:
            cdr_reviews = cdr_df[cdr_df["validation_status"] == "REVIEW"]
            if not cdr_reviews.empty:
                cols_to_show = [c for c in ["caller_number", "receiver_number", "event_timestamp", "duration_seconds", "validation_errors"] if c in cdr_reviews.columns]
                st.dataframe(cdr_reviews[cols_to_show], use_container_width=True, height=200)
            else:
                st.success("All loaded CDR records passed validation cleanly (0 REVIEW flags).")
                
        with tab_v2:
            ipdr_reviews = ipdr_df[ipdr_df["validation_status"] == "REVIEW"]
            if not ipdr_reviews.empty:
                cols_to_show_ipdr = [c for c in ["subscriber_id", "ip_address", "session_start", "session_end", "validation_errors"] if c in ipdr_reviews.columns]
                st.dataframe(ipdr_reviews[cols_to_show_ipdr], use_container_width=True, height=200)
            else:
                st.success("All loaded IPDR records passed validation cleanly (0 REVIEW flags).")

# ==============================================================================
# 5. MODULE 2: DATA STANDARDIZATION ENGINE
# ==============================================================================
elif page == "⚙️ 2. Data Standardization":
    st.title("⚙️ Intelligent CDR/IPDR Data Standardization Engine")
    st.markdown("""
    Upload raw telecom exports in **Excel (`.xlsx`, `.xls`)** or **CSV (`.csv`)** format.
    The standardization engine automatically:
    - **Detects File Type**: Automatically determines whether the file is **CDR** or **IPDR**.
    - **Maps Columns**: Normalizes diverse provider column aliases (`A-Party (Calling)`, `MSISDN`, `Duration (sec)`, etc.).
    - **Combines Split Fields**: Detects and unifies split `Call Date` and `Call Time` into canonical `event_timestamp`.
    - **Preserves Metadata**: Retains original values (country codes, IMEI, IMSI, APN, ports, operator, LAC, cell towers).
    - **Validates Data**: Assigns `VALID` or `REVIEW` status without silently deleting records.
    """)
    
    uploaded_file = st.file_uploader(
        "Upload CDR or IPDR File (Excel or CSV)",
        type=["xlsx", "xls", "csv"],
        key="standardizer_uploader",
        help="Upload files such as CDR_test_20_records.xlsx or IPDR_test_20_records.xlsx"
    )
    
    if uploaded_file is not None:
        filename = uploaded_file.name
        
        # Check available sheets for Excel
        sheet_selected = None
        if filename.lower().endswith((".xlsx", ".xls")):
            available_sheets = inspect_excel_sheets(uploaded_file)
            if len(available_sheets) > 1:
                col_sh1, _ = st.columns([1, 2])
                with col_sh1:
                    sheet_selected = st.selectbox(
                        "Worksheet Detected (Multi-Sheet Workbook):",
                        available_sheets,
                        index=available_sheets.index(select_best_sheet(available_sheets)) if select_best_sheet(available_sheets) in available_sheets else 0,
                        key="active_sheet_selector"
                    )
                    
        # Read raw tabular file
        try:
            raw_df, sheets, active_sheet = read_telecom_file(uploaded_file, filename, sheet_name=sheet_selected)
            raw_columns = list(raw_df.columns)
            
            # Step 1: Detect File Type
            detected_type, type_confidence = detect_file_type(raw_columns)
            
            st.markdown("---")
            st.subheader("1. File Detection & Schema Inspection")
            
            det_c1, det_c2, det_c3 = st.columns(3)
            det_c1.info(f"**Filename:** `{filename}`")
            det_c2.info(f"**Detected Type:** **{detected_type}** ({int(type_confidence*100)}% confidence)")
            det_c3.info(f"**Total Records:** `{len(raw_df):,}` rows | `{len(raw_columns)}` columns")
            
            # Allow user override of dataset type if needed
            type_override = st.radio(
                "Standardization Target Schema:",
                ["Auto-Detect (" + detected_type + ")", "CDR", "IPDR"],
                horizontal=True,
                index=0
            )
            final_type = detected_type if "Auto-Detect" in type_override else type_override
            
            # Step 2: Mapping Preview & Overrides
            st.markdown("---")
            st.subheader("2. Automated Column Mapping & Alignment")
            
            mapping_result = map_dataset_columns(raw_columns, dataset_type=final_type)
            detected_mappings = mapping_result["mapping"]
            
            # Create a structured mapping display
            mapping_rows = []
            for col in raw_columns:
                target = detected_mappings.get(col, "(Unmapped / Extra Metadata)")
                conf = mapping_result["confidence"].get(col, 0.0)
                status = "Mapped Canonical" if col in detected_mappings else "Preserved Metadata"
                if target in ["call_date", "call_time"]:
                    status = "Combined into event_timestamp"
                mapping_rows.append({
                    "Uploaded Column": col,
                    "Target Canonical Field": target,
                    "Confidence": f"{int(conf * 100)}%" if conf > 0 else "N/A",
                    "Role / Handling": status
                })
                
            st.dataframe(pd.DataFrame(mapping_rows), use_container_width=True, height=250)
            
            # Step 3: Action Buttons & Standardization Trigger
            st.markdown("---")
            st.subheader("3. Execute Standardization Pipeline")
            
            col_btn, _ = st.columns([1, 3])
            with col_btn:
                run_standardization = st.button("🚀 Standardize Data", type="primary", use_container_width=True)
                
            if run_standardization or f"std_res_{filename}" in st.session_state:
                if final_type == "CDR":
                    res = standardize_cdr_dataset(raw_df)
                    if res.is_successful:
                        st.session_state.cdr_df = res.standardized_df
                        st.session_state.cdr_raw_df = raw_df
                        st.session_state.cdr_source = f"Standardized Upload: {filename}"
                        st.session_state.load_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                else:
                    res = standardize_ipdr_dataset(raw_df)
                    if res.is_successful:
                        st.session_state.ipdr_df = res.standardized_df
                        st.session_state.ipdr_raw_df = raw_df
                        st.session_state.ipdr_source = f"Standardized Upload: {filename}"
                        st.session_state.load_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                st.session_state[f"std_res_{filename}"] = res
                
                if not res.is_successful:
                    st.error(f"Standardization Error: {res.error_message}")
                else:
                    # Display Verification Statistics Card (Section 8 spec)
                    st.success("✅ Standardization Pipeline Completed Successfully!")
                    
                    std_df = res.standardized_df
                    valid_pct = round((res.valid_count / res.total_records * 100), 1) if res.total_records > 0 else 0
                    
                    stat_col1, stat_col2, stat_col3, stat_col4, stat_col5, stat_col6 = st.columns(6)
                    stat_col1.metric("Total Records", f"{res.total_records:,}")
                    stat_col2.metric("Valid Records", f"{res.valid_count:,}", f"{valid_pct}%")
                    stat_col3.metric("Review Records", f"{res.review_count:,}")
                    stat_col4.metric("Columns Detected", len(raw_columns))
                    required_count = "3 / 3" if final_type == "CDR" else "4 / 4"
                    stat_col5.metric("Required Mapped", required_count)
                    stat_col6.metric("Pipeline Status", "Successful")
                    
                    # Previews & Inspection Tabs
                    tab_std, tab_orig, tab_log, tab_invalid = st.tabs([
                        "📋 Standardized Dataset",
                        "📄 Original Uploaded Dataset",
                        "🔍 Mapping Decisions & Metadata Log",
                        "⚠️ Invalid / Review Records"
                    ])
                    
                    with tab_std:
                        st.dataframe(std_df, use_container_width=True, height=350)
                        
                        down_c1, down_c2 = st.columns(2)
                        with down_c1:
                            csv_std = std_df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                f"⬇️ Download Standardized {final_type} (CSV)",
                                data=csv_std,
                                file_name=f"standardized_{final_type.lower()}_{filename.split('.')[0]}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                        with down_c2:
                            xlsx_std = to_excel_bytes(std_df, sheet_name=f"{final_type}_Standardized")
                            st.download_button(
                                f"⬇️ Download Standardized {final_type} (Excel .xlsx)",
                                data=xlsx_std,
                                file_name=f"standardized_{final_type.lower()}_{filename.split('.')[0]}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                            
                    with tab_orig:
                        st.caption("Untouched raw dataset as uploaded:")
                        st.dataframe(raw_df, use_container_width=True, height=350)
                        
                    with tab_log:
                        st.write("##### Engine Decisions & Field Transformations:")
                        for dec in res.decisions:
                            st.write(f"• {dec}")
                            
                        if res.unmapped_columns:
                            st.warning(f"**Preserved Extra Unmapped Metadata Columns:** {', '.join(res.unmapped_columns)}")
                        else:
                            st.info("All uploaded columns successfully matched or integrated into the canonical model.")
                            
                    with tab_invalid:
                        invalid_records = std_df[std_df["validation_status"] == "REVIEW"]
                        if not invalid_records.empty:
                            st.warning(f"Found {len(invalid_records)} record(s) flagged for analyst review:")
                            st.dataframe(invalid_records, use_container_width=True, height=300)
                            
                            inv_csv = invalid_records.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                "⬇️ Download Invalid/Rejected Records (CSV)",
                                data=inv_csv,
                                file_name=f"invalid_records_{filename.split('.')[0]}.csv",
                                mime="text/csv"
                            )
                        else:
                            st.success("Zero invalid records detected. 100% of rows are ready for immediate investigation.")
        except Exception as e:
            st.error(f"Error processing upload: {str(e)}")
    else:
        st.info("Please upload a CDR or IPDR file above to begin automatic standardization.")
        
        # Provide sample loading shortcuts
        st.markdown("---")
        st.write("##### Or load test files directly from workspace:")
        ts_c1, ts_c2 = st.columns(2)
        if ts_c1.button("📂 Load 'CDR_test_20_records.xlsx'", use_container_width=True):
            cdr_path = os.path.join("data", "CDR_test_20_records.xlsx")
            if os.path.exists(cdr_path):
                with open(cdr_path, "rb") as f:
                    raw_cdr, _, _ = read_telecom_file(f, "CDR_test_20_records.xlsx")
                res = standardize_cdr_dataset(raw_cdr)
                st.session_state.cdr_df = res.standardized_df
                st.session_state.cdr_raw_df = raw_cdr
                st.session_state.cdr_source = "Loaded: CDR_test_20_records.xlsx"
                st.session_state.load_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success("Loaded and standardized CDR_test_20_records.xlsx!")
                st.rerun()
                
        if ts_c2.button("📂 Load 'IPDR_test_20_records.xlsx'", use_container_width=True):
            ipdr_path = os.path.join("data", "IPDR_test_20_records.xlsx")
            if os.path.exists(ipdr_path):
                with open(ipdr_path, "rb") as f:
                    raw_ipdr, _, _ = read_telecom_file(f, "IPDR_test_20_records.xlsx")
                res = standardize_ipdr_dataset(raw_ipdr)
                st.session_state.ipdr_df = res.standardized_df
                st.session_state.ipdr_raw_df = raw_ipdr
                st.session_state.ipdr_source = "Loaded: IPDR_test_20_records.xlsx"
                st.session_state.load_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.success("Loaded and standardized IPDR_test_20_records.xlsx!")
                st.rerun()

# ==============================================================================
# 6. MODULE 3: PATTERN ANALYSIS
# ==============================================================================
elif page == "📈 3. Pattern Analysis":
    st.title("📈 Communication Pattern Analysis")
    st.markdown("""
    Statistical profiling across calling behavior, hourly distributions, counterparty diversity, and daily activity baselines.
    """)
    
    cdr_df = st.session_state.cdr_df
    if cdr_df.empty:
        st.warning("Please load or standardise a CDR dataset first.")
        st.stop()
        
    valid_cdr = cdr_df[cdr_df["validation_status"] == "VALID"].copy()
    
    all_parties = sorted(list(set(valid_cdr["caller_number"].dropna().unique()).union(set(valid_cdr["receiver_number"].dropna().unique()))))
    all_parties = [p for p in all_parties if p and str(p) != "nan"]
    
    options = ["All Identifiers"] + all_parties
    selected_target = st.selectbox("Select Target Identifier for Pattern Deep-Dive", options, index=0)
    
    if selected_target == "All Identifiers":
        target_df = valid_cdr
        st.info(f"Showing aggregated metrics across all **{len(all_parties)}** phone identifiers.")
    else:
        target_df = valid_cdr[(valid_cdr["caller_number"] == selected_target) | (valid_cdr["receiver_number"] == selected_target)].copy()
        st.info(f"Filtered to identifier **{selected_target}** ({len(target_df)} involved events).")
        
    m1, m2, m3, m4 = st.columns(4)
    tot_events = len(target_df)
    tot_duration = int(target_df["duration_seconds"].sum()) if "duration_seconds" in target_df.columns else 0
    hours, remainder = divmod(tot_duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    dur_str = f"{hours}h {minutes}m {seconds}s"
    
    if selected_target == "All Identifiers":
        counterparties = len(all_parties)
    else:
        calls_out = set(target_df[target_df["caller_number"] == selected_target]["receiver_number"])
        calls_in = set(target_df[target_df["receiver_number"] == selected_target]["caller_number"])
        counterparties = len((calls_out | calls_in) - {selected_target, ""})
        
    top_tower = target_df["cell_tower_id"].mode()[0] if not target_df.empty and "cell_tower_id" in target_df.columns and not target_df["cell_tower_id"].empty else "N/A"
    
    m1.metric("Total Events", f"{tot_events:,}")
    m2.metric("Cumulative Duration", dur_str)
    m3.metric("Distinct Counterparties", f"{counterparties:,}")
    m4.metric("Top Cell Tower", top_tower)
    
    st.markdown("---")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("⏰ Hourly Communication Profile (24h)")
        if "parsed_timestamp" in target_df.columns and not target_df["parsed_timestamp"].isna().all():
            target_df["hour"] = target_df["parsed_timestamp"].dt.hour
            hourly_counts = target_df["hour"].value_counts().reindex(range(24), fill_value=0).reset_index()
            hourly_counts.columns = ["Hour of Day", "Event Count"]
            
            fig_hour = px.bar(
                hourly_counts,
                x="Hour of Day",
                y="Event Count",
                title="Event Frequency by Hour (00:00 - 23:00)",
                labels={"Hour of Day": "Hour (0-23)", "Event Count": "Total Events"},
                color="Event Count",
                color_continuous_scale="Viridis"
            )
            fig_hour.update_layout(xaxis=dict(tickmode="linear", tick0=0, dtick=2), margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_hour, use_container_width=True)
        else:
            st.info("Parsed timestamps not available for hourly chart.")
            
    with col_chart2:
        st.subheader("🏆 Top Calling Parties by Outgoing Records")
        top_callers = valid_cdr.groupby("caller_number").size().reset_index(name="Call Count").sort_values("Call Count", ascending=True).tail(8)
        
        fig_top = px.bar(
            top_callers,
            x="Call Count",
            y="caller_number",
            orientation="h",
            title="Most Active Calling Numbers",
            labels={"Call Count": "Outgoing Records", "caller_number": "Phone Identifier"},
            color="Call Count",
            color_continuous_scale="Blues"
        )
        fig_top.update_layout(margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_top, use_container_width=True)
        
    st.markdown("---")
    
    st.subheader("🚨 Statistical Daily Outlier Analysis (Mean + 2σ Baseline)")
    if "parsed_timestamp" in target_df.columns and not target_df.empty and not target_df["parsed_timestamp"].isna().all():
        target_df["date"] = target_df["parsed_timestamp"].dt.date
        daily_series = target_df.groupby("date").size().reset_index(name="Event_Count")
        daily_series["date"] = pd.to_datetime(daily_series["date"])
        
        mean_val = daily_series["Event_Count"].mean()
        std_val = daily_series["Event_Count"].std() if len(daily_series) > 1 else 0
        threshold = mean_val + (2 * std_val) if std_val > 0 else mean_val * 1.5
        
        daily_series["Outlier_Flag"] = daily_series["Event_Count"].apply(lambda x: "🚨 SPIKE DETECTED" if x > threshold else "Normal")
        
        fig_outlier = go.Figure()
        fig_outlier.add_trace(go.Bar(
            x=daily_series["date"],
            y=daily_series["Event_Count"],
            name="Daily Events",
            marker_color=["#ef4444" if flag == "🚨 SPIKE DETECTED" else "#38bdf8" for flag in daily_series["Outlier_Flag"]]
        ))
        fig_outlier.add_trace(go.Scatter(
            x=daily_series["date"],
            y=[threshold] * len(daily_series),
            mode="lines",
            name="Threshold (Mean + 2σ)",
            line=dict(color="#f59e0b", dash="dash", width=2)
        ))
        fig_outlier.update_layout(
            title=f"Daily Events vs Anomaly Threshold ({threshold:.1f} events/day)",
            xaxis_title="Date",
            yaxis_title="Events",
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_outlier, use_container_width=True)

# ==============================================================================
# 7. MODULE 4: RELATIONSHIP GRAPH
# ==============================================================================
elif page == "🕸️ 4. Relationship Graph":
    st.title("🕸️ Communication Relationship Network Graph")
    st.markdown("""
    Visualises caller-receiver pairs as an undirected network graph constructed with NetworkX and rendered via Plotly. Node size reflects connectivity degree; edges represent observed communication interactions.
    """)
    
    cdr_df = st.session_state.cdr_df
    if cdr_df.empty:
        st.warning("Please load or standardise a CDR dataset first.")
        st.stop()
        
    valid_cdr = cdr_df[cdr_df["validation_status"] == "VALID"].copy()
    if valid_cdr.empty:
        st.warning("No valid CDR records available for relationship graph construction.")
        st.stop()
        
    g_col1, g_col2 = st.columns([1, 2])
    with g_col1:
        min_interactions = st.slider("Minimum Interaction Threshold (Calls/SMS)", min_value=1, max_value=10, value=1, step=1)
    with g_col2:
        distinct_nodes = sorted(list(set(valid_cdr["caller_number"].dropna()).union(set(valid_cdr["receiver_number"].dropna()))))
        distinct_nodes = [d for d in distinct_nodes if d and str(d) != "nan"]
        focus_node = st.selectbox("Focus on Subgraph (Ego Network)", ["All Nodes (Full Network)"] + distinct_nodes)
        
    valid_cdr["pair_node1"] = valid_cdr.apply(lambda r: min(str(r["caller_number"]), str(r["receiver_number"])), axis=1)
    valid_cdr["pair_node2"] = valid_cdr.apply(lambda r: max(str(r["caller_number"]), str(r["receiver_number"])), axis=1)
    
    dur_col = "duration_seconds" if "duration_seconds" in valid_cdr.columns else "caller_number"
    edge_summary = valid_cdr.groupby(["pair_node1", "pair_node2"]).agg(
        interactions=("caller_number", "count")
    ).reset_index()
    
    edge_filtered = edge_summary[edge_summary["interactions"] >= min_interactions]
    
    G = nx.Graph()
    for idx, row in edge_filtered.iterrows():
        n1, n2, weight = row["pair_node1"], row["pair_node2"], row["interactions"]
        if n1 and n2 and n1 != n2:
            G.add_edge(n1, n2, weight=weight)
            
    if focus_node != "All Nodes (Full Network)":
        if focus_node in G:
            neighbors = list(G.neighbors(focus_node)) + [focus_node]
            G = G.subgraph(neighbors).copy()
        else:
            st.info(f"Node **{focus_node}** has no connections meeting the threshold.")
            G = nx.Graph()
            
    if G.number_of_nodes() == 0:
        st.warning("No nodes or relationships meet the current filter criteria.")
    else:
        pos = nx.spring_layout(G, k=0.7, iterations=50, seed=42)
        
        edge_x = []
        edge_y = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=1.5, color='#475569'),
            hoverinfo='none',
            mode='lines'
        )
        
        node_x, node_y, node_text, node_size, node_color = [], [], [], [], []
        degrees = dict(G.degree())
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            deg = degrees[node]
            node_text.append(f"<b>Identifier:</b> {node}<br><b>Degree:</b> {deg} links")
            
            if focus_node != "All Nodes (Full Network)" and node == focus_node:
                node_size.append(34)
                node_color.append("#f43f5e")
            else:
                node_size.append(18 + min(deg * 3, 20))
                node_color.append("#38bdf8")
                
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            text=[f"  {n}" for n in G.nodes()],
            textposition="top right",
            hoverinfo='text',
            hovertext=node_text,
            marker=dict(color=node_color, size=node_size, line=dict(width=2, color='#ffffff'))
        )
        
        fig_net = go.Figure(
            data=[edge_trace, node_trace],
            layout=go.Layout(
                title=f"Network Visualization ({G.number_of_nodes()} Nodes, {G.number_of_edges()} Edges)",
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20, l=20, r=20, t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                plot_bgcolor='#0b1120'
            )
        )
        st.plotly_chart(fig_net, use_container_width=True)
        
        st.subheader("📊 Graph Metrics & Centrality")
        net_col1, net_col2, net_col3 = st.columns(3)
        net_col1.metric("Observed Nodes", G.number_of_nodes())
        net_col2.metric("Observed Links", G.number_of_edges())
        density = nx.density(G)
        net_col3.metric("Network Density", f"{density:.3f}")
        
        degree_df = pd.DataFrame([{"Identifier": n, "Degree Centrality": d} for n, d in G.degree()]).sort_values("Degree Centrality", ascending=False)
        st.dataframe(degree_df, use_container_width=True, height=200)

# ==============================================================================
# 8. MODULE 5: ACTIVITY TIMELINE
# ==============================================================================
elif page == "⏱️ 5. Activity Timeline":
    st.title("⏱️ Chronological Activity Timeline")
    st.markdown("""
    Detailed chronological inspection of communication events and network sessions for target identifiers.
    """)
    
    t_tab1, t_tab2 = st.tabs(["📞 CDR Identifier Timeline", "🌐 IPDR Subscriber Sessions"])
    
    with t_tab1:
        cdr_df = st.session_state.cdr_df
        if not cdr_df.empty:
            valid_cdr = cdr_df[cdr_df["validation_status"] == "VALID"].copy()
            unique_targets = sorted(list(set(valid_cdr["caller_number"].dropna()).union(set(valid_cdr["receiver_number"].dropna()))))
            unique_targets = [u for u in unique_targets if u and str(u) != "nan"]
            
            selected_sub = st.selectbox("Select Phone Identifier", unique_targets, index=0)
            
            sub_events = valid_cdr[(valid_cdr["caller_number"] == selected_sub) | (valid_cdr["receiver_number"] == selected_sub)].copy()
            if "parsed_timestamp" in sub_events.columns and not sub_events["parsed_timestamp"].isna().all():
                sub_events = sub_events.sort_values("parsed_timestamp", ascending=True)
                
            out_count = len(sub_events[sub_events["caller_number"] == selected_sub])
            in_count = len(sub_events[sub_events["receiver_number"] == selected_sub])
            
            c_k1, c_k2, c_k3 = st.columns(3)
            c_k1.metric("Total Events", len(sub_events))
            c_k2.metric("Outgoing Calls/SMS", out_count)
            c_k3.metric("Incoming Calls/SMS", in_count)
            
            if not sub_events.empty:
                sub_events["Role"] = sub_events.apply(lambda r: "Outgoing (Caller)" if r["caller_number"] == selected_sub else "Incoming (Receiver)", axis=1)
                sub_events["Counterparty"] = sub_events.apply(lambda r: r["receiver_number"] if r["caller_number"] == selected_sub else r["caller_number"], axis=1)
                
                if "parsed_timestamp" in sub_events.columns and not sub_events["parsed_timestamp"].isna().all():
                    fig_time = px.scatter(
                        sub_events,
                        x="parsed_timestamp",
                        y="Counterparty",
                        color="Role",
                        size="duration_seconds" if "duration_seconds" in sub_events.columns else None,
                        hover_data=[c for c in ["call_type", "direction", "call_status", "cell_tower_id", "operator"] if c in sub_events.columns],
                        title=f"Chronological Communication Timeline for {selected_sub}",
                        color_discrete_map={"Outgoing (Caller)": "#38bdf8", "Incoming (Receiver)": "#34d399"}
                    )
                    fig_time.update_layout(margin=dict(l=20, r=20, t=40, b=20))
                    st.plotly_chart(fig_time, use_container_width=True)
                    
                st.subheader("Event Ledger")
                preferred_cols = ["event_timestamp", "Role", "Counterparty", "duration_seconds", "call_type", "direction", "call_status", "cell_tower_id", "operator"]
                display_cols = [c for c in preferred_cols if c in sub_events.columns]
                st.dataframe(sub_events[display_cols], use_container_width=True, height=350)
                
                col_exp1, col_exp2 = st.columns(2)
                with col_exp1:
                    tl_csv = sub_events[display_cols].to_csv(index=False).encode('utf-8')
                    st.download_button(
                        f"⬇️ Export Timeline (CSV)",
                        data=tl_csv,
                        file_name=f"timeline_{selected_sub}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                with col_exp2:
                    tl_xlsx = to_excel_bytes(sub_events[display_cols], sheet_name=f"TL_{selected_sub[-6:]}")
                    st.download_button(
                        f"⬇️ Export Timeline (Excel)",
                        data=tl_xlsx,
                        file_name=f"timeline_{selected_sub}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
        else:
            st.info("No CDR dataset loaded.")
            
    with t_tab2:
        ipdr_df = st.session_state.ipdr_df
        if not ipdr_df.empty:
            valid_ipdr = ipdr_df[ipdr_df["validation_status"] == "VALID"].copy()
            subs = sorted(list(valid_ipdr["subscriber_id"].dropna().unique()))
            
            selected_ipdr_sub = st.selectbox("Select IPDR Subscriber ID", subs, index=0)
            
            sub_sessions = valid_ipdr[valid_ipdr["subscriber_id"] == selected_ipdr_sub].copy()
            if "parsed_start" in sub_sessions.columns and not sub_sessions["parsed_start"].isna().all():
                sub_sessions = sub_sessions.sort_values("parsed_start", ascending=True)
                
            sub_sessions["Upload (MB)"] = (sub_sessions["upload_bytes"] / (1024 * 1024)).round(2)
            sub_sessions["Download (MB)"] = (sub_sessions["download_bytes"] / (1024 * 1024)).round(2)
            sub_sessions["Total (MB)"] = sub_sessions["Upload (MB)"] + sub_sessions["Download (MB)"]
            
            st.metric("Total Sessions for Subscriber", len(sub_sessions), f"{sub_sessions['Total (MB)'].sum():.2f} MB Transferred")
            
            pref_ipdr_cols = ["session_start", "session_end", "ip_address", "public_ip", "protocol", "service_domain", "network_id", "apn", "Upload (MB)", "Download (MB)", "Total (MB)"]
            show_ipdr_cols = [c for c in pref_ipdr_cols if c in sub_sessions.columns]
            st.dataframe(sub_sessions[show_ipdr_cols], use_container_width=True, height=350)
        else:
            st.info("No IPDR dataset loaded.")

# ==============================================================================
# 9. MODULE 6: AI ASSISTANT
# ==============================================================================
elif page == "🤖 6. AI Assistant":
    st.title("🤖 AI-Assisted Query Assistant")
    st.markdown("""
    Ask natural-language style questions to interrogate communication records.
    
    <div class='responsible-notice'>
        <b>Local Deterministic Router:</b> Standardized local query execution mapping questions to local Pandas operations without transmitting data to external third-party endpoints.
    </div>
    """, unsafe_allow_html=True)
    
    st.write("##### Quick Suggestion Queries:")
    quick_col1, quick_col2, quick_col3 = st.columns(3)
    quick_col4, quick_col5, _ = st.columns(3)
    
    prompt_clicked = None
    if quick_col1.button("Show the top callers by number of records", use_container_width=True):
        prompt_clicked = "Show the top callers by number of records"
        
    first_test_caller = "919810000105" if not st.session_state.cdr_df.empty and "919810000105" in set(st.session_state.cdr_df["caller_number"].values) else "9000000001"
    second_test_caller = "919820000204" if not st.session_state.cdr_df.empty and "919820000204" in set(st.session_state.cdr_df["receiver_number"].values) else "9000000002"
    
    if quick_col2.button(f"Show timeline for {first_test_caller}", use_container_width=True):
        prompt_clicked = f"Show timeline for {first_test_caller}"
    if quick_col3.button(f"Find common contacts between {first_test_caller} and {second_test_caller}", use_container_width=True):
        prompt_clicked = f"Find common contacts between {first_test_caller} and {second_test_caller}"
    if quick_col4.button("Summarise the uploaded datasets", use_container_width=True):
        prompt_clicked = "Summarise the uploaded datasets"
    if quick_col5.button("Show IPDR data volume by subscriber", use_container_width=True):
        prompt_clicked = "Show IPDR data volume by subscriber"
        
    query_input = st.text_input(
        "Enter your query:",
        value=prompt_clicked if prompt_clicked else "",
        placeholder=f"e.g. Show timeline for {first_test_caller}"
    )
    
    if st.button("🔍 Run Query", type="primary") or query_input:
        if query_input:
            text_ans, res_table, intent = process_assistant_query(
                query_input,
                st.session_state.cdr_df,
                st.session_state.ipdr_df
            )
            
            st.markdown("### 📋 Assistant Response")
            st.markdown(text_ans)
            
            if not res_table.empty:
                st.markdown("#### 🔍 Supporting Evidence Table")
                st.dataframe(res_table, use_container_width=True)
                
                if intent == "top_callers" and "Calling Party (caller_number)" in res_table.columns:
                    fig_res = px.bar(
                        res_table.head(10),
                        x="Calling Party (caller_number)",
                        y="Outgoing Records Count",
                        title="Top Callers by Outgoing Record Count",
                        color="Outgoing Records Count",
                        color_continuous_scale="Viridis"
                    )
                    st.plotly_chart(fig_res, use_container_width=True)
                    
                q_col1, q_col2 = st.columns(2)
                with q_col1:
                    res_csv = res_table.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "⬇️ Download Evidence (CSV)",
                        data=res_csv,
                        file_name=f"evidence_{intent}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                with q_col2:
                    res_xlsx = to_excel_bytes(res_table, sheet_name="QueryEvidence")
                    st.download_button(
                        "⬇️ Download Evidence (Excel)",
                        data=res_xlsx,
                        file_name=f"evidence_{intent}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
        else:
            st.info("Please enter a question or click a quick suggestion button above.")

# ==============================================================================
# 10. MODULE 7: EVIDENCE & EXPORT
# ==============================================================================
elif page == "💾 7. Evidence & Export":
    st.title("💾 Evidence Dossier & Export Center")
    st.markdown("""
    Generate standardised exports in CSV or Excel formats, download complete audit summaries, and review dataset provenance.
    """)
    
    cdr_df = st.session_state.cdr_df
    ipdr_df = st.session_state.ipdr_df
    
    st.subheader("📋 Dataset Provenance & Session Metadata")
    prov_data = {
        "Attribute": [
            "CDR Dataset Source", "CDR Record Count", "CDR Valid / Review Count",
            "IPDR Dataset Source", "IPDR Record Count", "IPDR Valid / Review Count",
            "Session Generated At", "Classification"
        ],
        "Value": [
            st.session_state.cdr_source,
            f"{len(cdr_df):,}",
            f"{len(cdr_df[cdr_df['validation_status'] == 'VALID'])} VALID / {len(cdr_df[cdr_df['validation_status'] == 'REVIEW'])} REVIEW" if not cdr_df.empty else "0 / 0",
            st.session_state.ipdr_source,
            f"{len(ipdr_df):,}",
            f"{len(ipdr_df[ipdr_df['validation_status'] == 'VALID'])} VALID / {len(ipdr_df[ipdr_df['validation_status'] == 'REVIEW'])} REVIEW" if not ipdr_df.empty else "0 / 0",
            st.session_state.load_time,
            "Standardized Telecom Records"
        ]
    }
    st.table(pd.DataFrame(prov_data))
    
    st.markdown("---")
    st.subheader("📦 Export Artifacts")
    
    e_col1, e_col2, e_col3 = st.columns(3)
    
    with e_col1:
        st.markdown("##### 1. Standardised CDR Export")
        st.caption("Complete canonical CDR table with validation flags.")
        if not cdr_df.empty:
            cdr_csv = cdr_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "⬇️ Download CDR (CSV)",
                data=cdr_csv,
                file_name="standardised_cdr_export.csv",
                mime="text/csv",
                use_container_width=True
            )
            cdr_xlsx = to_excel_bytes(cdr_df, sheet_name="CDR_Records")
            st.download_button(
                "⬇️ Download CDR (Excel .xlsx)",
                data=cdr_xlsx,
                file_name="standardised_cdr_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.button("No CDR Data", disabled=True, use_container_width=True)
            
    with e_col2:
        st.markdown("##### 2. Standardised IPDR Export")
        st.caption("Complete canonical IPDR sessions with validation flags.")
        if not ipdr_df.empty:
            ipdr_csv = ipdr_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "⬇️ Download IPDR (CSV)",
                data=ipdr_csv,
                file_name="standardised_ipdr_export.csv",
                mime="text/csv",
                use_container_width=True
            )
            ipdr_xlsx = to_excel_bytes(ipdr_df, sheet_name="IPDR_Sessions")
            st.download_button(
                "⬇️ Download IPDR (Excel .xlsx)",
                data=ipdr_xlsx,
                file_name="standardised_ipdr_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.button("No IPDR Data", disabled=True, use_container_width=True)
            
    with e_col3:
        st.markdown("##### 3. Case Dossier Audit (JSON)")
        st.caption("Complete JSON summary for case reporting and evidence.")
        
        summary_payload = {
            "metadata": {
                "generated_at": datetime.datetime.now().isoformat(),
                "application": "CDR/IPDR Intelligence Platform v2.0",
                "classification": "Demonstration Synthetic & Test Data"
            },
            "cdr_metrics": {
                "total_records": len(cdr_df),
                "valid_records": len(cdr_df[cdr_df["validation_status"] == "VALID"]) if not cdr_df.empty else 0,
                "review_records": len(cdr_df[cdr_df["validation_status"] == "REVIEW"]) if not cdr_df.empty else 0,
                "unique_callers": int(cdr_df["caller_number"].nunique()) if not cdr_df.empty else 0,
                "unique_receivers": int(cdr_df["receiver_number"].nunique()) if not cdr_df.empty else 0
            },
            "ipdr_metrics": {
                "total_sessions": len(ipdr_df),
                "valid_sessions": len(ipdr_df[ipdr_df["validation_status"] == "VALID"]) if not ipdr_df.empty else 0,
                "review_sessions": len(ipdr_df[ipdr_df["validation_status"] == "REVIEW"]) if not ipdr_df.empty else 0,
                "unique_subscribers": int(ipdr_df["subscriber_id"].nunique()) if not ipdr_df.empty else 0
            }
        }
        
        json_str = json.dumps(summary_payload, indent=2).encode('utf-8')
        st.download_button(
            "⬇️ Download Audit Summary (JSON)",
            data=json_str,
            file_name="case_audit_summary.json",
            mime="application/json",
            use_container_width=True
        )

# Footer
st.markdown("---")
st.caption("CDR/IPDR Intelligence Platform | AI-Assisted Communication & Network Analysis Platform | Hackathon Prototype")
