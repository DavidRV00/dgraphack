import os
import tempfile

API_HOST = "127.0.0.1"
API_PORT = 8124
API_URL = f"http://{API_HOST}:{API_PORT}"
API_WORK_DIR = os.path.join(tempfile.gettempdir(), "dgraphack")

