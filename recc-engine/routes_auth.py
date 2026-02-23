import json
import os
import time

import jwt
import portalocker
import requests
from fastapi import APIRouter, HTTPException
from jwt.algorithms import RSAAlgorithm

import user
from api_schemas import AppleAuthRequest
from app_shared import logger


router = APIRouter()


@router.post("/auth/apple")
def apple_auth(request: AppleAuthRequest):
    """
    Verifies Apple Identity Token and issues a session token.
    Creates a user profile if one doesn't exist.
    """
    try:
        apple_keys_url = "https://appleid.apple.com/auth/keys"

        key_response = requests.get(apple_keys_url, timeout=10)
        key_response.raise_for_status()
        key_payload = key_response.json()
        keys = key_payload.get("keys", [])

        header = jwt.get_unverified_header(request.identityToken)
        kid = header.get("kid")
        alg = header.get("alg")

        key = next((k for k in keys if k["kid"] == kid), None)
        if not key:
            raise HTTPException(status_code=401, detail="Invalid token: key not found")

        public_key = RSAAlgorithm.from_jwk(json.dumps(key))

        payload = jwt.decode(
            request.identityToken,
            public_key,
            algorithms=[alg],
            options={"verify_aud": False},
        )

        user_sub = payload.get("sub")
        if not user_sub:
            raise HTTPException(status_code=401, detail="Invalid token: no sub claim")

        user_id = user_sub
        file_path = f"users/{user_id}.json"
        lock_file = f"users/{user_id}.lock"

        os.makedirs("users", exist_ok=True)
        profile = None

        with portalocker.Lock(lock_file, timeout=5):
            if os.path.exists(file_path):
                try:
                    profile = user.load_user_profile(file_path)
                except Exception as e:
                    logger.error("Failed to load profile for %s: %s", user_id, e)
                    raise HTTPException(status_code=500, detail="Profile load error")
            else:
                name_part = "User"
                if request.fullName:
                    given = request.fullName.get("givenName", "")
                    family = request.fullName.get("familyName", "")
                    parts = [p for p in [given, family] if p]
                    if parts:
                        name_part = " ".join(parts)

                profile = {
                    "id": user_id,
                    "name": name_part,
                    "email": request.email or payload.get("email"),
                    "genres": [],
                    "data": {
                        "liked": [],
                        "disliked": [],
                        "neutral": [],
                        "watchlist": [],
                        "history": [],
                        "shown": [],
                    },
                    "keywords": {},
                    "personas": [],
                }
                user.save_user_profile(file_path, profile)
                logger.info("Created new user profile: %s", user_id)

        secret_key = os.getenv("JWT_SECRET_KEY")
        if not secret_key:
            logger.warning("JWT_SECRET_KEY is not set; using development fallback secret")
            secret_key = "dev-secret"

        session_payload = {
            "sub": user_id,
            "iat": time.time(),
            "exp": time.time() + (24 * 3600 * 7),
        }
        session_token = jwt.encode(session_payload, secret_key, algorithm="HS256")

        return {
            "token": session_token,
            "user": profile,
            "needs_onboarding": len(profile.get("personas", [])) == 0,
        }

    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error("Auth error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
