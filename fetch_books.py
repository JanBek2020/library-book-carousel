import requests
import json
import os

# Configuration
ALMA_API_KEY = os.environ.get('ALMA_API_KEY')
ALMA_BASE_URL = 'https://api-na.hosted.exlibrisgroup.com'
TEST_MMS_ID = '99179893604141'

def test_single_book():
    """Test retrieving a single book by MMS ID"""
    
    headers = {
        'Authorization': f'apikey {ALMA_API_KEY}',
        'Accept': 'application/json'
    }
    
    # Direct retrieval by MMS ID - this should work
    url = f'{ALMA_BASE_URL}/almaws/v1/bibs/{TEST_MMS_ID}'
    
    print(f"Testing API with MMS ID: {TEST_MMS_ID}")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n✓ SUCCESS! API connection works!")
            print(f"\nTitle: {data.get('title', 'N/A')}")
            print(f"Author: {data.get('author', 'N/A')}")
            print(f"MMS ID: {data.get('mms_id', 'N/A')}")
            
            # Show full response for debugging
            print("\nFull response:")
            print(json.dumps(data, indent=2))
            
            return data
        else:
            print(f"\n✗ Error response: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"\n✗ Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return None

if __name__ == '__main__':
    test_single_book()
