import os
import sys
import json
import pandas as pd
import networkx as nx

# Add current project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import functions from engine.py
from engine import (
    standardize_cdr,
    standardize_ipdr,
    process_assistant_query,
    read_tabular_file,
    to_excel_bytes,
    CDR_ALIASES,
    IPDR_ALIASES
)

def run_all_tests():
    print("==================================================")
    print("STARTING CDR/IPDR INTELLIGENCE ACCEPTANCE TESTS")
    print("==================================================")
    
    passed = 0
    total = 12 # Now 12 tests including Excel CDR & IPDR verification!
    
    # --------------------------------------------------------------------------
    # T01: Bundled Sample Datasets Exist & Have Required Rows
    # --------------------------------------------------------------------------
    print("\n[T01] Testing Bundled Sample Datasets...")
    assert os.path.exists("data/sample_cdr.csv"), "sample_cdr.csv missing"
    assert os.path.exists("data/sample_ipdr.csv"), "sample_ipdr.csv missing"
    cdr_raw = pd.read_csv("data/sample_cdr.csv")
    ipdr_raw = pd.read_csv("data/sample_ipdr.csv")
    assert len(cdr_raw) == 220, f"Expected 220 CDR rows, got {len(cdr_raw)}"
    assert len(ipdr_raw) == 100, f"Expected 100 IPDR rows, got {len(ipdr_raw)}"
    print(f" PASS: Bundled CDR has {len(cdr_raw)} rows, IPDR has {len(ipdr_raw)} rows.")
    passed += 1

    # --------------------------------------------------------------------------
    # T02: Upload & Standardize Valid CDR with Aliases (CSV)
    # --------------------------------------------------------------------------
    print("\n[T02] Testing CDR Alias Mapping & Standardization (CSV)...")
    custom_cdr = pd.DataFrame({
        "A Party": ["919876543210", "919876543211"],
        "B Party": ["919876543212", "919876543213"],
        "call_date_time": ["2026-11-05 10:15:00", "2026-11-05 10:20:00"],
        "call_duration": [120, 45],
        "direction": ["VOICE", "SMS"],
        "status": ["ANSWERED", "DELIVERED"],
        "site_id": ["TWR-01", "TWR-02"]
    })
    std_cdr, mapping, err = standardize_cdr(custom_cdr)
    assert err == "", f"CDR standardization returned error: {err}"
    assert "caller_number" in std_cdr.columns
    assert "receiver_number" in std_cdr.columns
    assert "event_timestamp" in std_cdr.columns
    assert std_cdr["validation_status"].iloc[0] == "VALID"
    print(f" PASS: CDR aliases mapped successfully: {mapping}")
    passed += 1

    # --------------------------------------------------------------------------
    # T03: Upload & Standardize Valid IPDR with Aliases (CSV)
    # --------------------------------------------------------------------------
    print("\n[T03] Testing IPDR Alias Mapping & Standardization (CSV)...")
    custom_ipdr = pd.DataFrame({
        "account_id": ["ACC-999"],
        "source_ip": ["192.0.2.77"],
        "start_time": ["2026-11-10 14:00:00"],
        "end_time": ["2026-11-10 15:30:00"],
        "bytes_up": [1048576],
        "bytes_down": [5242880],
        "proto": ["HTTPS"],
        "apn": ["APN-TEST-1"]
    })
    std_ipdr, ipdr_mapping, err = standardize_ipdr(custom_ipdr)
    assert err == "", f"IPDR standardization error: {err}"
    assert "subscriber_id" in std_ipdr.columns
    assert "ip_address" in std_ipdr.columns
    assert std_ipdr["validation_status"].iloc[0] == "VALID"
    print(f" PASS: IPDR aliases mapped successfully: {ipdr_mapping}")
    passed += 1

    # --------------------------------------------------------------------------
    # T04: Upload File Missing Required Fields
    # --------------------------------------------------------------------------
    print("\n[T04] Testing Handling of Missing Required Fields...")
    bad_cdr = pd.DataFrame({
        "random_col_1": [1, 2],
        "random_col_2": ["a", "b"]
    })
    _, _, err = standardize_cdr(bad_cdr)
    assert "Missing required CDR column" in err, f"Expected missing column error, got: {err}"
    print(f" PASS: Caught missing required fields: {err}")
    passed += 1

    # --------------------------------------------------------------------------
    # T05: Invalid Timestamp Rows Marked REVIEW (Not Dropped)
    # --------------------------------------------------------------------------
    print("\n[T05] Testing REVIEW Flagging for Malformed Records...")
    std_sample_cdr, _, _ = standardize_cdr(cdr_raw)
    review_rows = std_sample_cdr[std_sample_cdr["validation_status"] == "REVIEW"]
    assert len(review_rows) > 0, "Expected at least 1 REVIEW row in sample CDR"
    assert len(std_sample_cdr) == 220, "Total rows changed during validation!"
    
    # Check invalid timestamp edge case
    bad_time_row = std_sample_cdr[std_sample_cdr["event_timestamp"] == "2026-11-99 25:99:99"]
    assert not bad_time_row.empty, "Missing bad timestamp row"
    assert bad_time_row["validation_status"].iloc[0] == "REVIEW"
    print(f" PASS: {len(review_rows)} malformed rows flagged as REVIEW without row dropping.")
    passed += 1

    # --------------------------------------------------------------------------
    # T06: Relationship Graph Construction
    # --------------------------------------------------------------------------
    print("\n[T06] Testing Communication Network Graph Generation...")
    valid_cdr = std_sample_cdr[std_sample_cdr["validation_status"] == "VALID"]
    G = nx.Graph()
    for _, row in valid_cdr.iterrows():
        n1 = row["caller_number"]
        n2 = row["receiver_number"]
        if n1 and n2:
            if G.has_edge(n1, n2):
                G[n1][n2]["weight"] += 1
            else:
                G.add_edge(n1, n2, weight=1)
                
    assert G.number_of_nodes() >= 8, f"Expected >= 8 nodes, got {G.number_of_nodes()}"
    assert G.number_of_edges() > 0, "No edges created in graph"
    density = nx.density(G)
    print(f" PASS: Graph generated with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, density {density:.3f}.")
    passed += 1

    # --------------------------------------------------------------------------
    # T07: Timeline for Sample Identifier in Chronological Order
    # --------------------------------------------------------------------------
    print("\n[T07] Testing Chronological Activity Timeline...")
    target = "9000000001"
    sub_events = valid_cdr[(valid_cdr["caller_number"] == target) | (valid_cdr["receiver_number"] == target)].copy()
    sub_events = sub_events.sort_values("parsed_timestamp", ascending=True)
    assert not sub_events.empty, f"No events found for {target}"
    timestamps = list(sub_events["parsed_timestamp"])
    assert all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1)), "Timestamps not in sorted order"
    print(f" PASS: Found {len(sub_events)} sorted events for {target}.")
    passed += 1

    # --------------------------------------------------------------------------
    # T08: AI Assistant Deterministic Query Routing
    # --------------------------------------------------------------------------
    print("\n[T08] Testing Deterministic AI Assistant Queries...")
    std_sample_ipdr, _, _ = standardize_ipdr(ipdr_raw)
    
    # Query 1: Top Callers
    q1_text, q1_df, q1_intent = process_assistant_query("Show the top callers by number of records", std_sample_cdr, std_sample_ipdr)
    assert q1_intent == "top_callers"
    assert not q1_df.empty
    
    # Query 2: Timeline
    q2_text, q2_df, q2_intent = process_assistant_query("Show timeline for 9000000001", std_sample_cdr, std_sample_ipdr)
    assert q2_intent == "timeline"
    assert not q2_df.empty
    
    # Query 3: Shared Contacts
    q3_text, q3_df, q3_intent = process_assistant_query("Find common contacts between 9000000001 and 9000000002", std_sample_cdr, std_sample_ipdr)
    assert q3_intent == "shared_contacts"
    assert not q3_df.empty
    
    # Query 4: Dataset Summary
    q4_text, q4_df, q4_intent = process_assistant_query("Summarise the uploaded datasets", std_sample_cdr, std_sample_ipdr)
    assert q4_intent == "summary"
    assert len(q4_df) == 2
    
    # Query 5: IPDR Volume
    q5_text, q5_df, q5_intent = process_assistant_query("Show IPDR data volume by subscriber", std_sample_cdr, std_sample_ipdr)
    assert q5_intent == "ipdr_volume"
    assert not q5_df.empty
    
    print(" PASS: All 5 assistant intent patterns routed and produced evidence tables.")
    passed += 1

    # --------------------------------------------------------------------------
    # T09: CSV Export Capability
    # --------------------------------------------------------------------------
    print("\n[T09] Testing Standardized CSV Export...")
    csv_out = std_sample_cdr.to_csv(index=False)
    assert len(csv_out) > 500
    assert "caller_number,receiver_number,event_timestamp" in csv_out
    print(f" PASS: Produced valid CSV export ({len(csv_out)} bytes).")
    passed += 1

    # --------------------------------------------------------------------------
    # T10: Audit Summary JSON Export Capability
    # --------------------------------------------------------------------------
    print("\n[T10] Testing Case Audit JSON Export...")
    summary_payload = {
        "metadata": {
            "application": "CDR/IPDR Intelligence Platform v1.0",
            "classification": "Demonstration Synthetic Data"
        },
        "cdr_metrics": {
            "total_records": len(std_sample_cdr),
            "valid_records": len(valid_cdr),
            "review_records": len(review_rows)
        },
        "ipdr_metrics": {
            "total_sessions": len(std_sample_ipdr),
            "valid_sessions": len(std_sample_ipdr[std_sample_ipdr["validation_status"] == "VALID"])
        }
    }
    json_bytes = json.dumps(summary_payload, indent=2).encode('utf-8')
    parsed_back = json.loads(json_bytes.decode('utf-8'))
    assert parsed_back["cdr_metrics"]["total_records"] == 220
    assert parsed_back["ipdr_metrics"]["total_sessions"] == 100
    print(f" PASS: Validated case audit JSON summary ({len(json_bytes)} bytes).")
    passed += 1

    # --------------------------------------------------------------------------
    # T11: Excel CDR Upload & Standardisation (.xlsx)
    # --------------------------------------------------------------------------
    print("\n[T11] Testing Excel (.xlsx) CDR Upload & Multi-sheet Support...")
    excel_cdr_df = pd.DataFrame({
        "Calling Number": ["919811223344", "919811223355"],
        "Called Number": ["919811223366", "919811223377"],
        "Call Start": ["2026-11-12 14:30:00", "2026-11-12 15:45:00"],
        "Duration": [95, 12],
        "Direction": ["VOICE", "SMS"],
        "Status": ["ANSWERED", "DELIVERED"],
        "Tower": ["TWR-XLS-01", "TWR-XLS-02"]
    })
    excel_path_cdr = "data/test_cdr.xlsx"
    with pd.ExcelWriter(excel_path_cdr, engine="openpyxl") as writer:
        excel_cdr_df.to_excel(writer, index=False, sheet_name="CDR_Records")
        pd.DataFrame({"Info": ["Test Sheet"]}).to_excel(writer, index=False, sheet_name="Metadata")
        
    loaded_excel_cdr, sheets = read_tabular_file(open(excel_path_cdr, "rb"), "test_cdr.xlsx", sheet_name="CDR_Records")
    assert sheets == ["CDR_Records", "Metadata"], f"Sheets mismatch: {sheets}"
    std_excel_cdr, mapping_xls, err_xls = standardize_cdr(loaded_excel_cdr)
    assert err_xls == "", f"Excel CDR standardization error: {err_xls}"
    assert std_excel_cdr["caller_number"].iloc[0] == "919811223344"
    assert std_excel_cdr["validation_status"].iloc[0] == "VALID"
    print(f" PASS: Read Excel CDR from workbook with {len(sheets)} sheets and standardised successfully.")
    passed += 1

    # --------------------------------------------------------------------------
    # T12: Excel IPDR Upload & Binary Export (.xlsx)
    # --------------------------------------------------------------------------
    print("\n[T12] Testing Excel (.xlsx) IPDR Upload & Excel Binary Export...")
    excel_ipdr_df = pd.DataFrame({
        "User ID": ["SUB-XLS-101", "SUB-XLS-102"],
        "Assigned IP": ["192.0.2.201", "192.0.2.202"],
        "Start": ["2026-11-14 09:00:00", "2026-11-14 11:15:00"],
        "End": ["2026-11-14 10:30:00", "2026-11-14 12:00:00"],
        "Bytes Up": [204800, 512000],
        "Bytes Down": [1048576, 4194304],
        "Protocol": ["HTTPS", "QUIC"],
        "Tower ID": ["APN-CORP-1", "APN-CORP-2"]
    })
    excel_path_ipdr = "data/test_ipdr.xlsx"
    with pd.ExcelWriter(excel_path_ipdr, engine="openpyxl") as writer:
        excel_ipdr_df.to_excel(writer, index=False, sheet_name="IPDR_Sessions")
        
    loaded_excel_ipdr, _ = read_tabular_file(open(excel_path_ipdr, "rb"), "test_ipdr.xlsx")
    std_excel_ipdr, _, err_ipdr_xls = standardize_ipdr(loaded_excel_ipdr)
    assert err_ipdr_xls == "", f"Excel IPDR error: {err_ipdr_xls}"
    assert std_excel_ipdr["subscriber_id"].iloc[0] == "SUB-XLS-101"
    assert std_excel_ipdr["validation_status"].iloc[0] == "VALID"
    
    # Test Excel Export Byte generation
    xlsx_bytes = to_excel_bytes(std_excel_ipdr, sheet_name="Exported_IPDR")
    assert len(xlsx_bytes) > 1000, "Generated Excel bytes too small"
    print(f" PASS: Excel IPDR loaded, standardised, and exported to .xlsx ({len(xlsx_bytes)} bytes).")
    passed += 1

    print("\n==================================================")
    print(f"ACCEPTANCE CRITERIA RESULTS: {passed}/{total} TESTS PASSED")
    print("==================================================")

if __name__ == "__main__":
    run_all_tests()
