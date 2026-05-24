"""Unit tests for security module."""
import pytest
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_token,
    generate_api_key,
)


def test_password_hash_and_verify():
    password = "SecurePassword123!"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("WrongPassword", hashed)


def test_jwt_create_and_decode():
    data = {"sub": "user-uuid-1234", "role": "creator"}
    token = create_access_token(data)
    assert token
    decoded = decode_token(token)
    assert decoded["sub"] == "user-uuid-1234"
    assert decoded["role"] == "creator"


def test_jwt_invalid_token():
    from jose import JWTError
    with pytest.raises(Exception):
        decode_token("invalid.token.here")


def test_api_key_generation():
    key1 = generate_api_key()
    key2 = generate_api_key()
    assert len(key1) > 20
    assert key1 != key2


def test_password_hash_bcrypt_format():
    hashed = get_password_hash("test")
    assert hashed.startswith("$2b$")
