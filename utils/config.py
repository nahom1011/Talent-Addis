import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")
BOT_USERNAME = os.getenv("BOT_USERNAME", "dbutalent_bot") # Default or set in env  

if not BOT_TOKEN:
    print("Warning: BOT_TOKEN is not set in .env file.")
if not CHANNEL_ID:
    print("Warning: CHANNEL_ID is not set in .env file.")
