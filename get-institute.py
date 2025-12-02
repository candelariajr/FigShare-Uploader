import requests

BASE_URL = "https://api.figshare.com/v2"
token = ""

headers = {
    "Authorization": f"token {token}"
}

# Call the endpoint to get your institution info
r = requests.get(f"{BASE_URL}/account/institution", headers=headers)

print(r.status_code)
print(r.json())
