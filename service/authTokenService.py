import requests
import json
from service.applyFabricTokenService import ApplyFabricTokenService
from utils import tools

class AuthTokenService:
    def __init__(self, BASE_URL, fabricAppId, appSecret, merchantAppId):
        self.BASE_URL = BASE_URL.rstrip('/')
        self.fabricAppId = fabricAppId
        self.appSecret = appSecret
        self.merchantAppId = merchantAppId
   
    def auth_token(self, app_token):
        """
        App token በመጠቀም የኢንተርፕራይዝ አውተንቲኬሽን ቶከን ማቀበያ method
        """
        print("Received App Token:", app_token)
        
        # Step 1: Apply Fabric Token
        fabric_service = ApplyFabricTokenService(
            self.BASE_URL, 
            self.fabricAppId, 
            self.appSecret, 
            self.merchantAppId
        )
        fabric_token_response = fabric_service.applyFabricToken()
        
        if not fabric_token_response or "token" not in fabric_token_response:
            raise Exception(f"Failed to fetch Fabric Token. Response: {fabric_token_response}")
            
        fabric_token = fabric_token_response["token"]
       
        # Step 2: Request Auth Token
        return self.request_auth_token(fabric_token, app_token)
   
    def request_auth_token(self, fabric_token, app_token):
        url = f"{self.BASE_URL}/payment/v1/auth/authToken"
        headers = {
            "Content-Type": "application/json",
            "X-APP-Key": self.fabricAppId,
            "Authorization": fabric_token
        }
       
        request_object = self.create_request_object(app_token)
       
        try:
            response = requests.post(
                url=url, 
                headers=headers, 
                json=request_object, 
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Auth Token API Error: {e}")
            if 'response' in locals() and response is not None:
                print(f"API Error Details: {response.text}")
            return None
   
    def create_request_object(self, app_token):
        req = {
            "timestamp": str(tools.create_timestamp()),
            "nonce_str": tools.create_nonce_str(),
            "method": "payment.authtoken",
            "version": "1.0",
            "app_code": self.merchantAppId
        }
       
        biz = {
            "access_token": app_token,
            "trade_type": "InApp",
            "appid": self.merchantAppId,
            "resource_type": "OpenId"
        }
       
        req["biz_content"] = biz
        # RSA Signature ማዘጋጀት
        req["sign"] = tools.sign_request_object(req)
        req["sign_type"] = "SHA256WithRSA"
       
        print("Generated Request Object:", json.dumps(req, indent=4))
        return req
