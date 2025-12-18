
from src.api.admin import CreateUserRequest
from pydantic import ValidationError
import pytest

def test_create_user_request_logic():
    # Test 1: Super Admin implies Admin
    req = CreateUserRequest(email="test@example.com", display_name="Test", is_super_admin=True)
    assert req.is_super_admin is True
    assert req.is_admin is True, "is_super_admin=True should imply is_admin=True"

    # Test 2: Admin does not imply Super Admin
    req = CreateUserRequest(email="test@example.com", display_name="Test", is_admin=True)
    assert req.is_admin is True
    assert req.is_super_admin is False

    # Test 3: Explicit False Admin with True Super Admin (Should still be True due to __init__ logic OR API logic)
    # Note: Our __init__ logic overrides it.
    req = CreateUserRequest(email="test@example.com", display_name="Test", is_admin=False, is_super_admin=True)
    assert req.is_admin is True, "is_super_admin=True should override is_admin=False"

if __name__ == "__main__":
    try:
        test_create_user_request_logic()
        print("✅ CreateUserRequest logic verification passed!")
    except AssertionError as e:
        print(f"❌ Verification failed: {e}")
    except Exception as e:
        print(f"❌ An error occurred: {e}")
