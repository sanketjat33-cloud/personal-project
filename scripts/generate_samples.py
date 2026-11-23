import os
import random
import datetime
import csv

def generate_cdr():
    random.seed(42)
    os.makedirs("data", exist_ok=True)
    
    phone_numbers = [
        "9000000001",
        "9000000002",
        "9000000003",
        "9000000004",
        "9000000005",
        "9000000006",
        "9000000007",
        "9000000008"
    ]
    
    towers = [
        "TWR-DEL-101",
        "TWR-DEL-102",
        "TWR-MUM-201",
        "TWR-MUM-202",
        "TWR-BLR-301",
        "TWR-HYD-401"
    ]
    
    call_types = ["VOICE", "VOICE", "VOICE", "SMS"]
    call_statuses = ["ANSWERED", "ANSWERED", "ANSWERED", "MISSED", "BUSY", "FAILED"]
    
    start_date = datetime.datetime(2026, 11, 1, 8, 0, 0)
    
    records = []
    
    # 212 valid records
    for i in range(212):
        # Pick caller and receiver
        # Let 9000000001 and 9000000002 be high activity top callers
        weights = [35, 25, 12, 10, 8, 5, 3, 2]
        caller = random.choices(phone_numbers, weights=weights)[0]
        other_numbers = [p for p in phone_numbers if p != caller]
        receiver = random.choice(other_numbers)
        
        # Random day in Nov 2026
        day_offset = random.randint(0, 22)
        hour = random.choices(
            list(range(24)),
            weights=[1, 1, 1, 1, 1, 2, 4, 7, 10, 12, 14, 15, 14, 13, 15, 16, 18, 19, 17, 14, 10, 6, 3, 2]
        )[0]
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        dt = datetime.datetime(2026, 11, 1 + day_offset, hour, minute, second)
        
        c_type = random.choice(call_types)
        if c_type == "SMS":
            duration = 0
            status = "DELIVERED"
        else:
            status = random.choice(call_statuses)
            if status == "ANSWERED":
                duration = random.randint(15, 1800)
            else:
                duration = 0
                
        tower = random.choice(towers)
        
        records.append({
            "caller_number": caller,
            "receiver_number": receiver,
            "event_timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": duration,
            "call_type": c_type,
            "call_status": status,
            "cell_tower_id": tower
        })
        
    # Sort valid records chronologically
    records.sort(key=lambda x: x["event_timestamp"])
    
    # Add 8 edge case rows for REVIEW validation (total 220)
    edge_cases = [
        {
            "caller_number": "9000000001",
            "receiver_number": "9000000002",
            "event_timestamp": "2026-11-99 25:99:99", # Malformed timestamp
            "duration_seconds": 120,
            "call_type": "VOICE",
            "call_status": "ANSWERED",
            "cell_tower_id": "TWR-DEL-101"
        },
        {
            "caller_number": "", # Blank caller
            "receiver_number": "9000000003",
            "event_timestamp": "2026-11-05 14:20:00",
            "duration_seconds": 45,
            "call_type": "VOICE",
            "call_status": "ANSWERED",
            "cell_tower_id": "TWR-BLR-301"
        },
        {
            "caller_number": "9000000004",
            "receiver_number": "", # Blank receiver
            "event_timestamp": "2026-11-08 09:15:30",
            "duration_seconds": 0,
            "call_type": "SMS",
            "call_status": "FAILED",
            "cell_tower_id": "TWR-MUM-201"
        },
        {
            "caller_number": "INVALID_PHONE", # Non-digits
            "receiver_number": "9000000005",
            "event_timestamp": "2026-11-12 11:45:00",
            "duration_seconds": 30,
            "call_type": "VOICE",
            "call_status": "ANSWERED",
            "cell_tower_id": "TWR-HYD-401"
        },
        {
            "caller_number": "9000000002",
            "receiver_number": "9000000001",
            "event_timestamp": "NOT_A_DATE", # Invalid timestamp
            "duration_seconds": 60,
            "call_type": "VOICE",
            "call_status": "ANSWERED",
            "cell_tower_id": "TWR-DEL-102"
        },
        {
            "caller_number": "9000000006",
            "receiver_number": "9000000007",
            "event_timestamp": "2026-11-15 16:30:00",
            "duration_seconds": -50, # Negative duration
            "call_type": "VOICE",
            "call_status": "ANSWERED",
            "cell_tower_id": "TWR-DEL-101"
        },
        {
            "caller_number": "9000000003",
            "receiver_number": "9000000008",
            "event_timestamp": "2026-11-19 23:59:60", # Invalid second
            "duration_seconds": 15,
            "call_type": "VOICE",
            "call_status": "MISSED",
            "cell_tower_id": "TWR-MUM-202"
        },
        {
            "caller_number": "9000000005",
            "receiver_number": "   ", # Whitespace receiver
            "event_timestamp": "2026-11-21 12:00:00",
            "duration_seconds": 10,
            "call_type": "VOICE",
            "call_status": "ANSWERED",
            "cell_tower_id": "TWR-BLR-301"
        }
    ]
    
    # Interleave edge cases
    for ec in edge_cases:
        records.append(ec)
        
    print(f"Generated {len(records)} CDR records.")
    with open("data/sample_cdr.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "caller_number", "receiver_number", "event_timestamp",
            "duration_seconds", "call_type", "call_status", "cell_tower_id"
        ])
        writer.writeheader()
        writer.writerows(records)

def generate_ipdr():
    random.seed(123)
    os.makedirs("data", exist_ok=True)
    
    subscribers = ["SUB-1001", "SUB-1002", "SUB-1003", "SUB-1004", "SUB-1005"]
    ip_addresses = [
        "192.0.2.10", "192.0.2.15", "192.0.2.22",
        "192.0.2.50", "192.0.2.85", "192.0.2.105"
    ]
    protocols = ["HTTPS", "HTTPS", "DNS", "QUIC", "WSS", "TCP", "UDP"]
    networks = ["APN-NET-1", "APN-NET-2", "TWR-DEL-101", "TWR-MUM-201", "TWR-BLR-301"]
    
    records = []
    
    # 96 valid records
    for i in range(96):
        sub = random.choice(subscribers)
        ip = random.choice(ip_addresses)
        proto = random.choice(protocols)
        net = random.choice(networks)
        
        day_offset = random.randint(0, 22)
        hour = random.randint(0, 23)
        minute = random.randint(0, 50)
        second = random.randint(0, 59)
        
        start_dt = datetime.datetime(2026, 11, 1 + day_offset, hour, minute, second)
        duration_minutes = random.randint(1, 120)
        end_dt = start_dt + datetime.timedelta(minutes=duration_minutes, seconds=random.randint(0, 59))
        
        up_bytes = random.randint(50000, 15000000)
        down_bytes = random.randint(200000, 150000000)
        
        records.append({
            "subscriber_id": sub,
            "ip_address": ip,
            "session_start": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "session_end": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "upload_bytes": up_bytes,
            "download_bytes": down_bytes,
            "protocol": proto,
            "network_id": net
        })
        
    records.sort(key=lambda x: x["session_start"])
    
    # 4 edge case rows for REVIEW validation (total 100)
    edge_cases = [
        {
            "subscriber_id": "SUB-1001",
            "ip_address": "192.0.2.10",
            "session_start": "2026-11-10 15:30:00",
            "session_end": "2026-11-10 14:00:00", # End before start!
            "upload_bytes": 1024,
            "download_bytes": 2048,
            "protocol": "HTTPS",
            "network_id": "APN-NET-1"
        },
        {
            "subscriber_id": "", # Blank subscriber
            "ip_address": "192.0.2.15",
            "session_start": "2026-11-12 10:00:00",
            "session_end": "2026-11-12 10:30:00",
            "upload_bytes": 5000,
            "download_bytes": 10000,
            "protocol": "DNS",
            "network_id": "APN-NET-2"
        },
        {
            "subscriber_id": "SUB-1003",
            "ip_address": "", # Blank IP address
            "session_start": "2026-11-15 08:00:00",
            "session_end": "2026-11-15 08:45:00",
            "upload_bytes": 20000,
            "download_bytes": 50000,
            "protocol": "QUIC",
            "network_id": "TWR-DEL-101"
        },
        {
            "subscriber_id": "SUB-1005",
            "ip_address": "192.0.2.50",
            "session_start": "INVALID_TIMESTAMP", # Invalid start
            "session_end": "2026-11-18 19:30:00",
            "upload_bytes": 1000,
            "download_bytes": 4000,
            "protocol": "TCP",
            "network_id": "TWR-MUM-201"
        }
    ]
    
    for ec in edge_cases:
        records.append(ec)
        
    print(f"Generated {len(records)} IPDR records.")
    with open("data/sample_ipdr.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "subscriber_id", "ip_address", "session_start", "session_end",
            "upload_bytes", "download_bytes", "protocol", "network_id"
        ])
        writer.writeheader()
        writer.writerows(records)

if __name__ == "__main__":
    generate_cdr()
    generate_ipdr()
