# Test script
import requests
import os
from dotenv import load_dotenv

load_dotenv()
vidu_key = os.getenv("VIDU_API_KEY")
print(f"API Key: {vidu_key[:10]}..." if vidu_key else "No API key found")
