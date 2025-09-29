from flask import Flask, request, jsonify
from pydantic import BaseModel, EmailStr, conint, ValidationError
from datetime import datetime
import hashlib
import json
import os
import uuid

app = Flask(__name__)

DATA_FILE = os.path.join("data", "survey.ndjson")
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)


# --------- Pydantic model ---------
class SurveySubmission(BaseModel):
    name: str
    email: EmailStr
    age: conint(ge=13, le=120)
    consent: bool
    rating: conint(ge=1, le=5)
    comments: str = ""


# --------- Helper functions ---------
def hash_value(value: str) -> str:
    """Hash sensitive values like email and age deterministically using SHA-256."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def store_submission(record: dict) -> None:
    """Append the record as JSON to the NDJSON file."""
    with open(DATA_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


# --------- Routes ---------
@app.route("/v1/survey", methods=["POST"])
def submit_survey():
    # Enforce JSON only
    if not request.is_json:
        return jsonify({"error": "invalid_content_type"}), 400

    try:
        data = SurveySubmission(**request.get_json())
    except ValidationError as e:
        return jsonify({"error": "validation_error", "details": e.errors()}), 422

    submission_id = uuid.uuid4().hex

    # Hash sensitive fields before storing
    stored_record = {
        "full_name": data.name,
        "email": hash_value(data.email),
        "age": hash_value(str(data.age)),
        "rating": data.rating,
        "comments": data.comments,
        "consent": data.consent,
        "user_agent": request.headers.get("User-Agent"),
        "submission_id": submission_id,
        "received_at": datetime.utcnow().isoformat(),
        "ip": request.remote_addr,
    }

    store_submission(stored_record)

    return jsonify({"status": "ok", "submission_id": submission_id}), 201


@app.route("/v1/survey/version", methods=["GET"])
def version():
    return jsonify({"version": "1.0.0"})

