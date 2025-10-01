from flask import Flask, request, jsonify
from pydantic import BaseModel, EmailStr, ValidationError
from datetime import datetime, timezone
from typing import Optional
import hashlib, json, os

app = Flask(__name__)

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "survey.ndjson")
os.makedirs(DATA_DIR, exist_ok=True)

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def utc_hour_bucket() -> str:
    # YYYYMMDDHH (UTC)
    return datetime.now(timezone.utc).strftime("%Y%m%d%H")

class SurveyIn(BaseModel):
    name: str
    email: EmailStr
    age: int
    consent: bool
    rating: int
    comments: Optional[str] = None
    user_agent: Optional[str] = None       # (1) optional user_agent
    submission_id: Optional[str] = None    # (3) optional submission_id

@app.post("/v1/survey")
def submit_survey():
    if not request.is_json:
        return jsonify(error="Request body must be JSON"), 400

    payload = request.get_json(silent=True) or {}

    try:
        data = SurveyIn(**payload)
    except ValidationError as e:
        return jsonify(error="validation_error", details=json.loads(e.json())), 422

    # (3) submission_id: use provided or compute sha256(email + UTC hour)
    submission_id = data.submission_id or sha256_hex(f"{data.email}{utc_hour_bucket()}")

    # (2) write only hashed email/age; no raw PII is persisted
    record = {
        "name": data.name,
        "consent": data.consent,
        "rating": data.rating,
        "comments": data.comments or "",
        "user_agent": data.user_agent or "",
        "submission_id": submission_id,
        "hashed_email": sha256_hex(str(data.email)),
        "hashed_age": sha256_hex(str(data.age)),
    }

    with open(DATA_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return jsonify(status="created", submission_id=submission_id), 201

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)

