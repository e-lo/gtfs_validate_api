from google.cloud import firestore
from google.api_core.exceptions import NotFound
import bcrypt
import uuid
import datetime

# Firestore client (uses emulator if FIRESTORE_EMULATOR_HOST is set)
db = firestore.Client()

# --- User helpers ---
def get_user(email: str):
    doc = db.collection('users').document(email.lower()).get()
    return doc.to_dict() if doc.exists else None

def create_user(email: str, is_verified: bool = False):
    user_data = {
        'is_verified': is_verified,
        'created_at': datetime.datetime.utcnow(),
    }
    db.collection('users').document(email.lower()).set(user_data)
    return user_data

def set_user_verified(email: str):
    db.collection('users').document(email.lower()).update({'is_verified': True})

# --- API Key helpers ---
def hash_api_key(api_key: str) -> str:
    return bcrypt.hashpw(api_key.encode(), bcrypt.gensalt()).decode()

def verify_api_key_hash(api_key: str, key_hash: str) -> bool:
    return bcrypt.checkpw(api_key.encode(), key_hash.encode())

def create_api_key(email: str, api_key: str):
    key_hash = hash_api_key(api_key)
    key_id = str(uuid.uuid4())
    data = {
        'user_email': email.lower(),
        'key_hash': key_hash,
        'created_at': datetime.datetime.utcnow(),
        'is_active': True,
    }
    db.collection('api_keys').document(key_id).set(data)
    return key_id

def get_api_key_by_value(api_key: str):
    # Search all api_keys for a matching hash (slow, but ok for small scale)
    keys = db.collection('api_keys').where('is_active', '==', True).stream()
    for doc in keys:
        data = doc.to_dict()
        if verify_api_key_hash(api_key, data['key_hash']):
            return data
    return None

# --- Verification Token helpers ---
def create_verification_token(email: str, token: str, expires_at: datetime.datetime):
    token_id = str(uuid.uuid4())
    data = {
        'user_email': email.lower(),
        'token': token,
        'created_at': datetime.datetime.utcnow(),
        'expires_at': expires_at,
        'is_used': False,
    }
    db.collection('verification_tokens').document(token_id).set(data)
    return token_id

def get_verification_token(token: str):
    # Search for token (should be indexed for scale)
    tokens = db.collection('verification_tokens').where('token', '==', token).where('is_used', '==', False).stream()
    for doc in tokens:
        data = doc.to_dict()
        return data, doc.id
    return None, None

def mark_token_used(token_id: str):
    db.collection('verification_tokens').document(token_id).update({'is_used': True}) 