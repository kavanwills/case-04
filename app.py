from flask import Flask, request, jsonify
from pydantic import BaseModel, Field, ValidationError, EmailStr
from datetime import datetime
import hashlib
import json
import os

app = Flask(__name__)

# Path for storing submissions (JSON Lines format)
DATA_FILE = "data/survey.ndjson"
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

# --- 1) Model with user_agent + submission_id ---
class SurveySubmission(BaseModel):
    full_name: str = Field(..., max_length=100)
    email: EmailStr
    age: int
    rating: int
    comments: str = ""
    consent: bool
    user_agent: str = None
    submission_id: str = None

def sha256_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

@app.get("/ping")
def ping():
    return jsonify({
        "message": "API is alive",
        "status": "ok",
        "utc_time": datetime.utcnow().isoformat()
    }), 200

# --- 2 & 3) Hash PII + handle submission_id ---
@app.post("/v1/survey")
def submit_survey():
    if not request.is_json:
        return jsonify({"error": "Request must be application/json"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Malformed JSON body"}), 400

    # Attach user agent if missing
    if not data.get("user_agent"):
        data["user_agent"] = request.headers.get("User-Agent", "")

    try:
        submission = SurveySubmission(**data)

        # Hash PII
        hashed_email = sha256_hash(submission.email)
        hashed_age = sha256_hash(str(submission.age))

        # Generate submission_id if needed
        if submission.submission_id is None:
            hour_stamp = datetime.utcnow().strftime("%Y%m%d%H")
            submission.submission_id = sha256_hash(submission.email + hour_stamp)

        record = submission.dict()
        record["email"] = hashed_email
        record["age"] = hashed_age
        record["received_at"] = datetime.utcnow().isoformat()
        record["ip"] = request.headers.get("X-Forwarded-For", request.remote_addr)

        with open(DATA_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")

        return jsonify({
            "status": "created",
            "submission_id": submission.submission_id
        }), 201

    except ValidationError as e:
        return jsonify({"error": "validation_error", "details": e.errors()}), 422
    except Exception as e:
        return jsonify({"error": "request_failed", "details": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

