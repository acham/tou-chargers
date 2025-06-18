from datetime import time

def is_time_in_interval(check_time: time, start_time: time, end_time: time) -> bool:
    """
    Check if a time is within an interval, handling intervals that cross midnight.
    """
    if start_time < end_time:
        return start_time <= check_time <= end_time
    
    else:
        return check_time >= start_time or check_time <= end_time 