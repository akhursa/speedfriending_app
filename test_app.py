"""
Integration tests for Speed Friending app
Tests the full participant and facilitator workflows
"""
import requests
import time
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"
TIMEOUT = 10

class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
    
    def add_pass(self, test_name: str, details: str = ""):
        self.passed.append(f"✅ {test_name}" + (f" - {details}" if details else ""))
    
    def add_fail(self, test_name: str, error: str):
        self.failed.append(f"❌ {test_name}: {error}")
    
    def print_summary(self):
        print("\n" + "="*60)
        print("TEST RESULTS")
        print("="*60)
        
        for test in self.passed:
            print(test)
        
        for test in self.failed:
            print(test)
        
        print(f"\n📊 Summary: {len(self.passed)} passed, {len(self.failed)} failed")
        print("="*60 + "\n")

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

def test_create_event() -> str:
    """Test: Create event via API"""
    try:
        payload = {"title": "Test Speed Friending Event"}
        response = requests.post(
            f"{BASE_URL}/events",
            json=payload,
            timeout=TIMEOUT
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        event = response.json()
        assert "join_code" in event, "Join code not in response"
        assert event["title"] == "Test Speed Friending Event", "Title mismatch"
        
        join_code = event["join_code"]
        results.add_pass("Create Event", f"Join code: {join_code}")
        return join_code
    except Exception as e:
        results.add_fail("Create Event", str(e))
        return None

def test_invalid_event_title():
    """Test: Invalid event title validation"""
    try:
        # Too short
        response = requests.post(
            f"{BASE_URL}/events",
            json={"title": "ab"},
            timeout=TIMEOUT
        )
        assert response.status_code == 400, "Should reject short title"
        
        # Empty
        response = requests.post(
            f"{BASE_URL}/events",
            json={"title": ""},
            timeout=TIMEOUT
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
    
    try:
        emails = [
            "alice@example.com",
            "bob@example.com",
            "charlie@example.com",
            "diana@example.com"
        ]
        
        participants = []
        for email in emails:
            response = requests.post(
                f"{BASE_URL}/events/{join_code}/join",
                json={"email": email},
                timeout=TIMEOUT
            )
            assert response.status_code == 200, f"Failed to join with {email}: {response.status_code}"
            
            participant = response.json()
            assert participant["email"] == email.lower(), "Email mismatch"
            participants.append(participant)
        
        results.add_pass("Join Participants", f"{len(participants)} participants joined")
        return participants
    except Exception as e:
        results.add_fail("Join Participants", str(e))
        return []

def test_duplicate_join(join_code: str, email: str):
    """Test: Duplicate email join is rejected"""
    try:
        # Second attempt with same email
        response = requests.post(
            f"{BASE_URL}/events/{join_code}/join",
            json={"email": email},
            timeout=TIMEOUT
        )
        assert response.status_code == 400, f"Should reject duplicate, got {response.status_code}"
        
        error = response.json()
        assert "already joined" in error.get("detail", "").lower(), "Error message should mention duplicate"
        
        results.add_pass("Duplicate Join Prevention", "Correctly prevents duplicate emails")
    except Exception as e:
        results.add_fail("Duplicate Join Prevention", str(e))

def test_invalid_email(join_code: str):
    """Test: Invalid email validation"""
    try:
        response = requests.post(
            f"{BASE_URL}/events/{join_code}/join",
            json={"email": "not-an-email"},
            timeout=TIMEOUT
        )
        assert response.status_code == 400, f"Should reject invalid email, got {response.status_code}"
        
        results.add_pass("Email Validation", "Correctly rejects invalid emails")
    except Exception as e:
        results.add_fail("Email Validation", str(e))

def test_event_state(join_code: str):
    """Test: Fetch event state"""
    try:
        response = requests.get(
            f"{BASE_URL}/events/{join_code}/state",
            timeout=TIMEOUT
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        state = response.json()
        assert "join_code" in state, "Missing join_code"
        assert "status" in state, "Missing status"
        assert "participants_count" in state, "Missing participants_count"
        assert state["participants_count"] == 4, f"Expected 4 participants, got {state['participants_count']}"
        
        results.add_pass("Event State", f"Status: {state['status']}, Participants: {state['participants_count']}")
    except Exception as e:
        results.add_fail("Event State", str(e))

def test_start_round(join_code: str):
    """Test: Start first round (Facilitator action)"""
    try:
        response = requests.post(
            f"{BASE_URL}/events/{join_code}/start_round",
            timeout=TIMEOUT
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        data = response.json()
        assert data["round"] == 1, "First round should be 1"
        assert data["pairings_count"] > 0, "Should have pairings"
        
        results.add_pass("Start Round", f"Round 1 started with {data['pairings_count']} pairings")
        return data
    except Exception as e:
        results.add_fail("Start Round", str(e))
        return None

def test_my_match(join_code: str, email: str):
    """Test: Participant view of their match"""
    try:
        response = requests.get(
            f"{BASE_URL}/events/{join_code}/my_match?email={email}",
            timeout=TIMEOUT
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        match = response.json()
        assert "status" in match, "Missing status"
        assert match["current_round"] == 1, "Should be round 1"
        
        if match["status"] == "paired":
            assert "partner" in match, "Missing partner"
            assert "email" in match["partner"], "Missing partner email"
            results.add_pass("My Match Endpoint", f"Participant paired with {match['partner']['email']}")
        else:
            results.add_pass("My Match Endpoint", f"Status: {match['status']} (resting round)")
    except Exception as e:
        results.add_fail("My Match Endpoint", str(e))

def test_mark_met(join_code: str, email: str):
    """Test: Mark as met endpoint"""
    try:
        response = requests.post(
            f"{BASE_URL}/events/{join_code}/mark_met",
            json={"email": email},
            timeout=TIMEOUT
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
            f"{BASE_URL}/events/{join_code}/dashboard",
            timeout=TIMEOUT
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        data = response.json()
        assert "event" in data, "Missing event"
        assert "participants" in data, "Missing participants"
        assert "pairings" in data, "Missing pairings"
        assert len(data["participants"]) == 4, "Should have 4 participants"
        
        results.add_pass("Dashboard Endpoint", f"{len(data['pairings'])} pairings in current round")
    except Exception as e:
        results.add_fail("Dashboard Endpoint", str(e))

def test_next_round(join_code: str):
    """Test: Advance to next round"""
    try:
        # Start with a talk phase transition to break
        response = requests.post(
            f"{BASE_URL}/events/{join_code}/next_round",
            timeout=TIMEOUT
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
            f"{BASE_URL}/events/{join_code}/participants",
            timeout=TIMEOUT
        )
        assert response.status_code == 200, f"Status code: {response.status_code}"
        
        data = response.json()
        assert "participants" in data, "Missing participants"
        assert len(data["participants"]) == 4, "Should have 4 participants"
        
        results.add_pass("List Participants", f"Listed {len(data['participants'])} participants")
    except Exception as e:
        results.add_fail("List Participants", str(e))

# ===== RUN ALL TESTS =====

print("\n🚀 Starting Speed Friending Integration Tests...\n")

# Test 1: Home page
test_home_page()
time.sleep(0.5)

# Test 2: Event creation
join_code = test_create_event()
time.sleep(0.5)

# Test 3: Invalid inputs
test_invalid_event_title()
time.sleep(0.5)

if join_code:
    # Test 4: Join participants
    participants = test_join_participants(join_code)
    time.sleep(0.5)
    
    # Test 5: Duplicate join prevention
    if participants:
        test_duplicate_join(join_code, participants[0]["email"])
        time.sleep(0.5)
    
    # Test 6: Invalid email
    test_invalid_email(join_code)
    time.sleep(0.5)
    
    # Test 7: Event state
    test_event_state(join_code)
    time.sleep(0.5)
    
    # Test 8: Start round (facilitator)
    round_data = test_start_round(join_code)
    time.sleep(1)
    
    # Test 9: Participant views their match
    if participants:
        test_my_match(join_code, participants[0]["email"])
        time.sleep(0.5)
        
        # Test 10: Mark as met
        test_mark_met(join_code, participants[0]["email"])
        time.sleep(0.5)
    
    # Test 11: Dashboard endpoint
    test_dashboard(join_code)
    time.sleep(0.5)
    
    # Test 12: List participants
    test_list_participants(join_code)
    time.sleep(0.5)
    
    # Test 13: Next round
    # Wait 2 seconds to allow for break phase timing
    time.sleep(2)
    test_next_round(join_code)

# Print results
results.print_summary()

# Exit with appropriate code
if results.failed:
    exit(1)
else:
    exit(0)
