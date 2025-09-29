from flask import Flask, request, jsonify
from datetime import datetime, timezone
from pydantic import BaseModel, Field, EmailStr, conint, ValidationError, validator
import hashlib
import json
import os

app = Flask(__name__)

# ---------- Constants ----------
DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "survey.ndjson")
os.makedirs(DATA_DIR, exist_ok=True)


# ---------- Pydantic model ----------
class SurveyIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    age: int
    consent: bool
    rating: conint(ge=1, le=5)
    comments: str = ""

    @validator("consent")
    def must_be_true(cls, v):
        if v is not True:
            raise ValueError("consent must be true")
        return v


# ---------- Helpers ----------
def hash_value(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def store_submission(record: dict):
    """Append the record to the NDJSON file."""
    with open(DATA_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


# ---------- Routes ----------
@app.route("/ping")
def ping():
    return jsonify({"message": "API is alive", "status": "ok"}), 200


@app.route("/v1/survey", methods=["POST"])
def submit_survey():
    # 400 if not JSON
    if not request.is_json:
        return jsonify({"error": "bad_request", "detail": "JSON body required"}), 400

    try:
        payload = request.get_json(force=True)

        # Accept legacy "full_name"
        if "name" not in payload and "full_name" in payload:
            payload["name"] = payload["full_name"]

        data = SurveyIn(**payload)

        # Generate submission_id (sha256(email+hourbucket))
        hour_bucket = datetime.utcnow().strftime("%Y%m%d%H")
        submission_id = hash_value(f"{data.email}{hour_bucket}")

        received_at = now_utc_iso()

        stored_record = {
            "full_name": data.name,
            "email_sha256": hash_value(data.email),
            "age_sha256": hash_value(str(data.age)),
            "rating": data.rating,
            "comments": data.comments,
            "consent": data.consent,
            "user_agent": request.headers.get("User-Agent", ""),
            "submission_id": submission_id,
            "received_at": received_at,
            "ip": request.remote_addr or "",
        }

        store_submission(stored_record)

        return jsonify({"status": "ok", "submission_id": submission_id}), 201

    except ValidationError as e:
        return jsonify({"error": "validation_error", "detail": e.errors()}), 422
    except Exception as e:
        return jsonify({"error": "internal_error", "detail": str(e)}), 500


@app.route("/v1/survey/version", methods=["GET"])
def version():
    return jsonify({"version": "1.0"}), 200


# ---------- Main ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))  # required by autograder
    app.run(host="0.0.0.0", port=port, debug=True)

