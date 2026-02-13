"""
Validation utilities for the speed friending app
"""
import re
from typing import Tuple

def validate_email(email: str) -> Tuple[bool, str]:
    """
    Validate email format.
    Returns (is_valid, error_message)
    """
    email = email.strip()
    
    if not email:
        return False, "Email is required"
    
    if len(email) > 254:
        return False, "Email is too long (max 254 characters)"
    
    # Basic email regex pattern
    pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(pattern, email):
        return False, "Invalid email format"
    
    return True, ""


def validate_join_code(code: str) -> Tuple[bool, str]:
    """
    Validate join code format.
    Returns (is_valid, error_message)
    """
    code = code.strip().upper()
    
    if not code:
        return False, "Join code is required"
    
    if len(code) < 4 or len(code) > 10:
        return False, "Join code must be 4-10 characters long"
    
    # Join code should be alphanumeric (letters and digits only)
    if not re.match(r'^[A-Z0-9]+$', code):
        return False, "Join code must contain only letters and numbers"
    
    return True, ""


def validate_event_title(title: str) -> Tuple[bool, str]:
    """
    Validate event title.
    Returns (is_valid, error_message)
    """
    title = title.strip()
    
    if not title:
        return False, "Event title is required"
    
    if len(title) < 3:
        return False, "Event title must be at least 3 characters long"
    
    if len(title) > 100:
        return False, "Event title must be no more than 100 characters long"
    
    return True, ""
