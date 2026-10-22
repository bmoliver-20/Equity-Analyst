from pathlib import Path

from dotenv import dotenv_values


config = dotenv_values(Path(__file__).resolve().parent / ".env")
api_key = config.get("API_KEY")
sec_user_agent = config.get("SEC_USER_AGENT")

if not api_key:
    print("API_KEY is missing or empty. Add API_KEY to .env.")
elif len(api_key) <= 4:
    print("API_KEY is too short to preview safely. Add a valid API_KEY to .env.")
else:
    print(api_key[:4] + "...")

if not sec_user_agent:
    print("SEC_USER_AGENT is missing or empty. Add SEC_USER_AGENT to .env.")
else:
    print(sec_user_agent)
