import re
import difflib

# ==============================================================================
# CONFIGURABLE ALIAS DICTIONARIES
# ==============================================================================

CDR_CANONICAL_ALIASES = {
    "caller_number": [
        "a party", "a-party", "a_party", "a party (calling)", "a-party (calling)",
        "a party calling", "calling", "calling number", "calling_no", "calling party",
        "caller", "caller number", "source number", "source", "from", "caller_id",
        "calling_party", "originating_number", "orig_number", "msisdn_orig",
        "source_address", "calling_address"
    ],
    "receiver_number": [
        "b party", "b-party", "b_party", "b party (called)", "b-party (called)",
        "b party called", "called", "called number", "called_no", "called party",
        "receiver", "receiver number", "destination number", "destination", "to",
        "receiver_id", "called_party", "terminating_number", "term_number",
        "msisdn_term", "destination_address", "called_address"
    ],
    "event_timestamp": [
        "event_timestamp", "timestamp", "call_date_time", "call_datetime",
        "call datetime", "start_time", "call_start", "date_time", "datetime",
        "date time", "call_time_start", "call start time", "event time"
    ],
    # Split date and time components
    "call_date": [
        "call date", "call_date", "date", "event_date", "call_start_date",
        "start date", "calldate"
    ],
    "call_time": [
        "call time", "call_time", "time", "event_time", "call_start_time",
        "start time", "calltime"
    ],
    "duration_seconds": [
        "duration (sec)", "duration(sec)", "duration_seconds", "duration",
        "call duration", "call_duration", "duration_sec", "call_duration_seconds",
        "call duration (sec)", "duration (s)", "billsec", "call_len", "duration sec"
    ],
    "call_type": [
        "call type", "call_type", "type", "traffic type", "traffic_type",
        "service type", "service_type", "call_category", "telecom_type"
    ],
    "direction": [
        "direction", "call direction", "call_direction", "flow", "traffic_direction",
        "in_out", "in/out", "mo_mt", "call_flow"
    ],
    "call_status": [
        "call status", "call_status", "status", "call result", "call_result",
        "disposition", "result", "termination_reason", "call_state", "release_reason"
    ],
    "cell_tower_id": [
        "cell id", "cell_id", "cell_tower_id", "tower id", "tower_id",
        "site id", "site_id", "tower", "cell site", "cell_site", "cgi",
        "first_cgi", "cell_name", "first_cell", "bts_id", "ci"
    ],
    "record_id": [
        "record id", "record_id", "recordid", "id", "cdr id", "cdr_id",
        "seq no", "sequence", "seq_no", "row_id", "cdr_ref", "transaction_id"
    ],
    "lac": [
        "lac", "location area code", "location_area_code", "location area"
    ],
    "tower_location": [
        "tower location", "tower_location", "location", "site location",
        "site_location", "tower address", "address", "circle", "cell_address"
    ],
    "imei": [
        "imei", "device id", "device_id", "handset id", "handset_id",
        "imei number", "caller_imei"
    ],
    "imsi": [
        "imsi", "subscriber identity", "imsi number", "caller_imsi"
    ],
    "operator": [
        "operator", "tsp", "provider", "carrier", "network operator", "telco", "telecom_operator"
    ]
}

IPDR_CANONICAL_ALIASES = {
    "subscriber_id": [
        "msisdn", "subscriber id", "subscriber_id", "subscriber", "user id",
        "user_id", "account id", "account_id", "client id", "client_id",
        "customer id", "customer_id", "user_identity", "sub_id"
    ],
    "private_ip": [
        "private ip", "private_ip", "source ip", "source_ip", "assigned ip",
        "assigned_ip", "framed ip", "framed_ip", "internal ip", "internal_ip",
        "private ip address", "client ip", "client_ip", "local ip", "src_ip"
    ],
    "public_ip": [
        "public ip", "public_ip", "external ip", "external_ip", "translated ip",
        "translated_ip", "nat ip", "nat_ip", "public ip address", "nat_public_ip",
        "public source ip", "translated_source_ip"
    ],
    "source_port": [
        "source port", "source_port", "src port", "src_port", "client port",
        "client_port", "sport", "private port", "local_port"
    ],
    "destination_ip": [
        "destination ip", "destination_ip", "dest ip", "dest_ip", "dst ip",
        "dst_ip", "target ip", "target_ip", "server ip", "server_ip", "remote_ip"
    ],
    "destination_port": [
        "destination port", "destination_port", "dest port", "dest_port",
        "dst port", "dst_port", "dport", "target port", "server port", "remote_port"
    ],
    "protocol": [
        "protocol", "ip protocol", "ip_protocol", "proto", "transport",
        "transport_protocol", "l4_protocol", "ip_proto"
    ],
    "service_domain": [
        "service / domain", "service/domain", "service domain", "service_domain",
        "domain", "service", "host", "website", "fqdn", "url", "sni", "app_name",
        "application", "destination_host", "visited_domain"
    ],
    "session_start": [
        "session start", "session_start", "start time", "start_time", "start",
        "begin time", "begin_time", "start_timestamp", "session start time",
        "session_start_time", "session_start_timestamp"
    ],
    "session_end": [
        "session end", "session_end", "end time", "end_time", "end",
        "stop time", "stop_time", "end_timestamp", "session end time",
        "session_end_time", "session_end_timestamp"
    ],
    "duration_seconds": [
        "duration (sec)", "duration(sec)", "duration_seconds", "duration",
        "session duration", "session_duration", "duration_sec", "session_len"
    ],
    "upload_bytes": [
        "upload (bytes)", "upload(bytes)", "upload bytes", "upload_bytes",
        "bytes up", "bytes_up", "uploaded bytes", "uploaded_bytes",
        "uplink bytes", "uplink_bytes", "up_bytes", "bytes_in", "tx bytes",
        "tx_bytes", "uplink_data_volume", "bytes_uploaded"
    ],
    "download_bytes": [
        "download (bytes)", "download(bytes)", "download bytes", "download_bytes",
        "bytes down", "bytes_down", "downloaded bytes", "downloaded_bytes",
        "downlink bytes", "downlink_bytes", "down_bytes", "bytes_out", "rx bytes",
        "rx_bytes", "downlink_data_volume", "bytes_downloaded"
    ],
    "network_id": [
        "cell id", "cell_id", "network id", "network_id", "tower id", "tower_id",
        "cell tower id", "cell_tower_id", "location id", "location_id", "cgi"
    ],
    "imei": [
        "imei", "device id", "device_id", "handset id", "terminal_imei"
    ],
    "imsi": [
        "imsi", "sim id", "subscriber identity", "card_imsi"
    ],
    "apn": [
        "apn", "access point name", "apn name", "access_point"
    ],
    "record_id": [
        "record id", "record_id", "id", "ipdr id", "session id", "seq no", "row_id"
    ]
}

# ==============================================================================
# STRING NORMALIZATION & TOKENIZATION
# ==============================================================================

def normalize_header(header: str) -> str:
    """
    Cleans header strings: lowercase, removes punctuation/brackets, collapses whitespace.
    Example: 'A-Party (Calling)' -> 'a party calling'
    """
    if not isinstance(header, str):
        header = str(header)
    # Replace symbols with space
    cleaned = re.sub(r'[\(\)\[\]_\-/\:\.]+', ' ', header)
    # Collapse whitespace and lowercase
    cleaned = re.sub(r'\s+', ' ', cleaned).strip().lower()
    return cleaned

def clean_alphanumeric(header: str) -> str:
    """Removes all non-alphanumeric characters for fuzzy matching."""
    return re.sub(r'[^a-z0-9]', '', str(header).lower())

# ==============================================================================
# COLUMN DETECTION ENGINE
# ==============================================================================

def match_single_header(source_col: str, alias_dict: dict) -> tuple[str, float]:
    """
    Finds best canonical match for a given column header.
    Returns: (canonical_name or None, confidence_score: 0.0 to 1.0)
    """
    norm_source = normalize_header(source_col)
    clean_source = clean_alphanumeric(source_col)
    
    # 1. Exact match on normalized alias
    for canonical, aliases in alias_dict.items():
        for alias in aliases:
            norm_alias = normalize_header(alias)
            if norm_source == norm_alias:
                return canonical, 1.0
                
    # 2. Strict clean alphanumeric equality
    for canonical, aliases in alias_dict.items():
        for alias in aliases:
            if clean_source == clean_alphanumeric(alias):
                return canonical, 0.95

    # 3. Substring match (e.g. 'Calling Number' matching 'calling')
    best_candidate = None
    best_score = 0.0
    for canonical, aliases in alias_dict.items():
        for alias in aliases:
            norm_alias = normalize_header(alias)
            if len(norm_alias) >= 4 and (norm_alias in norm_source or norm_source in norm_alias):
                # Token overlap ratio
                source_tokens = set(norm_source.split())
                alias_tokens = set(norm_alias.split())
                overlap = len(source_tokens.intersection(alias_tokens))
                total = len(source_tokens.union(alias_tokens))
                jaccard = overlap / total if total > 0 else 0
                score = 0.70 + (jaccard * 0.20)
                if score > best_score:
                    best_score = score
                    best_candidate = canonical
                    
    if best_candidate and best_score >= 0.75:
        return best_candidate, round(best_score, 2)
        
    return None, 0.0

def detect_file_type(columns: list) -> tuple[str, float]:
    """
    Automatically detects whether an uploaded file is CDR or IPDR
    based on matched column features.
    Returns: ('CDR' or 'IPDR', confidence_score)
    """
    cdr_matches = 0
    ipdr_matches = 0
    
    # Strong CDR indicators
    cdr_strong = ["caller_number", "receiver_number", "call_type", "direction", "call_status", "call_date", "call_time"]
    # Strong IPDR indicators
    ipdr_strong = ["subscriber_id", "private_ip", "public_ip", "source_port", "destination_ip", "session_start", "upload_bytes", "download_bytes", "apn"]
    
    for col in columns:
        c_match, c_conf = match_single_header(col, CDR_CANONICAL_ALIASES)
        if c_match in cdr_strong:
            cdr_matches += 2 if c_conf >= 0.9 else 1
            
        i_match, i_conf = match_single_header(col, IPDR_CANONICAL_ALIASES)
        if i_match in ipdr_strong:
            ipdr_matches += 2 if i_conf >= 0.9 else 1
            
    total = cdr_matches + ipdr_matches
    if total == 0:
        return "CDR", 0.5 # Default fallback
        
    if cdr_matches >= ipdr_matches:
        conf = round(cdr_matches / total, 2)
        return "CDR", conf
    else:
        conf = round(ipdr_matches / total, 2)
        return "IPDR", conf

def map_dataset_columns(columns: list, dataset_type: str = "CDR") -> dict:
    """
    Maps all uploaded columns to the target dataset's canonical schema.
    Returns a comprehensive mapping inspection dictionary.
    """
    alias_dict = CDR_CANONICAL_ALIASES if dataset_type.upper() == "CDR" else IPDR_CANONICAL_ALIASES
    
    col_mapping = {}      # source_col -> canonical_col
    confidence_map = {}   # source_col -> score
    assigned_canonicals = set()
    decisions_log = []
    
    # Step 1: Detect direct matches
    for col in columns:
        canonical, score = match_single_header(col, alias_dict)
        if canonical and canonical not in assigned_canonicals:
            col_mapping[col] = canonical
            confidence_map[col] = score
            assigned_canonicals.add(canonical)
            decisions_log.append(f"Mapped '{col}' -> '{canonical}' (confidence: {score})")
            
    # Step 2: Handle special CDR split Date and Time
    split_date_col = None
    split_time_col = None
    if dataset_type.upper() == "CDR" and "event_timestamp" not in assigned_canonicals:
        for col, canonical in col_mapping.items():
            if canonical == "call_date":
                split_date_col = col
            elif canonical == "call_time":
                split_time_col = col
        if split_date_col and split_time_col:
            decisions_log.append(f"Detected split date/time: '{split_date_col}' + '{split_time_col}' will be combined into 'event_timestamp'")
            
    # Step 3: Handle IPDR Private IP vs Public IP
    if dataset_type.upper() == "IPDR":
        private_col = None
        public_col = None
        for col, canonical in col_mapping.items():
            if canonical == "private_ip":
                private_col = col
            elif canonical == "public_ip":
                public_col = col
                
        if private_col:
            decisions_log.append(f"Designated primary 'ip_address' from Private IP '{private_col}'")
        elif public_col:
            decisions_log.append(f"Private IP not found. Using Public IP '{public_col}' as fallback for 'ip_address'")
            
    unmapped = [c for c in columns if c not in col_mapping]
    if unmapped:
        decisions_log.append(f"Preserving {len(unmapped)} additional raw columns: {', '.join(unmapped)}")
        
    return {
        "mapping": col_mapping,
        "confidence": confidence_map,
        "split_date_col": split_date_col,
        "split_time_col": split_time_col,
        "unmapped": unmapped,
        "decisions": decisions_log
    }
