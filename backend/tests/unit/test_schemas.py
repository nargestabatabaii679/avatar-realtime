"""Unit tests for Pydantic schemas."""
import pytest
from pydantic import ValidationError
from app.schemas.user import UserCreate, UserLogin
from app.schemas.avatar import AvatarCreate
from app.schemas.video import VideoGenerateRequest


def test_user_create_valid():
    user = UserCreate(
        email="test@example.com",
        password="SecurePassword123!",
        full_name="Test User",
    )
    assert user.email == "test@example.com"


def test_user_create_invalid_email():
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", password="pass", full_name="Test")


def test_user_login():
    login = UserLogin(email="user@example.com", password="mypassword")
    assert login.email == "user@example.com"


def test_avatar_create():
    avatar = AvatarCreate(name="My Avatar", source_type="photo")
    assert avatar.name == "My Avatar"


def test_video_generate_request_valid():
    req = VideoGenerateRequest(
        avatar_id="550e8400-e29b-41d4-a716-446655440000",
        voice_model_id="550e8400-e29b-41d4-a716-446655440001",
        script="Hello, this is a test script for video generation.",
        language="en",
        resolution="1080p",
    )
    assert req.resolution == "1080p"
    assert req.language == "en"


def test_video_generate_request_invalid_resolution():
    with pytest.raises(ValidationError):
        VideoGenerateRequest(
            avatar_id="550e8400-e29b-41d4-a716-446655440000",
            voice_model_id="550e8400-e29b-41d4-a716-446655440001",
            script="Test script",
            language="en",
            resolution="8k",  # invalid
        )
