import requests
import json

# ENACTdb API endpoint
url = "https://www.iscbglab.in/enactdb/ncbid/1/?format=api"

print("Connecting to ENACTdb...")

try:
    import certifi
    response = requests.get(
        url,
        headers={"Accept": "text/html"},
        timeout=60,
    )

    print("\nHTTP Status:", response.status_code)
    print("Content Type:", response.headers.get("Content-Type"))
    print("Final URL:", response.url)

    response.raise_for_status()

    # Save the original response
    with open("data/enact_response_raw.txt", "w") as f:
        f.write(response.text)

    # Parse JSON
    data = response.json()

    print("\nResponse successfully converted to JSON!")

    print("\nResponse structure:")

    if isinstance(data, dict):
        for key, value in data.items():
            print(f"\n{key}: {type(value).__name__}")

            if isinstance(value, list):
                print("Number of entries:", len(value))

            elif isinstance(value, dict):
                print("Available fields:", list(value.keys()))

    elif isinstance(data, list):
        print("Number of entries:", len(data))

    # Save formatted JSON
    with open("data/enact_response.json", "w") as f:
        json.dump(data, f, indent=4)

    print("\nJSON saved successfully!")
    print("Location: data/enact_response.json")

except requests.exceptions.RequestException as e:
    print("\nConnection error:", e)

except json.JSONDecodeError:
    print("\nThe server did not return valid JSON.")
    print("Check data/enact_response_raw.txt")
