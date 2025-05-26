from datetime import datetime
import pytz
from constants import DATETIMEFORMAT_READABLE, DATETIMEFORMAT_ISO

def is_datetime_valid(datetime_str: str) -> bool:
    try: 
        datetime.strptime(datetime_str, DATETIMEFORMAT_ISO)
        return True
    except Exception: return False

def is_date_valid(date) -> bool:
    try: 
        datetime.strptime(date, '%Y-%m-%d')
        return True
    except Exception: return False

def is_readable_datetime_valid(datetime_str: str) -> bool:
    try:
        datetime.strptime(datetime_str, DATETIMEFORMAT_READABLE)
        return True
    except Exception: return False


def list_val_at(ref_list: list, at: int):
    try: return ref_list[at]
    except Exception: return None


def flatten_list(ref_list: list) -> list:
    flat = []
    for x in ref_list:
        if x != None:
            if type(x) == list:
                for y in x: flat.append(y)
            else: flat.append(x)
    return flat


def stringify_and(ref_list: list) -> str:
    return f'({" AND ".join(ref_list)})' if ref_list else ''

def stringify_or(ref_list: list) -> str:
    return f'({" OR ".join(ref_list)})' if ref_list else '' 


def ph_datetime_now() -> str:
    utc_now = datetime.now(pytz.utc)
    ph_timezone = pytz.timezone('Asia/Manila')
    ph_datetime = utc_now.astimezone(ph_timezone)
    return ph_datetime.strftime(DATETIMEFORMAT_ISO)
