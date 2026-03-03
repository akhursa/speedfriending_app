"""
Validation utilities for the speed friending app
"""

import re
from typing import Tuple


def validate_nickname(nickname: str) -> Tuple[bool, str]:
    """
    Returns (is_valid, error_message)
    """
    nickname = nickname.strip()

    if not nickname:
        return False, "Nickname is required"

    if len(nickname) < 5:
        return False, "Nickname must be at least 5 characters long"

    if len(nickname) > 50:
        return False, "Nickname must be no more than 50 characters long"

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
    if not re.match(r"^[A-Z0-9]+$", code):
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


def validate_question(question: str) -> Tuple[bool, str]:
    """
    Validate a single question.
    Returns (is_valid, error_message)
    """
    if not question:
        return False, "Question cannot be empty"

    question = question.strip()

    if not question:
        return False, "Question cannot be empty or whitespace only"

    if len(question) < 5:
        return False, "Question must be at least 5 characters"

    if len(question) > 500:
        return False, "Question must be max 500 characters"

    return True, ""


def validate_questions_batch(questions: list[str]) -> Tuple[bool, str]:
    """
    Validate a batch of questions.
    Returns (is_valid, error_message)
    """
    if not questions or len(questions) == 0:
        return False, "At least one question required"

    if len(questions) > 50:
        return False, "Maximum 50 questions allowed"

    # Check each question
    for i, q in enumerate(questions):
        valid, error = validate_question(q)
        if not valid:
            return False, f"Question {i+1}: {error}"

    return True, ""
