import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

BOT_NAME = os.getenv("BOT_NAME", "DarkZsaid SSH Bot")
PANEL_NAME = os.getenv("PANEL_NAME", "DarkZsaid")

HOST = os.getenv("HOST", "127.0.0.1")
SSH_PORT = int(os.getenv("SSH_PORT", "22"))
WS_PORT = int(os.getenv("WS_PORT", "80"))
SSL_PORT = int(os.getenv("SSL_PORT", "443"))
UDP_CUSTOM = int(os.getenv("UDP_CUSTOM", "36712"))
