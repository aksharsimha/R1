import requests

try:
    r = requests.get("http://localhost:8501", timeout=5)
    print(f"HTTP Status: {r.status_code}")
    print(f"Content Length: {len(r.text)}")
    print("Streamlit app is running and responding cleanly on http://localhost:8501!")
except Exception as e:
    print("Error reaching http://localhost:8501:", e)
