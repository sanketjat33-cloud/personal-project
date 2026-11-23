import os
import io
import pandas as pd
import openpyxl

def detect_header_row(df_sample: pd.DataFrame) -> int:
    """
    Scans the first 10 rows of a dataframe to detect where column headers begin
    in case there are leading blank rows or report title rows.
    """
    common_keywords = [
        "party", "calling", "called", "number", "caller", "receiver",
        "date", "time", "duration", "status", "cell", "record", "id",
        "msisdn", "ip", "session", "upload", "download", "protocol", "imei", "imsi"
    ]
    
    best_row_idx = 0
    max_matches = 0
    
    rows_to_check = min(10, len(df_sample))
    for i in range(rows_to_check):
        row_vals = [str(x).strip().lower() for x in df_sample.iloc[i].values if pd.notna(x)]
        if not row_vals:
            continue
        matches = sum(1 for val in row_vals if any(kw in val for kw in common_keywords))
        if matches > max_matches:
            max_matches = matches
            best_row_idx = i
            
    # If first row already has matches or no row has good matches, default to 0
    return best_row_idx if max_matches >= 2 else 0

def inspect_excel_sheets(file_obj) -> list:
    """Returns sheet names in an Excel file."""
    try:
        excel = pd.ExcelFile(file_obj, engine="openpyxl")
        return excel.sheet_names
    except Exception:
        return []

def select_best_sheet(sheet_names: list, file_type_hint: str = None) -> str:
    """
    Selects the most appropriate sheet name based on hinted type or keywords.
    """
    if not sheet_names:
        return ""
    
    norm_sheets = [s.strip().lower() for s in sheet_names]
    
    if file_type_hint:
        hint = file_type_hint.strip().lower()
        for idx, s in enumerate(norm_sheets):
            if hint in s:
                return sheet_names[idx]
                
    # Search for CDR or IPDR in sheet names
    for idx, s in enumerate(norm_sheets):
        if "cdr" in s:
            return sheet_names[idx]
        if "ipdr" in s:
            return sheet_names[idx]
            
    return sheet_names[0]

def read_telecom_file(file_obj, filename: str, sheet_name: str = None) -> tuple[pd.DataFrame, list, str]:
    """
    Robust reader for CSV, XLSX, and XLS files.
    Returns: (raw_dataframe, list_of_sheets_if_excel, active_sheet_name)
    """
    fname = filename.lower()
    
    if fname.endswith(".csv"):
        # Detect delimiter or encoding if needed
        try:
            df = pd.read_csv(file_obj)
        except UnicodeDecodeError:
            file_obj.seek(0)
            df = pd.read_csv(file_obj, encoding="latin1")
            
        header_idx = detect_header_row(df.head(10))
        if header_idx > 0:
            file_obj.seek(0)
            try:
                df = pd.read_csv(file_obj, skiprows=header_idx)
            except Exception:
                pass
        return df, None, None
        
    elif fname.endswith((".xlsx", ".xls")):
        excel = pd.ExcelFile(file_obj, engine="openpyxl")
        sheets = excel.sheet_names
        
        target_sheet = sheet_name if (sheet_name and sheet_name in sheets) else select_best_sheet(sheets)
        
        # Read initial sample to check header row
        df_sample = pd.read_excel(excel, sheet_name=target_sheet, header=None, nrows=10)
        header_idx = detect_header_row(df_sample)
        
        df = pd.read_excel(excel, sheet_name=target_sheet, header=header_idx)
        return df, sheets, target_sheet
        
    else:
        raise ValueError(f"Unsupported file format '{filename}'. Please provide a .csv, .xlsx, or .xls file.")
