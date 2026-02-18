
import pytz
from datetime import datetime

print(f"System local time: {datetime.now()}")
try:
    tz = pytz.timezone('Europe/Istanbul')
    now = datetime.now(tz)
    print(f"Istanbul time: {now}")
except Exception as e:
    print(f"Error: {e}")
