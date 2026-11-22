import datetime
import time
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
    "angle": "side",
    "provider": "google_flow",
    "aspect_ratio": "1:1",
}

print(f"Calling {url} with Google Flow...")
with httpx.Client(timeout=60.0) as client:
    res = client.post(url, json=payload, headers=headers)
    print(f"Post Status: {res.status_code}")
    data = res.json()
    print(f"Response: {data}")
    
    job_id = data.get("job_id")
    if not job_id:
        print("No job_id returned!")
        exit(1)
        
    print(f"Polling job {job_id}...")
    for i in range(25):
        time.sleep(3)
        poll_res = client.get(f"http://127.0.0.1:8090/api/flow/images/jobs/{job_id}", headers=headers)
        poll_data = poll_res.json()
        status = poll_data.get("status")
        print(f"  Attempt {i+1}: status={status}")
        if status == "completed":
            print("Job Completed! Attaching to character...")
            attach_res = client.post(
                f"http://127.0.0.1:8090/api/v1/characters/{char_id}/attach-job-result",
                json={
                    "job_id": job_id,
                    "target_type": "turnaround",
                    "angle": "side"
                },
                headers=headers
            )
            print(f"Attach result: {attach_res.json()}")
            break
        elif status == "failed":
            print(f"Job Failed! Error: {poll_data.get('error_message')}")
            print(f"Debug screenshot: {poll_data.get('debug_screenshot_url')}")
            break
