import hmac
import hashlib
from utils.config import BOT_TOKEN

# Use part of BOT_TOKEN as secret if no specific secret exists
SECRET_KEY = BOT_TOKEN[:16].encode() 

def sign_data(data: str) -> str:
    """Appends an HMAC signature to the data string."""
    sig = hmac.new(SECRET_KEY, data.encode(), hashlib.sha256).hexdigest()[:10]
    return f"{data}:{sig}"

def verify_data(signed_data: str) -> str | None:
    """Verifies HMAC signature. Returns original data if valid, else None."""
    try:
        data, sig = signed_data.rsplit(":", 1)
        expected_sig = hmac.new(SECRET_KEY, data.encode(), hashlib.sha256).hexdigest()[:10]
        if hmac.compare_digest(sig, expected_sig):
            return data
        return None
    except ValueError:
        return None
