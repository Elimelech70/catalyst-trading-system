# ============================================================================
# TIMEZONE FIX FOR web_dashboard.py
# ============================================================================
# 
# Add this near the top of the file (after imports):
# 
# from datetime import datetime, timezone, timedelta
# 
# Then replace the format_time function with this:
# ============================================================================

from datetime import datetime, timezone, timedelta

# Perth timezone (UTC+8) - same as Hong Kong/Singapore
PERTH_TZ = timezone(timedelta(hours=8))

def format_time(dt) -> str:
    """Format datetime for display in Perth time (UTC+8)."""
    if not dt:
        return ""
    # Convert to Perth timezone
    if dt.tzinfo is not None:
        perth_time = dt.astimezone(PERTH_TZ)
    else:
        # Assume UTC if no timezone info
        perth_time = dt.replace(tzinfo=timezone.utc).astimezone(PERTH_TZ)
    return perth_time.strftime("%m/%d %H:%M AWST")


# ============================================================================
# OPTIONAL: Add timezone indicator to subtitle
# ============================================================================
# 
# In your dashboard HTML, you could add to the subtitle:
#
# <div class="subtitle">All times shown in Perth (AWST/UTC+8)</div>
#
# ============================================================================


# ============================================================================
# TEST
# ============================================================================
if __name__ == "__main__":
    # Test with a UTC timestamp
    utc_now = datetime.now(timezone.utc)
    print(f"UTC:   {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Perth: {format_time(utc_now)}")
    
    # Test with naive datetime (assumes UTC)
    naive = datetime(2025, 12, 31, 10, 30, 0)
    print(f"Naive (10:30 UTC) -> Perth: {format_time(naive)}")
    # Should show 18:30 AWST (10:30 + 8 hours)
