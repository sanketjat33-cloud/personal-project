import os
import sys
import pandas as pd
import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.file_reader import read_telecom_file
from modules.column_mapper import detect_file_type, map_dataset_columns
from modules.data_standardizer import (
    standardize_cdr_dataset,
    standardize_ipdr_dataset,
    clean_phone_number,
    combine_date_and_time
)

def test_actual_cdr_standardization():
    print("\n--- Testing Actual CDR File: CDR_test_20_records.xlsx ---")
    cdr_file_path = os.path.join("data", "CDR_test_20_records.xlsx")
    assert os.path.exists(cdr_file_path), f"File not found: {cdr_file_path}"
    
    with open(cdr_file_path, "rb") as f:
        raw_df, sheets, active_sheet = read_telecom_file(f, "CDR_test_20_records.xlsx")
        
    assert len(raw_df) == 20, f"Expected 20 records, got {len(raw_df)}"
    assert active_sheet == "CDR", f"Expected active sheet 'CDR', got {active_sheet}"
    
    # Verify Automatic File Type Detection
    detected_type, conf = detect_file_type(list(raw_df.columns))
    assert detected_type == "CDR", f"Expected detected type 'CDR', got {detected_type}"
    assert conf >= 0.8, f"Expected high confidence, got {conf}"
    print(f" PASS: Detected file type: {detected_type} (confidence: {conf})")
    
    # Standardize
    res = standardize_cdr_dataset(raw_df)
    assert res.is_successful, f"CDR standardization failed with error: {res.error_message}"
    std_df = res.standardized_df
    
    # 1. All 20 records read
    assert len(std_df) == 20, f"Expected 20 records, got {len(std_df)}"
    print(f" PASS: All 20 records read and standardized.")
    
    # 2. A-Party (Calling) maps to caller_number and preserves digits/country code
    assert "caller_number" in std_df.columns
    first_caller = str(std_df["caller_number"].iloc[0])
    assert first_caller.startswith("91"), f"Country code lost: {first_caller}"
    assert first_caller == "919810000105", f"Unexpected caller: {first_caller}"
    print(f" PASS: A-Party mapped to caller_number: {first_caller}")
    
    # 3. B-Party (Called) maps to receiver_number
    assert "receiver_number" in std_df.columns
    first_receiver = str(std_df["receiver_number"].iloc[0])
    assert first_receiver == "919820000204", f"Unexpected receiver: {first_receiver}"
    print(f" PASS: B-Party mapped to receiver_number: {first_receiver}")
    
    # 4. Call Date + Call Time combine correctly into event_timestamp
    assert "event_timestamp" in std_df.columns
    first_ts = std_df["event_timestamp"].iloc[0]
    assert first_ts == "2026-11-10 06:24:00", f"Unexpected combined timestamp: {first_ts}"
    assert pd.notna(std_df["parsed_timestamp"].iloc[0]), "parsed_timestamp is NaT"
    print(f" PASS: Call Date + Call Time successfully combined into: {first_ts}")
    
    # 5. Duration and optional metadata preserved
    assert "duration_seconds" in std_df.columns
    assert std_df["duration_seconds"].iloc[0] == 515
    assert "direction" in std_df.columns
    assert std_df["direction"].iloc[0] == "MOC"
    assert "lac" in std_df.columns
    assert "tower_location" in std_df.columns
    assert "imei" in std_df.columns
    assert "imsi" in std_df.columns
    assert "operator" in std_df.columns
    assert std_df["operator"].iloc[0] == "Airtel"
    print(f" PASS: Metadata preserved (duration, direction, lac, tower_location, imei, imsi, operator).")
    
    # 6. Validation status
    assert res.valid_count == 20
    assert res.review_count == 0
    print(f" PASS: Validation successful (20 VALID, 0 REVIEW).")

def test_actual_ipdr_standardization():
    print("\n--- Testing Actual IPDR File: IPDR_test_20_records.xlsx ---")
    ipdr_file_path = os.path.join("data", "IPDR_test_20_records.xlsx")
    assert os.path.exists(ipdr_file_path), f"File not found: {ipdr_file_path}"
    
    with open(ipdr_file_path, "rb") as f:
        raw_df, sheets, active_sheet = read_telecom_file(f, "IPDR_test_20_records.xlsx")
        
    assert len(raw_df) == 20, f"Expected 20 records, got {len(raw_df)}"
    assert active_sheet == "IPDR", f"Expected active sheet 'IPDR', got {active_sheet}"
    
    # Verify Automatic File Type Detection
    detected_type, conf = detect_file_type(list(raw_df.columns))
    assert detected_type == "IPDR", f"Expected detected type 'IPDR', got {detected_type}"
    print(f" PASS: Detected file type: {detected_type} (confidence: {conf})")
    
    # Standardize
    res = standardize_ipdr_dataset(raw_df)
    assert res.is_successful, f"IPDR standardization failed: {res.error_message}"
    std_df = res.standardized_df
    
    # 1. All 20 records read
    assert len(std_df) == 20, f"Expected 20 records, got {len(std_df)}"
    print(f" PASS: All 20 records read and standardized.")
    
    # 2. MSISDN maps to subscriber_id
    assert "subscriber_id" in std_df.columns
    first_sub = str(std_df["subscriber_id"].iloc[0])
    assert first_sub == "919810000101", f"Unexpected subscriber: {first_sub}"
    print(f" PASS: MSISDN mapped to subscriber_id: {first_sub}")
    
    # 3. Private IP maps to ip_address as primary, Public IP preserved
    assert "ip_address" in std_df.columns
    assert "private_ip" in std_df.columns
    assert "public_ip" in std_df.columns
    assert std_df["ip_address"].iloc[0] == "100.64.151.56"
    assert std_df["private_ip"].iloc[0] == "100.64.151.56"
    assert std_df["public_ip"].iloc[0] == "203.0.113.248"
    print(f" PASS: Private IP ('100.64.151.56') -> ip_address; Public IP ('203.0.113.248') preserved.")
    
    # 4. Session Start and Session End map correctly
    assert "session_start" in std_df.columns
    assert "session_end" in std_df.columns
    assert std_df["session_start"].iloc[0] == "2026-11-10 14:34:55"
    assert std_df["session_end"].iloc[0] == "2026-11-10 14:57:33"
    print(f" PASS: Session Start and End mapped cleanly.")
    
    # 5. Upload & Download bytes mapped correctly
    assert "upload_bytes" in std_df.columns
    assert "download_bytes" in std_df.columns
    assert std_df["upload_bytes"].iloc[0] == 1216629
    assert std_df["download_bytes"].iloc[0] == 72782208
    print(f" PASS: Upload ({std_df['upload_bytes'].iloc[0]}) & Download ({std_df['download_bytes'].iloc[0]}) bytes mapped.")
    
    # 6. Ports, protocol, IMEI, IMSI, APN, domain preserved
    assert "source_port" in std_df.columns
    assert "destination_ip" in std_df.columns
    assert "destination_port" in std_df.columns
    assert "protocol" in std_df.columns
    assert "service_domain" in std_df.columns
    assert "network_id" in std_df.columns
    assert "imei" in std_df.columns
    assert "imsi" in std_df.columns
    assert "apn" in std_df.columns
    assert std_df["apn"].iloc[0] == "internet"
    print(f" PASS: Extended network metadata preserved (ports, domain, imei, imsi, apn).")
    
    # 7. Validation status
    assert res.valid_count == 20
    assert res.review_count == 0
    print(f" PASS: Validation successful (20 VALID, 0 REVIEW).")

if __name__ == "__main__":
    print("==================================================")
    print("RUNNING STANDARDIZATION ENGINE TESTS")
    print("==================================================")
    test_actual_cdr_standardization()
    test_actual_ipdr_standardization()
    print("\n==================================================")
    print("ALL STANDARDIZATION TESTS PASSED (100% SUCCESS)!")
    print("==================================================")
