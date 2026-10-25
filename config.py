import os

def _p(v):
    v = str(v).strip()
    try:
        return int(v)
    except ValueError:
        return v

API_ID = int(os.environ.get("API_ID", "0") or 0)
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0") or 0)
STORAGE = _p(os.environ.get("STORAGE_CHANNEL_INPUT", ""))

FS_WINDOW = 24 * 60 * 60   # request / verification window (24 hrs)
REQUIRED_REQUESTS = 3      # user must send requests to any 3 channels per 24 hrs
AUTO_DELETE = 5 * 60       # first/last/greeting auto delete (5 min)
