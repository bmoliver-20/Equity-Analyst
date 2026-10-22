from pathlib import Path
import os

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")
print("GEMINI_API_KEY is present" if os.getenv("GEMINI_API_KEY") else "GEMINI_API_KEY is not present")
