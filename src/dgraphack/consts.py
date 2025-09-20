import os
import tempfile


API_PORT = 8123
API_URL = f"http://localhost:{API_PORT}"
API_WORK_DIR = os.path.join(tempfile.gettempdir(), "dgraphack")
API_IMG_DIR = os.path.join(API_WORK_DIR, "imgs")

