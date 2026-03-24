"""
Integration tests for Speed Friending app
Tests the full participant and facilitator workflows
"""

import requests
import time
import json
import io
import random
from typing import Dict, Any

BASE_URL = "http://localhost:8000"
TIMEOUT = 10


class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []

    def add_pass(self, test_name: str, details: str = ""):
        self.passed.append(f"[PASS] {test_name}" + (f" - {details}" if details else ""))

    def add_fail(self, test_name: str, error: str):
        self.failed.append(f"[FAIL] {test_name}: {error}")

    def print_summary(self):
        print("\n" + "=" * 60)
        print("TEST RESULTS")
        print("=" * 60)

        for test in self.passed:
            print(test)

        for test in self.failed:
            print(test)

        print(f"\nSummary: {len(self.passed)} passed, {len(self.failed)} failed")
        print("=" * 60 + "\n")


results = TestResults()


def test_home_page():
    """Test: Home page loads successfully"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=TIMEOUT)
        assert response.status_code == 200, f"Status code: {response.status_code}"
        assert "Speed Friending" in response.text, "Home page title not found"
        results.add_pass("Home Page Loads", "Status 200, content valid")
    except Exception as e:
        results.add_fail("Home Page Loads", str(e))


def test_join_page_has_redirect_logic():
    """Test: Join page contains checkSavedSession function for auto-redirect"""
    try:
        response = requests.get(f"{BASE_URL}/join", timeout=TIMEOUT)
        assert response.status_code == 200, f"Status code: {response.status_code}"
        assert "checkSavedSession" in response.text, (
            "Join page should contain checkSavedSession function"
        )
        assert "speedfriending_participant" in response.text, (
            "Join page should check for saved participant session"
        )
        results.add_pass(
            "Join Page Has Redirect Logic",
            "checkSavedSession function present for redirect after join",
        )
    except Exception as e:
        results.add_fail("Join Page Has Redirect Logic", str(e))


def test_index_page_no_redirect():
    """Test: Index page does NOT contain checkSavedSession (no auto-redirect to participant view)"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=TIMEOUT)
        assert response.status_code == 200, f"Status code: {response.status_code}"
        assert "checkSavedSession" not in response.text, (
            "Index page should NOT contain checkSavedSession function"
        )
        results.add_pass(
            "Index Page No Redirect",
            "No auto-redirect to participant view from index page",
        )
    except Exception as e:
        results.add_fail("Index Page No Redirect", str(e))


def test_create_event() -> tuple:
    """Test: Create event via API"""
    try:
        payload = {"title": "Test Speed Friending Event"}
        response = requests.post(f"{BASE_URL}/events", json=payload, timeout=TIMEOUT)
        assert response.status_code == 200, f"Status code: {response.status_code}"

        event = response.json()
        assert "join_code" in event, "Join code not in response"
        assert event["title"] == "Test Speed Friending Event", "Title mismatch"

        join_code = event["join_code"]
        facilitator_pin = event.get("facilitator_pin", "1234")
        results.add_pass("Create Event", f"Join code: {join_code}")
        return join_code, facilitator_pin
    except Exception as e:
        results.add_fail("Create Event", str(e))
        return None, None


def test_invalid_event_title():
    """Test: Invalid event title validation"""
    try:
        # Too short
        response = requests.post(
            f"{BASE_URL}/events", json={"title": "ab"}, timeout=TIMEOUT
        )
        assert response.status_code == 400, "Should reject short title"

        # Empty
        response = requests.post(
            f"{BASE_URL}/events", json={"title": ""}, timeout=TIMEOUT
        )
        assert response.status_code == 400, "Should reject empty title"

        results.add_pass("Event Title Validation", "Correctly rejects invalid titles")
    except Exception as e:
        results.add_fail("Event Title Validation", str(e))


def test_join_participants(join_code: str) -> list:
    """Test: Multiple participants join an event"""
    if not join_code:
        results.add_fail("Join Participants", "No join code provided")
        return []

    # Alias for backward compatibility
    return test_join_participants_with_nicknames(join_code)


def test_join_participants_with_nicknames(join_code: str) -> list:
    """Test: Multiple participants join an event using nicknames"""
    if not join_code:
        results.add_fail("Join Participants", "No join code provided")
        return []

    try:
        nicknames = ["alice1", "bob2test", "charl3", "diana4"]

        participants = []
        for nickname in nicknames:
            response = requests.post(
                f"{BASE_URL}/events/{join_code}/join",
                json={"nickname": nickname},
                timeout=TIMEOUT,
            )
            assert response.status_code == 200, (
                f"Failed to join with {nickname}: {response.status_code} - {response.text}"
            )

            participant = response.json()
            assert participant["nickname"] == nickname.lower(), "Nickname mismatch"
            participants.append(participant)

        results.add_pass(
            "Join Participants", f"{len(participants)} participants joined"
        )
        return participants
    except Exception as e:
        results.add_fail("Join Participants", str(e))
        return []

    try:
        nicknames = ["alice1", "bob2", "charlie3", "diana4"]

        participants = []
        for nickname in nicknames:
            response = requests.post(
                f"{BASE_URL}/events/{join_code}/join",
                json={"nickname": nickname},
                timeout=TIMEOUT,
            )
            assert response.status_code == 200, (
                f"Failed to join with {nickname}: {response.status_code} - {response.text}"
            )

            participant = response.json()
            assert participant["nickname"] == nickname.lower(), "Nickname mismatch"
            participants.append(participant)

        results.add_pass(
            "Join Participants", f"{len(participants)} participants joined"
        )
        return participants
    except Exception as e:
        results.add_fail("Join Participants", str(e))
        return []

    try:
        nicknames = ["alice", "bob", "charlie", "diana"]

        participants = []
        for nickname in nicknames:
            response = requests.post(
                f"{BASE_URL}/events/{join_code}/join",
                json={"nickname": nickname},
                timeout=TIMEOUT,
            )
            assert response.status_code == 200, (
                f"Failed to join with {nickname}: {response.status_code}"
            )

            participant = response.json()
            assert participant["nickname"] == nickname.lower(), "Nickname mismatch"
            participants.append(participant)

        results.add_pass(
            "Join Participants", f"{len(participants)} participants joined"
        )
        return participants
    except Exception as e:
        results.add_fail("Join Participants", str(e))
        return []

    try:
        emails = [
            "alice@example.com",
            "bob@example.com",
            "charlie@example.com",
            "diana@example.com",
        ]

        participants = []
        for email in emails:
            response = requests.post(
                f"{BASE_URL}/events/{join_code}/join",
                json={"email": email},
                timeout=TIMEOUT,
            )
            assert response.status_code == 200, (
                f"Failed to join with {email}: {response.status_code}"
            )

            participant = response.json()
            assert participant["email"] == email.lower(), "Email mismatch"
            participants.append(participant)

        results.add_pass(
            "Join Participants", f"{len(participants)} participants joined"
        )
        return participants
    except Exception as e:
        results.add_fail("Join Participants", str(e))
        return []


def test_duplicate_join(join_code: str, nickname: str):
    """Test: Duplicate nickname join is rejected"""
    try:
        # Second attempt with same nickname
        response = requests.post(
            f"{BASE_URL}/events/{join_code}/join",
            json={"nickname": nickname},
            timeout=TIMEOUT,
        )
        assert response.status_code == 400, (
            f"Should reject duplicate, got {response.status_code}"
        )

        error = response.json()
        assert "already joined" in error.get("detail", "").lower(), (
            "Error message should mention duplicate"
        )

        results.add_pass(
            "Duplicate Join Prevention", "Correctly prevents duplicate nicknames"
        )
    except Exception as e:
        results.add_fail("Duplicate Join Prevention", str(e))


def test_invalid_nickname(join_code: str):
    """Test: Invalid nickname validation"""
    try:
        response = requests.post(
            f"{BASE_URL}/events/{join_code}/join",
            json={"nickname": "ab"},
            timeout=TIMEOUT,
        )
        assert response.status_code == 400, (
            f"Should reject invalid nickname, got {response.status_code}"
        )

        # Also test a valid nickname succeeds
        response = requests.post(
            f"{BASE_URL}/events/{join_code}/join",
            json={"nickname": "valid1"},
            timeout=TIMEOUT,
        )
        assert response.status_code == 200, f"Valid nickname should succeed"

        results.add_pass("Nickname Validation", "Correctly rejects invalid nicknames")
    except Exception as e:
        results.add_fail("Nickname Validation", str(e))


def test_event_state(join_code: str):
    """Test: Fetch event state"""
    try:
        response = requests.get(f"{BASE_URL}/events/{join_code}/state", timeout=TIMEOUT)
        assert response.status_code == 200, f"Status code: {response.status_code}"

        state = response.json()
        assert "join_code" in state, "Missing join_code"
        assert "status" in state, "Missing status"
        assert "participants_count" in state, "Missing participants_count"
        assert state["participants_count"] >= 4, (
            f"Expected at least 4 participants after deletion, got {state['participants_count']}"
        )

        results.add_pass(
            "Event State",
            f"Status: {state['status']}, Participants: {state['participants_count']}",
        )
    except Exception as e:
        results.add_fail("Event State", str(e))


def test_event_state_nonexistent():
    """Test: Fetch state for non-existent event returns 404 (used for session validation)"""
    try:
        fake_code = "NOTEXIST999"
        response = requests.get(f"{BASE_URL}/events/{fake_code}/state", timeout=TIMEOUT)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

        results.add_pass(
            "Event State - Non-existent Event",
            "Returns 404 for non-existent event (validates session redirect)",
        )
    except Exception as e:
        results.add_fail("Event State - Non-existent Event", str(e))


def test_start_round(join_code: str):
    """Test: Start first round (Facilitator action)"""
    try:
        response = requests.post(
            f"{BASE_URL}/events/{join_code}/start_round", timeout=TIMEOUT
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"

        data = response.json()
        assert data["round"] == 1, "First round should be 1"
        assert data["pairings_count"] > 0, "Should have pairings"

        results.add_pass(
            "Start Round", f"Round 1 started with {data['pairings_count']} pairings"
        )
        return data
    except Exception as e:
        results.add_fail("Start Round", str(e))
        return None


def test_my_match(join_code: str, nickname: str):
    """Test: Participant view of their match"""
    try:
        response = requests.get(
            f"{BASE_URL}/events/{join_code}/my_match?nickname={nickname}",
            timeout=TIMEOUT,
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"

        match = response.json()
        assert "status" in match, "Missing status"
        assert match["current_round"] == 1, "Should be round 1"

        if match["status"] == "paired":
            assert "partner" in match, "Missing partner"
            assert "nickname" in match["partner"], "Missing partner nickname"
            results.add_pass(
                "My Match Endpoint",
                f"Participant paired with {match['partner']['nickname']}",
            )
        else:
            results.add_pass(
                "My Match Endpoint", f"Status: {match['status']} (resting round)"
            )
    except Exception as e:
        results.add_fail("My Match Endpoint", str(e))


def test_mark_met(join_code: str, nickname: str):
    """Test: Mark as met endpoint"""
    try:
        response = requests.post(
            f"{BASE_URL}/events/{join_code}/mark_met",
            json={"nickname": nickname},
            timeout=TIMEOUT,
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"

        result = response.json()
        assert result["status"] == "success", "Mark as met failed"
        assert "met_at" in result, "Missing met_at timestamp"

        results.add_pass("Mark As Met", f"Successfully marked as met")
    except Exception as e:
        results.add_fail("Mark As Met", str(e))


def test_dashboard(join_code: str):
    """Test: Facilitator dashboard data endpoint"""
    try:
        response = requests.get(
            f"{BASE_URL}/events/{join_code}/dashboard", timeout=TIMEOUT
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"

        data = response.json()
        assert "event" in data, "Missing event"
        assert "participants" in data, "Missing participants"
        assert "pairings" in data, "Missing pairings"
        assert len(data["participants"]) == 5, "Should have 5 participants"

        results.add_pass(
            "Dashboard Endpoint", f"{len(data['pairings'])} pairings in current round"
        )
    except Exception as e:
        results.add_fail("Dashboard Endpoint", str(e))


def test_next_round(join_code: str):
    """Test: Advance to next round"""
    try:
        # Start with a talk phase transition to break
        response = requests.post(
            f"{BASE_URL}/events/{join_code}/next_round", timeout=TIMEOUT
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"

        data = response.json()
        assert "phase" in data, "Missing phase in response"

        results.add_pass("Next Round", f"Phase: {data.get('phase', 'unknown')}")
    except Exception as e:
        results.add_fail("Next Round", str(e))


def test_list_participants(join_code: str):
    """Test: List event participants"""
    try:
        response = requests.get(
            f"{BASE_URL}/events/{join_code}/participants", timeout=TIMEOUT
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"

        data = response.json()
        assert "participants" in data, "Missing participants"
        assert len(data["participants"]) == 5, "Should have 5 participants"

        results.add_pass(
            "List Participants", f"Listed {len(data['participants'])} participants"
        )
    except Exception as e:
        results.add_fail("List Participants", str(e))


def test_delete_participant(join_code: str, facilitator_pin: str, nickname: str):
    """Test: Delete a participant from the event"""
    try:
        response = requests.delete(
            f"{BASE_URL}/events/{join_code}/participants/{nickname}?pin={facilitator_pin}",
            timeout=TIMEOUT,
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"

        data = response.json()
        assert data["status"] == "success", "Delete should return success"

        # Verify participant was deleted
        participants_response = requests.get(
            f"{BASE_URL}/events/{join_code}/participants", timeout=TIMEOUT
        )
        participants = participants_response.json()["participants"]
        remaining_nicknames = [p["nickname"] for p in participants]
        assert nickname not in remaining_nicknames, "Participant should be removed"

        results.add_pass("Delete Participant", f"Removed '{nickname}' from event")
    except Exception as e:
        results.add_fail("Delete Participant", str(e))


def test_delete_nonexistent_participant(join_code: str, facilitator_pin: str):
    """Test: Delete non-existent participant returns 404"""
    try:
        response = requests.delete(
            f"{BASE_URL}/events/{join_code}/participants/nonexistent_user_xyz?pin={facilitator_pin}",
            timeout=TIMEOUT,
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

        results.add_pass(
            "Delete Non-existent Participant",
            "Correctly returns 404 for non-existent participant",
        )
    except Exception as e:
        results.add_fail("Delete Non-existent Participant", str(e))


def test_delete_participant_no_pin(join_code: str):
    """Test: Delete participant without PIN returns 400"""
    try:
        response = requests.delete(
            f"{BASE_URL}/events/{join_code}/participants/someone", timeout=TIMEOUT
        )
        assert response.status_code == 400 or response.status_code == 422, (
            f"Expected 400/422, got {response.status_code}"
        )

        results.add_pass(
            "Delete Participant No PIN", "Correctly requires PIN for deletion"
        )
    except Exception as e:
        results.add_fail("Delete Participant No PIN", str(e))


def test_event_info(join_code: str):
    """Test: Get event metadata via info endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/events/{join_code}/info", timeout=TIMEOUT)
        assert response.status_code == 200, f"Status code: {response.status_code}"

        info = response.json()
        assert "title" in info, "Missing title"
        assert "join_code" in info, "Missing join_code"
        assert "status" in info, "Missing status"
        assert "participant_count" in info, "Missing participant_count"
        assert info["participant_count"] >= 4, (
            f"Expected at least 4 participants after deletion, got {info['participant_count']}"
        )
        assert "total_pairings" in info, "Missing total_pairings"
        assert "total_unique_pairs" in info, "Missing total_unique_pairs"

        results.add_pass(
            "Event Info Endpoint",
            f"Retrieved metadata: {info['participant_count']} participants, {info['total_pairings']} total pairings",
        )
    except Exception as e:
        results.add_fail("Event Info Endpoint", str(e))


# ===== PHOTO UPLOAD TESTS =====


def create_test_image(width=100, height=100, format="jpeg"):
    """Create a test image in memory"""
    import struct
    import zlib

    if format == "jpeg":
        # Create a simple valid JPEG
        img = io.BytesIO()
        img.write(
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        )
        img.write(
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f"
        )
        img.write(
            b"\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
        )
        img.write(b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00")
        img.write(
            b"\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\t\x00\x02\x00\x00"
        )
        img.write(
            b"\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        )
        img.write(b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xd5G\xff\xd9")
        return img.getvalue()
    else:
        # PNG format
        def png_chunk(chunk_type, data):
            chunk = chunk_type + data
            return (
                struct.pack(">I", len(data))
                + chunk
                + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
            )

        img = io.BytesIO()
        img.write(b"\x89PNG\r\n\x1a\n")
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        img.write(png_chunk(b"IHDR", ihdr))

        raw_data = b""
        for y in range(height):
            raw_data += b"\x00"
            for x in range(width):
                raw_data += b"\xff\x00\x00"

        img.write(png_chunk(b"IDAT", zlib.compress(raw_data)))
        img.write(png_chunk(b"IEND", b""))
        return img.getvalue()


def test_upload_photo(join_code: str, nickname: str = "alice@example.com"):
    """Test: Upload a valid photo for a participant"""
    try:
        # Create a test JPEG image
        image_data = create_test_image(format="jpeg")

        files = {"photo": ("test_photo.jpg", io.BytesIO(image_data), "image/jpeg")}

        response = requests.post(
            f"{BASE_URL}/events/{join_code}/upload_photo?nickname={nickname}",
            files=files,
            timeout=TIMEOUT,
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"

        data = response.json()
        assert data.get("success") == True, "Upload should succeed"
        assert "photo_url" in data, "Missing photo_url in response"
        assert data["photo_url"] is not None, "Photo URL should not be None"

        results.add_pass("Upload Photo", f"Photo uploaded: {data['photo_url']}")
        return data["photo_url"]
    except Exception as e:
        results.add_fail("Upload Photo", str(e))
        return None


def test_upload_photo_unauthorized(join_code: str):
    """Test: Reject photo upload for non-existent participant"""
    try:
        image_data = create_test_image(format="jpeg")

        files = {"photo": ("test_photo.jpg", io.BytesIO(image_data), "image/jpeg")}

        response = requests.post(
            f"{BASE_URL}/events/{join_code}/upload_photo?nickname=nonexistent_user_12345",
            files=files,
            timeout=TIMEOUT,
        )
        assert response.status_code == 404, (
            f"Should return 404, got {response.status_code}"
        )

        results.add_pass(
            "Upload Photo Unauthorized", "Correctly rejects non-existent participant"
        )
    except Exception as e:
        results.add_fail("Upload Photo Unauthorized", str(e))


def test_upload_invalid_file_type(join_code: str, nickname: str = "alice@example.com"):
    """Test: Reject non-image files"""
    try:
        text_data = b"This is not an image"

        files = {"photo": ("test.txt", io.BytesIO(text_data), "text/plain")}

        response = requests.post(
            f"{BASE_URL}/events/{join_code}/upload_photo?nickname={nickname}",
            files=files,
            timeout=TIMEOUT,
        )
        assert response.status_code == 400, (
            f"Should return 400, got {response.status_code}"
        )

        error = response.json()
        assert "image" in error.get("detail", "").lower(), (
            "Error should mention image requirement"
        )

        results.add_pass(
            "Upload Invalid File Type", "Correctly rejects non-image files"
        )
    except Exception as e:
        results.add_fail("Upload Invalid File Type", str(e))


def test_upload_oversized_file(join_code: str, nickname: str = "alice1"):
    """Test: Reject files exceeding size limit"""
    try:
        # Create a large dummy file (>5MB)
        large_data = b"\x00" * (6 * 1024 * 1024)

        files = {"photo": ("large_photo.jpg", io.BytesIO(large_data), "image/jpeg")}

        response = requests.post(
            f"{BASE_URL}/events/{join_code}/upload_photo?nickname={nickname}",
            files=files,
            timeout=TIMEOUT,
        )
        assert response.status_code == 400, (
            f"Should return 400, got {response.status_code}"
        )

        error = response.json()
        assert (
            "size" in error.get("detail", "").lower()
            or "limit" in error.get("detail", "").lower()
        ), "Error should mention size limit"

        results.add_pass("Upload Oversized File", "Correctly rejects oversized files")
    except Exception as e:
        results.add_fail("Upload Oversized File", str(e))


def test_participants_include_photo(join_code: str):
    """Test: Verify participants endpoint includes photo URLs"""
    try:
        response = requests.get(
            f"{BASE_URL}/events/{join_code}/participants", timeout=TIMEOUT
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"

        data = response.json()
        assert "participants" in data, "Missing participants"

        # Check that participants have photo fields
        for participant in data["participants"]:
            assert "photo_filename" in participant, (
                f"Missing photo_filename for {participant.get('nickname')}"
            )
            assert "photo_url" in participant, (
                f"Missing photo_url for {participant.get('nickname')}"
            )

        results.add_pass(
            "Participants Include Photo",
            f"All {len(data['participants'])} participants have photo fields",
        )
    except Exception as e:
        results.add_fail("Participants Include Photo", str(e))


def test_my_match_includes_photo(join_code: str, nickname: str = "alice@example.com"):
    """Test: Verify my_match endpoint includes partner photo"""
    try:
        response = requests.get(
            f"{BASE_URL}/events/{join_code}/my_match?nickname={nickname}",
            timeout=TIMEOUT,
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"

        match = response.json()

        if match.get("status") == "paired" and match.get("partner"):
            assert "photo_url" in match["partner"], "Missing photo_url in partner"
            results.add_pass(
                "My Match Includes Photo",
                f"Partner photo_url: {match['partner'].get('photo_url')}",
            )
        else:
            results.add_pass(
                "My Match Includes Photo", "Participant not paired in current round"
            )
    except Exception as e:
        results.add_fail("My Match Includes Photo", str(e))


def test_break_phase_next_partner_photo(
    join_code: str, nickname: str = "alice@example.com"
):
    """Test: Verify break phase shows next partner with photo"""
    try:
        response = requests.get(
            f"{BASE_URL}/events/{join_code}/my_match?nickname={nickname}",
            timeout=TIMEOUT,
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"

        match = response.json()

        # If in break phase and has next partner
        if (
            match.get("phase") == "break"
            and match.get("status") == "next_partner_preview"
        ):
            assert "photo_url" in match.get("next_partner", {}), (
                "Missing photo_url in next_partner"
            )
            results.add_pass(
                "Break Phase Next Partner Photo",
                f"Next partner has photo: {match['next_partner'].get('photo_url')}",
            )
        elif match.get("phase") == "break":
            results.add_pass(
                "Break Phase Next Partner Photo",
                f"Status: {match.get('status')} (no next partner yet)",
            )
        else:
            results.add_pass(
                "Break Phase Next Partner Photo",
                f"Not in break phase, current phase: {match.get('phase')}",
            )
    except Exception as e:
        results.add_fail("Break Phase Next Partner Photo", str(e))


def test_join_response_includes_photo_fields():
    """Test: Verify join response includes photo fields"""
    try:
        # Create a new event for this test
        create_response = requests.post(
            f"{BASE_URL}/events", json={"title": "Photo Test Event"}, timeout=TIMEOUT
        )
        test_join_code = create_response.json()["join_code"]

        # Join with a nickname
        join_response = requests.post(
            f"{BASE_URL}/events/{test_join_code}/join",
            json={"nickname": "tester123"},
            timeout=TIMEOUT,
        )
        assert join_response.status_code == 200, (
            f"Join failed: {join_response.status_code}"
        )

        participant = join_response.json()

        # Verify photo fields are in response
        assert "photo_filename" in participant, "Missing photo_filename"
        assert "photo_uploaded_at" in participant, "Missing photo_uploaded_at"
        assert "photo_url" in participant, "Missing photo_url"

        results.add_pass(
            "Join Response Includes Photo Fields",
            "All photo fields present in join response",
        )
    except Exception as e:
        results.add_fail("Join Response Includes Photo Fields", str(e))


# ===== RUN ALL TESTS =====

print("\nStarting Speed Friending Integration Tests...\n")

# Test 1: Home page
test_home_page()
time.sleep(0.5)

# Test 1b: Join page has redirect logic
test_join_page_has_redirect_logic()
time.sleep(0.5)

# Test 1c: Index page does NOT have redirect logic
test_index_page_no_redirect()
time.sleep(0.5)

# Test 2: Event creation
join_code, facilitator_pin = test_create_event()
time.sleep(0.5)

# Test 3: Invalid inputs
test_invalid_event_title()
time.sleep(0.5)

# Test join response includes photo fields (creates its own event)
test_join_response_includes_photo_fields()
time.sleep(0.5)

if join_code:
    # Test 4: Join participants (using nickname)
    participants = test_join_participants_with_nicknames(join_code)
    time.sleep(0.5)

    # Get alice1 nickname for photo tests
    alice_nickname = participants[0]["nickname"] if participants else "alice1"

    # Test 5: Duplicate join prevention
    if participants:
        test_duplicate_join(join_code, participants[0]["nickname"])
        time.sleep(0.5)

    # Test 6: Invalid nickname
    test_invalid_nickname(join_code)
    time.sleep(0.5)

    # Test 7: Event state
    test_event_state(join_code)
    time.sleep(0.5)

    # Test 7b: Event state for non-existent event (validates session redirect)
    test_event_state_nonexistent()
    time.sleep(0.5)

    # Test 8: Start round (facilitator)
    round_data = test_start_round(join_code)
    time.sleep(1)

    # Test 9: Upload photo (using nickname)
    test_upload_photo(join_code, alice_nickname)
    time.sleep(0.5)

    # Test 10: Upload photo for unauthorized user
    test_upload_photo_unauthorized(join_code)
    time.sleep(0.5)

    # Test 11: Upload invalid file type
    test_upload_invalid_file_type(join_code, alice_nickname)
    time.sleep(0.5)

    # Test 12: Upload oversized file
    test_upload_oversized_file(join_code)
    time.sleep(0.5)

    # Test 13: Participants include photo fields
    test_participants_include_photo(join_code)
    time.sleep(0.5)

    # Test 14: My match includes photo
    test_my_match_includes_photo(join_code, alice_nickname)
    time.sleep(0.5)

    # Test 15: Participant views their match (using nickname)
    if participants:
        test_my_match(join_code, participants[0]["nickname"])
        time.sleep(0.5)

        # Test 16: Mark as met
        test_mark_met(join_code, participants[0]["nickname"])
        time.sleep(0.5)

    # Test 17: Dashboard endpoint
    test_dashboard(join_code)
    time.sleep(0.5)

    # Test 18: List participants
    test_list_participants(join_code)
    time.sleep(0.5)

    # Test 19: Break phase next partner photo (run before delete tests)
    test_break_phase_next_partner_photo(join_code, alice_nickname)
    time.sleep(0.5)

    # Test 20: Delete participant (use first participant's nickname)
    if participants and facilitator_pin:
        test_delete_participant(join_code, facilitator_pin, participants[0]["nickname"])
        time.sleep(0.5)

        # Test 21: Delete non-existent participant
        test_delete_nonexistent_participant(join_code, facilitator_pin)
        time.sleep(0.5)

        # Test 22: Delete participant without PIN
        test_delete_participant_no_pin(join_code)
        time.sleep(0.5)

    # Test 23: Event info endpoint (after deletion, should have 4 participants)
    test_event_info(join_code)
    time.sleep(0.5)

# Print results
results.print_summary()

# Exit with appropriate code
if results.failed:
    exit(1)
else:
    exit(0)
