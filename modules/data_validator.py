import re
import ipaddress
import pandas as pd
import numpy as np

def is_valid_ip(ip_str: str) -> bool:
    """Validates IPv4 or IPv6 address string format."""
    if not ip_str or pd.isna(ip_str):
        return False
    clean_ip = str(ip_str).strip()
    try:
        ipaddress.ip_address(clean_ip)
        return True
    except ValueError:
        return False

def validate_cdr_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies comprehensive telecom validation rules to standardized CDR records.
    Adds 'validation_status' ('VALID' or 'REVIEW') and 'validation_errors' columns.
    """
    df = df.copy()
    
    statuses = []
    errors_list = []
    
    # Track duplicates across key CDR event identifiers
    duplicate_mask = df.duplicated(
        subset=["caller_number", "receiver_number", "event_timestamp", "duration_seconds"],
        keep=False
    ) if all(c in df.columns for c in ["caller_number", "receiver_number", "event_timestamp", "duration_seconds"]) else pd.Series(False, index=df.index)
    
    for idx, row in df.iterrows():
        errs = []
        
        # 1. Caller & Receiver check
        caller = str(row.get("caller_number", "")).strip()
        receiver = str(row.get("receiver_number", "")).strip()
        
        if not caller or caller == "nan" or caller == "":
            errs.append("Missing or blank caller identifier (caller_number)")
        if not receiver or receiver == "nan" or receiver == "":
            errs.append("Missing or blank receiver identifier (receiver_number)")
            
        # 2. Timestamp check
        parsed_ts = row.get("parsed_timestamp", pd.NaT)
        if pd.isna(parsed_ts):
            errs.append("Invalid or unparseable event timestamp")
            
        # 3. Duration check
        duration = row.get("duration_seconds", 0)
        try:
            dur_num = float(duration)
            if dur_num < 0:
                errs.append("Negative call duration recorded")
        except (ValueError, TypeError):
            errs.append("Non-numeric call duration value")
            
        # 4. Duplicate check
        if duplicate_mask.iloc[idx]:
            errs.append("Duplicate CDR event detected")
            
        if errs:
            statuses.append("REVIEW")
            errors_list.append("; ".join(errs))
        else:
            statuses.append("VALID")
            errors_list.append("None")
            
    df["validation_status"] = statuses
    df["validation_errors"] = errors_list
    return df

def validate_ipdr_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies comprehensive network session validation rules to standardized IPDR records.
    Adds 'validation_status' ('VALID' or 'REVIEW') and 'validation_errors' columns.
    """
    df = df.copy()
    
    statuses = []
    errors_list = []
    
    # Duplicate check across sessions
    duplicate_mask = df.duplicated(
        subset=["subscriber_id", "ip_address", "session_start", "session_end"],
        keep=False
    ) if all(c in df.columns for c in ["subscriber_id", "ip_address", "session_start", "session_end"]) else pd.Series(False, index=df.index)
    
    for idx, row in df.iterrows():
        errs = []
        
        # 1. Subscriber check
        sub_id = str(row.get("subscriber_id", "")).strip()
        if not sub_id or sub_id == "nan" or sub_id == "":
            errs.append("Missing or blank subscriber ID")
            
        # 2. IP address check
        ip_addr = str(row.get("ip_address", "")).strip()
        if not ip_addr or ip_addr == "nan" or ip_addr == "":
            errs.append("Missing assigned IP address")
        elif not is_valid_ip(ip_addr):
            errs.append(f"Malformed IP address format: '{ip_addr}'")
            
        # 3. Timestamp checks
        parsed_start = row.get("parsed_start", pd.NaT)
        parsed_end = row.get("parsed_end", pd.NaT)
        
        if pd.isna(parsed_start):
            errs.append("Invalid session_start timestamp")
        if pd.isna(parsed_end):
            errs.append("Invalid session_end timestamp")
            
        if pd.notna(parsed_start) and pd.notna(parsed_end):
            if parsed_end < parsed_start:
                errs.append("Session end timestamp is earlier than session start")
                
        # 4. Upload & Download bytes checks
        up_bytes = row.get("upload_bytes", 0)
        down_bytes = row.get("download_bytes", 0)
        try:
            if float(up_bytes) < 0:
                errs.append("Negative upload bytes recorded")
        except (ValueError, TypeError):
            errs.append("Non-numeric upload bytes")
            
        try:
            if float(down_bytes) < 0:
                errs.append("Negative download bytes recorded")
        except (ValueError, TypeError):
            errs.append("Non-numeric download bytes")
            
        # 5. Duplicate check
        if duplicate_mask.iloc[idx]:
            errs.append("Duplicate IPDR session detected")
            
        if errs:
            statuses.append("REVIEW")
            errors_list.append("; ".join(errs))
        else:
            statuses.append("VALID")
            errors_list.append("None")
            
    df["validation_status"] = statuses
    df["validation_errors"] = errors_list
    return df
