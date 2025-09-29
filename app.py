from flask import Flask, request, jsonify
from datetime import datetime, timezone
from pydantic import BaseModel, Field, conint, ValidationError, validator
import hashlib, json, os

app = Flask(__name__)

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "survey.ndjson")
os.makedirs(DATA_DIR, exist_ok=True)

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

class SurveyIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str
    age: int
    consent: bool
    rating: conint(ge=1, le=5)
    comments: str = ""
    user_agent: str = None
    submission_id: str = None

    @validator("email")
    def simple_email_check(cls, v: str) -> str:
        v = v.strip()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("value is not a valid email address")
        return v

    @validator("consent")
    def must_be_true(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("consent must be true")
        return v

@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"message": "API is alive", "status": "ok"}), 200

@app.route("/v1/survey/version", methods=["GET"])
def versioned():
    return jsonify({"version": 1}), 200

@app.route("/v1/survey", methods=["POST"])
def submit_survey():
    if not request.is_json:
        return jsonify({"error": "bad_request", "detail": "JSON body required"}), 400
    try:
        payload = request.get_json(force=True) or {}
        if "name" not in payload and "full_name" in payload:
            payload["name"] = payload["full_name"]
        if not payload.get("user_agent"):
            payload["user_agent"] = request.headers.get("User-Agent", "") or ""
        data = SurveyIn(**payload)
        if not data.submission_id:
            hour_bucket = datetime.utcnow().strftime("%Y%m%d%H")
            data.submission_id = sha256_hex(f"{data.email}{hour_bucket}")

        stored = {
            "name": data.name,
            "full_name": data.name,
            "hashed_email": sha256_hex(data.email),
            "hashed_age": sha256_hex(str(data.age)),
            "rating": data.rating,
            "comments": data.comments,
            "consent": True,
            "user_agent": data.user_agent or "",
            "submission_id": data.submission_id,
            "received_at": now_utc_iso(),
            "ip": request.remote_addr or "",
        }

        with open(DATA_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(stored) + "\n")

        return jsonify({"status": "ok", "submission_id": data.submission_id}), 201
    except ValidationError as e:
        return jsonify({"error": "validation_error", "detail": e.errors()}), 422
    except Exception as e:
        return jsonify({"error": "internal_error", "detail": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)

