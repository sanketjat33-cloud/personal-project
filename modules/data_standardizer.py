import re
import datetime
import pandas as pd
import numpy as np

from modules.column_mapper import (
    CDR_CANONICAL_ALIASES,
    IPDR_CANONICAL_ALIASES,
    detect_file_type,
    map_dataset_columns
)
from modules.data_validator import (
    validate_cdr_dataframe,
    validate_ipdr_dataframe
)

# ==============================================================================
# DATA CLEANING UTILITIES
# ==============================================================================

def clean_phone_number(val) -> str:
    """
    Cleans phone/subscriber identifiers while preserving leading digits, country codes,
    and alphanumeric subscriber IDs (e.g. SUB-1001).
    Handles Excel integers and floating point conversions without truncating.
    """
    if pd.isna(val) or val is None:
        return ""
    if isinstance(val, (int, np.integer)):
        return str(val)
    if isinstance(val, (float, np.floating)):
        if np.isnan(val):
            return ""
        if val.is_integer():
            return str(int(val))
        return str(val).split('.')[0]
        
    val_str = str(val).strip()
    if val_str.endswith(".0"):
        val_str = val_str[:-2]
    # If it contains letters (e.g. SUB-1001), preserve it as an alphanumeric subscriber/account ID
    if re.search(r'[a-zA-Z]', val_str):
        return val_str
    # Otherwise keep digits only (preserving country code)
    digits = re.sub(r'\D', '', val_str)
    return digits

def combine_date_and_time(dates: pd.Series, times: pd.Series) -> pd.Series:
    """
    Combines separate Date and Time columns into a unified datetime series.
    Supports Excel-native timestamps, datetime.time objects, and formatted strings.
    """
    combined_datetimes = []
    
    for d, t in zip(dates, times):
        if pd.isna(d) or pd.isna(t) or d is None or t is None:
            combined_datetimes.append(pd.NaT)
            continue
            
        # 1. Date string extraction (YYYY-MM-DD)
        if isinstance(d, (pd.Timestamp, datetime.datetime, datetime.date)):
            d_str = d.strftime("%Y-%m-%d")
        else:
            d_parsed = pd.to_datetime(d, errors="coerce")
            if pd.notna(d_parsed):
                d_str = d_parsed.strftime("%Y-%m-%d")
            else:
                d_str = str(d).strip()
                
        # 2. Time string extraction (HH:MM:SS)
        if isinstance(t, datetime.time):
            t_str = t.strftime("%H:%M:%S")
        elif isinstance(t, (pd.Timestamp, datetime.datetime)):
            t_str = t.strftime("%H:%M:%S")
        else:
            t_str = str(t).strip()
            
        full_str = f"{d_str} {t_str}"
        parsed_dt = pd.to_datetime(full_str, errors="coerce")
        combined_datetimes.append(parsed_dt)
        
    return pd.Series(combined_datetimes)

# ==============================================================================
# STANDARDIZATION ENGINE PIPELINE
# ==============================================================================

class StandardizationResult:
    """Encapsulates the output of the data standardization engine."""
    def __init__(
        self,
        standardized_df: pd.DataFrame,
        original_df: pd.DataFrame,
        dataset_type: str,
        mapping: dict,
        confidence: dict,
        decisions: list,
        unmapped_columns: list,
        valid_count: int,
        review_count: int,
        error_message: str = ""
    ):
        self.standardized_df = standardized_df
        self.original_df = original_df
        self.dataset_type = dataset_type
        self.mapping = mapping
        self.confidence = confidence
        self.decisions = decisions
        self.unmapped_columns = unmapped_columns
        self.total_records = len(original_df)
        self.valid_count = valid_count
        self.review_count = review_count
        self.error_message = error_message
        self.is_successful = (error_message == "")

def standardize_cdr_dataset(
    raw_df: pd.DataFrame,
    custom_mapping: dict = None
) -> StandardizationResult:
    """
    Standardizes a CDR DataFrame:
    - Applies automatic or user-defined column mapping
    - Combines split Call Date + Call Time into event_timestamp if needed
    - Preserves country codes and phone numbers
    - Preserves all extra metadata (IMEI, IMSI, Cell ID, LAC, Tower Location, Operator, Record ID, etc.)
    - Runs data validation and tags rows as VALID or REVIEW
    """
    original_df = raw_df.copy()
    columns = list(original_df.columns)
    
    # 1. Determine mapping
    map_meta = map_dataset_columns(columns, dataset_type="CDR")
    mapping = custom_mapping if custom_mapping is not None else map_meta["mapping"]
    confidence = map_meta["confidence"]
    decisions = list(map_meta["decisions"])
    unmapped = [c for c in columns if c not in mapping]
    
    # Invert mapping to find source column for each canonical target
    canonical_to_source = {v: k for k, v in mapping.items()}
    
    std_df = pd.DataFrame()
    
    # 2. Check & combine split Date and Time
    split_date_col = canonical_to_source.get("call_date")
    split_time_col = canonical_to_source.get("call_time")
    
    if "event_timestamp" not in canonical_to_source:
        if split_date_col and split_time_col:
            std_df["parsed_timestamp"] = combine_date_and_time(
                original_df[split_date_col],
                original_df[split_time_col]
            )
            # Create string event_timestamp
            std_df["event_timestamp"] = std_df["parsed_timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("INVALID_TIMESTAMP")
            decisions.append(f"Combined '{split_date_col}' and '{split_time_col}' into canonical 'event_timestamp'")
        else:
            return StandardizationResult(
                standardized_df=pd.DataFrame(),
                original_df=original_df,
                dataset_type="CDR",
                mapping=mapping,
                confidence=confidence,
                decisions=decisions,
                unmapped_columns=unmapped,
                valid_count=0,
                review_count=len(original_df),
                error_message="Missing required CDR column(s): 'event_timestamp' (or separate 'Call Date' + 'Call Time')"
            )
    else:
        source_ts_col = canonical_to_source["event_timestamp"]
        std_df["parsed_timestamp"] = pd.to_datetime(original_df[source_ts_col], errors="coerce")
        std_df["event_timestamp"] = std_df["parsed_timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna(original_df[source_ts_col].astype(str))
        
    # 3. Required caller and receiver
    if "caller_number" not in canonical_to_source:
        return StandardizationResult(
            standardized_df=pd.DataFrame(),
            original_df=original_df,
            dataset_type="CDR",
            mapping=mapping,
            confidence=confidence,
            decisions=decisions,
            unmapped_columns=unmapped,
            valid_count=0,
            review_count=len(original_df),
            error_message="Missing required CDR column: 'caller_number' (A-Party / Calling Number)"
        )
    if "receiver_number" not in canonical_to_source:
        return StandardizationResult(
            standardized_df=pd.DataFrame(),
            original_df=original_df,
            dataset_type="CDR",
            mapping=mapping,
            confidence=confidence,
            decisions=decisions,
            unmapped_columns=unmapped,
            valid_count=0,
            review_count=len(original_df),
            error_message="Missing required CDR column: 'receiver_number' (B-Party / Called Number)"
        )
        
    std_df["caller_number"] = original_df[canonical_to_source["caller_number"]].apply(clean_phone_number)
    std_df["receiver_number"] = original_df[canonical_to_source["receiver_number"]].apply(clean_phone_number)
    
    # 4. Optional canonical columns
    if "duration_seconds" in canonical_to_source:
        std_df["duration_seconds"] = pd.to_numeric(original_df[canonical_to_source["duration_seconds"]], errors="coerce").fillna(0).astype(int)
    else:
        std_df["duration_seconds"] = 0
        
    if "call_type" in canonical_to_source:
        std_df["call_type"] = original_df[canonical_to_source["call_type"]].fillna("UNKNOWN").astype(str).str.strip().str.upper()
    else:
        std_df["call_type"] = "UNKNOWN"
        
    if "call_status" in canonical_to_source:
        std_df["call_status"] = original_df[canonical_to_source["call_status"]].fillna("UNKNOWN").astype(str).str.strip().str.upper()
    else:
        std_df["call_status"] = "UNKNOWN"
        
    if "cell_tower_id" in canonical_to_source:
        std_df["cell_tower_id"] = original_df[canonical_to_source["cell_tower_id"]].fillna("UNKNOWN").astype(str).str.strip()
    else:
        std_df["cell_tower_id"] = "UNKNOWN"
        
    # Extended telecom fields (Direction, Record ID, LAC, Tower Location, IMEI, IMSI, Operator)
    for extra_field in ["record_id", "direction", "lac", "tower_location", "imei", "imsi", "operator"]:
        if extra_field in canonical_to_source:
            std_df[extra_field] = original_df[canonical_to_source[extra_field]].fillna("").astype(str).str.strip()
            
    # 5. Preserve any remaining unmapped source columns
    mapped_sources = set(mapping.keys())
    for col in original_df.columns:
        if col not in mapped_sources and col not in std_df.columns:
            std_df[col] = original_df[col]
            
    # 6. Apply validation
    validated_df = validate_cdr_dataframe(std_df)
    
    # 7. Order columns cleanly
    canonical_first = [
        "caller_number", "receiver_number", "event_timestamp", "parsed_timestamp",
        "duration_seconds", "call_type", "call_status", "cell_tower_id",
        "validation_status", "validation_errors", "review_reason"
    ]
    present_canonicals = [c for c in canonical_first if c in validated_df.columns]
    other_cols = [c for c in validated_df.columns if c not in present_canonicals]
    validated_df = validated_df[present_canonicals + other_cols]
    
    valid_count = int((validated_df["validation_status"] == "VALID").sum())
    review_count = len(validated_df) - valid_count
    
    return StandardizationResult(
        standardized_df=validated_df,
        original_df=original_df,
        dataset_type="CDR",
        mapping=mapping,
        confidence=confidence,
        decisions=decisions,
        unmapped_columns=unmapped,
        valid_count=valid_count,
        review_count=review_count,
        error_message=""
    )

def standardize_ipdr_dataset(
    raw_df: pd.DataFrame,
    custom_mapping: dict = None
) -> StandardizationResult:
    """
    Standardizes an IPDR DataFrame:
    - Applies automatic or user-defined column mapping
    - Maps Private IP to ip_address as primary, preserves Public IP separately
    - Preserves ports, protocol, domain, duration, upload/download bytes, IMEI, IMSI, APN, etc.
    - Runs data validation and tags rows as VALID or REVIEW
    """
    original_df = raw_df.copy()
    columns = list(original_df.columns)
    
    map_meta = map_dataset_columns(columns, dataset_type="IPDR")
    mapping = custom_mapping if custom_mapping is not None else map_meta["mapping"]
    confidence = map_meta["confidence"]
    decisions = list(map_meta["decisions"])
    unmapped = [c for c in columns if c not in mapping]
    
    canonical_to_source = {v: k for k, v in mapping.items()}
    std_df = pd.DataFrame()
    
    # 1. Required subscriber_id (MSISDN)
    if "subscriber_id" not in canonical_to_source:
        return StandardizationResult(
            standardized_df=pd.DataFrame(),
            original_df=original_df,
            dataset_type="IPDR",
            mapping=mapping,
            confidence=confidence,
            decisions=decisions,
            unmapped_columns=unmapped,
            valid_count=0,
            review_count=len(original_df),
            error_message="Missing required IPDR column: 'subscriber_id' (MSISDN / Account ID)"
        )
    std_df["subscriber_id"] = original_df[canonical_to_source["subscriber_id"]].apply(clean_phone_number)
    
    # 2. IP Address Logic (Private IP primary, Public IP fallback)
    private_src = canonical_to_source.get("private_ip")
    public_src = canonical_to_source.get("public_ip")
    
    if private_src:
        std_df["ip_address"] = original_df[private_src].fillna("").astype(str).str.strip()
        std_df["private_ip"] = original_df[private_src].fillna("").astype(str).str.strip()
    elif public_src:
        std_df["ip_address"] = original_df[public_src].fillna("").astype(str).str.strip()
        decisions.append(f"Used Public IP '{public_src}' as fallback for primary 'ip_address'")
    else:
        return StandardizationResult(
            standardized_df=pd.DataFrame(),
            original_df=original_df,
            dataset_type="IPDR",
            mapping=mapping,
            confidence=confidence,
            decisions=decisions,
            unmapped_columns=unmapped,
            valid_count=0,
            review_count=len(original_df),
            error_message="Missing required IPDR column: 'ip_address' (Private IP or Public IP)"
        )
        
    if public_src:
        std_df["public_ip"] = original_df[public_src].fillna("").astype(str).str.strip()
    else:
        std_df["public_ip"] = "N/A"
        
    # 3. Timestamps
    if "session_start" not in canonical_to_source or "session_end" not in canonical_to_source:
        return StandardizationResult(
            standardized_df=pd.DataFrame(),
            original_df=original_df,
            dataset_type="IPDR",
            mapping=mapping,
            confidence=confidence,
            decisions=decisions,
            unmapped_columns=unmapped,
            valid_count=0,
            review_count=len(original_df),
            error_message="Missing required IPDR session timestamp column(s): 'session_start' and/or 'session_end'"
        )
        
    std_df["parsed_start"] = pd.to_datetime(original_df[canonical_to_source["session_start"]], errors="coerce")
    std_df["parsed_end"] = pd.to_datetime(original_df[canonical_to_source["session_end"]], errors="coerce")
    
    std_df["session_start"] = std_df["parsed_start"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna(original_df[canonical_to_source["session_start"]].astype(str))
    std_df["session_end"] = std_df["parsed_end"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna(original_df[canonical_to_source["session_end"]].astype(str))
    
    # 4. Bytes & Duration
    if "upload_bytes" in canonical_to_source:
        std_df["upload_bytes"] = pd.to_numeric(original_df[canonical_to_source["upload_bytes"]], errors="coerce").fillna(0).astype(int)
    else:
        std_df["upload_bytes"] = 0
        
    if "download_bytes" in canonical_to_source:
        std_df["download_bytes"] = pd.to_numeric(original_df[canonical_to_source["download_bytes"]], errors="coerce").fillna(0).astype(int)
    else:
        std_df["download_bytes"] = 0
        
    if "duration_seconds" in canonical_to_source:
        std_df["duration_seconds"] = pd.to_numeric(original_df[canonical_to_source["duration_seconds"]], errors="coerce").fillna(0).astype(int)
        
    # 5. Extended IPDR fields
    extended_fields = [
        "protocol", "service_domain", "source_port", "destination_ip",
        "destination_port", "network_id", "imei", "imsi", "apn", "record_id"
    ]
    for field in extended_fields:
        if field in canonical_to_source:
            std_df[field] = original_df[canonical_to_source[field]].fillna("").astype(str).str.strip()
        else:
            if field == "protocol":
                std_df["protocol"] = "UNKNOWN"
            elif field == "network_id":
                std_df["network_id"] = "UNKNOWN"
                
    # 6. Preserve unmapped columns
    mapped_sources = set(mapping.keys())
    for col in original_df.columns:
        if col not in mapped_sources and col not in std_df.columns:
            std_df[col] = original_df[col]
            
    # 7. Validation
    validated_df = validate_ipdr_dataframe(std_df)
    # 8. Order canonical IPDR columns cleanly
    canonical_first_ipdr = [
        "subscriber_id", "ip_address", "session_start", "session_end",
        "parsed_start", "parsed_end", "upload_bytes", "download_bytes",
        "protocol", "network_id", "private_ip", "public_ip",
        "validation_status", "validation_errors", "review_reason"
    ]
    present_canonicals_ipdr = [c for c in canonical_first_ipdr if c in validated_df.columns]
    other_cols_ipdr = [c for c in validated_df.columns if c not in present_canonicals_ipdr]
    validated_df = validated_df[present_canonicals_ipdr + other_cols_ipdr]
    
    valid_count = int((validated_df["validation_status"] == "VALID").sum())
    review_count = len(validated_df) - valid_count
    
    return StandardizationResult(
        standardized_df=validated_df,
        original_df=original_df,
        dataset_type="IPDR",
        mapping=mapping,
        confidence=confidence,
        decisions=decisions,
        unmapped_columns=unmapped,
        valid_count=valid_count,
        review_count=review_count,
        error_message=""
    )
