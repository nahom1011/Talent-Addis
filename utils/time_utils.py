from datetime import datetime, timezone

def get_time_ago(dt_str):
    if not dt_str: return ""
    try:
        # Simplified for now, just return raw string or simple format if strict
        # Assuming DB stores UTC string
        return dt_str
    except:
        return ""
