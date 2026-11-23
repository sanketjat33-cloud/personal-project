import os
import io
import re
import datetime
import json
import pandas as pd
import numpy as np

# Import modular components
from modules.file_reader import read_telecom_file
from modules.column_mapper import (
    CDR_CANONICAL_ALIASES,
    IPDR_CANONICAL_ALIASES,
    detect_file_type,
    map_dataset_columns,
    normalize_header
)
from modules.data_validator import (
    validate_cdr_dataframe,
    validate_ipdr_dataframe,
    is_valid_ip
)
from modules.data_standardizer import (
    clean_phone_number,
    combine_date_and_time,
    standardize_cdr_dataset,
    standardize_ipdr_dataset,
    StandardizationResult
)

# Maintain alias constants for backward compatibility
CDR_ALIASES = CDR_CANONICAL_ALIASES
IPDR_ALIASES = IPDR_CANONICAL_ALIASES

def read_tabular_file(file_obj, filename: str, sheet_name=None) -> tuple[pd.DataFrame, list]:
    """Compatibility wrapper around read_telecom_file."""
    df, sheets, active_sheet = read_telecom_file(file_obj, filename, sheet_name=sheet_name)
    return df, sheets

def to_excel_bytes(df: pd.DataFrame, sheet_name="Data") -> bytes:
    """Converts a DataFrame to Excel (.xlsx) bytes."""
    output = io.BytesIO()
    export_df = df.copy()
    for col in export_df.columns:
        if pd.api.types.is_datetime64_any_dtype(export_df[col]):
            export_df[col] = export_df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

def standardize_cdr(df_input: pd.DataFrame, custom_mapping=None) -> tuple[pd.DataFrame, dict, str]:
    """Centralized CDR standardization wrapper."""
    res = standardize_cdr_dataset(df_input, custom_mapping=custom_mapping)
    if not res.is_successful:
        return pd.DataFrame(), res.mapping, res.error_message
    return res.standardized_df, res.mapping, ""

def standardize_ipdr(df_input: pd.DataFrame, custom_mapping=None) -> tuple[pd.DataFrame, dict, str]:
    """Centralized IPDR standardization wrapper."""
    res = standardize_ipdr_dataset(df_input, custom_mapping=custom_mapping)
    if not res.is_successful:
        return pd.DataFrame(), res.mapping, res.error_message
    return res.standardized_df, res.mapping, ""

# Re-export clean_phone_identifier for backward compatibility
clean_phone_identifier = clean_phone_number
map_columns = lambda df, alias_dict: (
    map_dataset_columns(list(df.columns), "CDR" if "caller_number" in alias_dict else "IPDR")["mapping"],
    map_dataset_columns(list(df.columns), "CDR" if "caller_number" in alias_dict else "IPDR")["unmapped"]
)

# ==============================================================================
# DETERMINISTIC ASSISTANT INTENT ROUTER
# ==============================================================================
def process_assistant_query(query: str, cdr_df: pd.DataFrame, ipdr_df: pd.DataFrame):
    """Deterministic natural-language intent router mapping questions to local Pandas operations."""
    q = query.strip().lower()
    phone_numbers = re.findall(r'\b\d{8,15}\b', q)
    
    # 1. Dataset summary
    if any(k in q for k in ["summarise", "summarize", "overview", "dataset summary", "summary of data"]):
        valid_cdr = len(cdr_df[cdr_df["validation_status"] == "VALID"]) if not cdr_df.empty else 0
        review_cdr = len(cdr_df[cdr_df["validation_status"] == "REVIEW"]) if not cdr_df.empty else 0
        valid_ipdr = len(ipdr_df[ipdr_df["validation_status"] == "VALID"]) if not ipdr_df.empty else 0
        review_ipdr = len(ipdr_df[ipdr_df["validation_status"] == "REVIEW"]) if not ipdr_df.empty else 0
        
        unique_callers = set(cdr_df["caller_number"].dropna().unique()).union(set(cdr_df["receiver_number"].dropna().unique())) if not cdr_df.empty else set()
        unique_callers.discard("")
        unique_subs = ipdr_df["subscriber_id"].nunique() if not ipdr_df.empty else 0
        
        summary_data = [
            {"Dataset": "CDR (Call Detail Records)", "Total Records": len(cdr_df), "VALID": valid_cdr, "REVIEW Required": review_cdr, "Unique Entities": len(unique_callers)},
            {"Dataset": "IPDR (Internet Protocol Records)", "Total Records": len(ipdr_df), "VALID": valid_ipdr, "REVIEW Required": review_ipdr, "Unique Entities": unique_subs}
        ]
        
        text = f"**Dataset Health & Record Summary**\n- Currently loaded CDR records: **{len(cdr_df)}** ({valid_cdr} VALID, {review_cdr} REVIEW)\n- Currently loaded IPDR sessions: **{len(ipdr_df)}** ({valid_ipdr} VALID, {review_ipdr} REVIEW)\n- Total distinct phone identifiers tracked: **{len(unique_callers)}**\n- Total subscribers tracked in IPDR: **{unique_subs}**"
        return text, pd.DataFrame(summary_data), "summary"
        
    # 2. Shared contacts / common contacts between two identifiers
    elif ("common" in q or "shared" in q or "mutual" in q) and len(phone_numbers) >= 2:
        p1, p2 = phone_numbers[0], phone_numbers[1]
        valid_cdr = cdr_df[cdr_df["validation_status"] == "VALID"].copy()
        
        # Contacts of p1
        c1_out = set(valid_cdr[valid_cdr["caller_number"] == p1]["receiver_number"])
        c1_in = set(valid_cdr[valid_cdr["receiver_number"] == p1]["caller_number"])
        contacts_1 = (c1_out | c1_in) - {p1, ""}
        
        # Contacts of p2
        c2_out = set(valid_cdr[valid_cdr["caller_number"] == p2]["receiver_number"])
        c2_in = set(valid_cdr[valid_cdr["receiver_number"] == p2]["caller_number"])
        contacts_2 = (c2_out | c2_in) - {p2, ""}
        
        shared = contacts_1.intersection(contacts_2)
        
        if not shared:
            return f"No common contacts found between **{p1}** and **{p2}** in the valid CDR records.", pd.DataFrame(), "shared_contacts"
            
        rows = []
        for contact in sorted(list(shared)):
            calls_with_p1 = len(valid_cdr[((valid_cdr["caller_number"] == p1) & (valid_cdr["receiver_number"] == contact)) | ((valid_cdr["caller_number"] == contact) & (valid_cdr["receiver_number"] == p1))])
            calls_with_p2 = len(valid_cdr[((valid_cdr["caller_number"] == p2) & (valid_cdr["receiver_number"] == contact)) | ((valid_cdr["caller_number"] == contact) & (valid_cdr["receiver_number"] == p2))])
            rows.append({
                "Common Contact Identifier": contact,
                f"Interactions with {p1}": calls_with_p1,
                f"Interactions with {p2}": calls_with_p2,
                "Total Correlated Events": calls_with_p1 + calls_with_p2
            })
            
        res_df = pd.DataFrame(rows).sort_values("Total Correlated Events", ascending=False)
        text = f"Found **{len(shared)} common contact(s)** between **{p1}** and **{p2}** based on observed CDR pairs."
        return text, res_df, "shared_contacts"
        
    # 3. Timeline for specific phone number
    elif ("timeline" in q or "activity" in q or "history" in q or "calls" in q) and len(phone_numbers) >= 1:
        target = phone_numbers[0]
        valid_cdr = cdr_df[cdr_df["validation_status"] == "VALID"].copy()
        
        matching = valid_cdr[(valid_cdr["caller_number"] == target) | (valid_cdr["receiver_number"] == target)].copy()
        if matching.empty:
            return f"No valid CDR events found for identifier **{target}**.", pd.DataFrame(), "timeline"
            
        matching = matching.sort_values("parsed_timestamp", ascending=True)
        
        timeline_rows = []
        for idx, row in matching.iterrows():
            is_caller = (row["caller_number"] == target)
            role = "Outgoing (Caller)" if is_caller else "Incoming (Receiver)"
            counterparty = row["receiver_number"] if is_caller else row["caller_number"]
            timeline_rows.append({
                "Timestamp": row["event_timestamp"],
                "Direction/Role": role,
                "Counterparty": counterparty,
                "Duration (s)": int(row.get("duration_seconds", 0)),
                "Call Type": row.get("call_type", "UNKNOWN"),
                "Status": row.get("call_status", "UNKNOWN"),
                "Cell Tower": row.get("cell_tower_id", "UNKNOWN")
            })
            
        res_df = pd.DataFrame(timeline_rows)
        text = f"Chronological timeline for identifier **{target}** contains **{len(res_df)} record(s)** across the dataset."
        return text, res_df, "timeline"
        
    # 4. Top callers / highest activity
    elif any(k in q for k in ["top caller", "top callers", "highest caller", "most calls", "caller ranking", "rank callers"]):
        valid_cdr = cdr_df[cdr_df["validation_status"] == "VALID"].copy()
        if valid_cdr.empty:
            return "No valid CDR records available for analysis.", pd.DataFrame(), "top_callers"
            
        top_df = valid_cdr.groupby("caller_number").agg(
            total_records=("receiver_number", "count"),
            distinct_recipients=("receiver_number", "nunique"),
            total_duration_sec=("duration_seconds", "sum"),
            avg_duration_sec=("duration_seconds", "mean")
        ).reset_index()
        
        top_df = top_df.sort_values("total_records", ascending=False).rename(columns={
            "caller_number": "Calling Party (caller_number)",
            "total_records": "Outgoing Records Count",
            "distinct_recipients": "Distinct Counterparties",
            "total_duration_sec": "Total Duration (sec)",
            "avg_duration_sec": "Avg Duration (sec)"
        })
        top_df["Avg Duration (sec)"] = top_df["Avg Duration (sec)"].round(1)
        top_df["Total Duration (sec)"] = top_df["Total Duration (sec)"].astype(int)
        
        text = f"Top caller ranking by outgoing record count. Displaying **{len(top_df)}** active calling parties from valid CDR records."
        return text, top_df, "top_callers"
        
    # 5. IPDR data volume by subscriber
    elif any(k in q for k in ["ipdr", "volume", "byte", "bytes", "data usage", "internet volume", "subscriber data"]):
        valid_ipdr = ipdr_df[ipdr_df["validation_status"] == "VALID"].copy()
        if valid_ipdr.empty:
            return "No valid IPDR records available for analysis.", pd.DataFrame(), "ipdr_volume"
            
        grouped = valid_ipdr.groupby("subscriber_id").agg(
            total_sessions=("session_start", "count"),
            total_up_bytes=("upload_bytes", "sum"),
            total_down_bytes=("download_bytes", "sum")
        ).reset_index()
        
        grouped["Total Bytes"] = grouped["total_up_bytes"] + grouped["total_down_bytes"]
        grouped["Upload (MB)"] = (grouped["total_up_bytes"] / (1024 * 1024)).round(2)
        grouped["Download (MB)"] = (grouped["total_down_bytes"] / (1024 * 1024)).round(2)
        grouped["Total (MB)"] = (grouped["Total Bytes"] / (1024 * 1024)).round(2)
        
        res_df = grouped[["subscriber_id", "total_sessions", "Upload (MB)", "Download (MB)", "Total (MB)"]].sort_values("Total (MB)", ascending=False)
        res_df = res_df.rename(columns={"subscriber_id": "Subscriber ID", "total_sessions": "Session Count"})
        
        text = f"Internet Protocol Detail Record (IPDR) volume aggregation by subscriber across **{len(res_df)}** subscriber(s)."
        return text, res_df, "ipdr_volume"
        
    # Fallback
    else:
        text = """
**Supported Deterministic Queries:**
- 📊 **Top Callers**: `"Show the top callers by number of records"`
- ⏱️ **Identifier Timeline**: `"Show timeline for 9000000001"`
- 🤝 **Shared Contacts**: `"Find common contacts between 9000000001 and 9000000002"`
- 📋 **Dataset Quality Summary**: `"Summarise the uploaded datasets"`
- 🌐 **IPDR Usage**: `"Show IPDR data volume by subscriber"`

*Tip: Please ensure phone identifiers contain 8 to 15 digits.*
"""
        return text, pd.DataFrame(), "unknown"
