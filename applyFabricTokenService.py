import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ApplyFabricTokenService:
    def __init__(self, BASE_URL, fabricAppId, appSecret, merchantAppId):
        # Base URL መጨረሻ ላይ '/' ካለ ማስወገድ
        self.BASE_URL = BASE_URL.rstrip('/')
        self.fabricAppId = fabricAppId
        self.appSecret = appSecret
        self.merchantAppId = merchantAppId
    
    def applyFabricToken(self):
        url = f"{self.BASE_URL}/payment/v1/token"
        headers = {
            "Content-Type": "application/json",
            "X-APP-Key": self.fabricAppId
        }
        payload = {
            "appSecret": self.appSecret
        }
        
        try:
            response = requests.post(
                url=url,
                headers=headers,
                data=json.dumps(payload),
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Fabric Token Request Error: {e}")
            if 'response' in locals() and response is not None:
                print(f"Response Content: {response.text}")
            return None
