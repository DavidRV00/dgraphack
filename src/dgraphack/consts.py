import os
import tempfile


API_HOST = "0.0.0.0"
API_PORT = 8123
API_URL = f"http://{API_HOST}:{API_PORT}"
API_WORK_DIR = os.path.join(tempfile.gettempdir(), "dgraphack")
API_IMG_DIR = os.path.join(API_WORK_DIR, "imgs")

