import requests
import time
import subprocess
import os
import signal
import json
import sqlite3

BASE_URL = "http://localhost:8000"
TEST_USER = "test_bot_999"
TEST_MOVIE_ID = 27205  # Inception

def start_server():
    print("Starting server...")
    # Use the existing run_server.sh script
    process = subprocess.Popen(["./run_server.sh"], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE,
                             preexec_fn=os.setsid)
    
    # Wait for server to be ready
    for _ in range(30):
        try:
            response = requests.get(BASE_URL)
            if response.status_code == 200:
                print("Server is up!")
                return process
        except:
            time.sleep(1)
    
    print("Server failed to start")
    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    exit(1)

def run_test(name, method, endpoint, payload=None):
    start = time.time()
    url = f"{BASE_URL}{endpoint}"
    print(f"\n>>> TESTING: {name}")
    try:
        if method == "GET":
            resp = requests.get(url)
        elif method == "POST":
            resp = requests.post(url, json=payload)
        elif method == "DELETE":
            resp = requests.delete(url)
        
        duration = time.time() - start
        status = "PASS" if resp.status_code < 400 else f"FAIL ({resp.status_code})"
        print(f"[{status}] {name} | {duration:.4f}s")
        
        try:
            output = resp.json()
            print("Response Output:")
            print(json.dumps(output, indent=2))
            return output
        except:
            print(f"Raw Response: {resp.text}")
            return resp.text

    except Exception as e:
        print(f"[ERROR] {name}: {e}")
        return None

def main():
    server_process = start_server()
    
    print("\n--- Running API Integration Tests ---")
    
    # 1. Root
    run_test("Root Health Check", "GET", "/")

    # 2. Encode User
    user_data = {
        "name": TEST_USER,
        "genres": ["Action", "Sci-Fi"],
        "movie_ids": [TEST_MOVIE_ID],
        "personas": ["persona_The_Thrill_Seeker"]
    }
    run_test("Create/Encode User", "POST", "/encode", user_data)

    # 3. Get Profile
    run_test("Get User Profile", "GET", f"/users/{TEST_USER}")

    # 4. Watchlist Add
    run_test("Add to Watchlist", "POST", f"/users/{TEST_USER}/watchlist", {"movie_id": 157336})

    # 5. Watchlist Remove
    run_test("Remove from Watchlist", "DELETE", f"/users/{TEST_USER}/watchlist/157336")

    # 6. Rate Movie (Like) - This triggers re-encoding
    run_test("Rate Movie (Like)", "POST", f"/users/{TEST_USER}/ratings", {"movie_id": 550, "rating": "like"})

    # 7. Sync Shown
    run_test("Sync Shown Movies", "POST", f"/users/{TEST_USER}/sync", {"shown_ids": [101, 102]})

    # 8. Get Recommendations
    run_test("Get Recommendations", "GET", f"/users/{TEST_USER}/recommendations?top_k=5")

    print("\n--- Tests Complete ---")
    
    # Cleanup
    print("\nShutting down server...")
    os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
    
    db_path = "data/user_profiles.sqlite3"
    if os.path.exists(db_path):
        with sqlite3.connect(db_path) as conn:
            conn.execute("DELETE FROM user_profiles WHERE user_id = ?", (TEST_USER,))
            conn.commit()
        print(f"Cleaned up test user from SQLite: {TEST_USER}")

if __name__ == "__main__":
    main()
