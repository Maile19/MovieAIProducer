import datetime
from dotenv import load_dotenv
load_dotenv("/home/ubuntu/MovieAIProducer/.env")

import jwt
import httpx
from backend.app.core.config import get_settings

settings = get_settings()
now = datetime.datetime.now(datetime.timezone.utc)
exp = now + datetime.timedelta(hours=2)

token = jwt.encode(
    {
        "sub": "146f9c35-1d26-4d3d-9cb3-4e3d4cb6ffc5",
        "email": "needgenius19@gmail.com",
        "role": "SHOWRUNNER",
        "name": "Admin",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    },
    settings.jwt_secret_key,
    algorithm=settings.jwt_algorithm,
)

char_id = "f3057dc6-6ff1-4444-a560-399597722ed0"
url = f"http://127.0.0.1:8090/api/v1/characters/{char_id}/generate-asset"
headers = {"Authorization": f"Bearer {token}"}
payload = {
    "target_type": "turnaround",
    "angle": "front",
    "provider": "ag_gemini_flash",
    "model": "ag/gemini-3.8-flash",
    "aspect_ratio": "1:1",
}

print(f"Calling {url} with AG/Gemini 3.8 Flash (secret key: {settings.jwt_secret_key[:8]}...)...")
with httpx.Client(timeout=90.0) as client:
    res = client.post(url, json=payload, headers=headers)
    print(f"Status: {res.status_code}")
    print(f"Response: {res.json()}")
