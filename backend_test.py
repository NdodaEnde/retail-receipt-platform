import requests
import sys
import json
from datetime import datetime, timedelta

class RetailRewardsAPITester:
    def __init__(self, base_url="https://retail-rewards-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                if isinstance(data, dict):
                    response = requests.post(url, json=data, headers=headers)
                else:
                    # For form data
                    response = requests.post(url, data=data, headers={'Accept': 'application/json'})

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    self.test_results.append({
                        "test": name,
                        "status": "PASS",
                        "response_code": response.status_code,
                        "response_data": response_data
                    })
                    return True, response_data
                except:
                    self.test_results.append({
                        "test": name,
                        "status": "PASS",
                        "response_code": response.status_code,
                        "response_data": response.text
                    })
                    return True, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"Response: {response.text}")
                self.test_results.append({
                    "test": name,
                    "status": "FAIL",
                    "response_code": response.status_code,
                    "expected_code": expected_status,
                    "response_data": response.text
                })
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.test_results.append({
                "test": name,
                "status": "ERROR",
                "error": str(e)
            })
            return False, {}

    def test_health_check(self):
        """Test health endpoint"""
        return self.run_test("Health Check", "GET", "health", 200)

    def test_analytics_overview(self):
        """Test analytics overview endpoint"""
        return self.run_test("Analytics Overview", "GET", "analytics/overview", 200)

    def test_demo_seed(self):
        """Test demo data seeding"""
        return self.run_test("Demo Data Seed", "POST", "demo/seed", 200)

    def test_customer_creation(self):
        """Test customer creation"""
        customer_data = {
            "phone_number": "+1234567890",
            "name": "Test Customer"
        }
        return self.run_test("Create Customer", "POST", "customers", 200, customer_data)

    def test_get_customer(self, phone_number="+1234567890"):
        """Test getting customer by phone number"""
        return self.run_test("Get Customer", "GET", f"customers/{phone_number}", 200)

    def test_list_customers(self):
        """Test listing customers"""
        return self.run_test("List Customers", "GET", "customers", 200)

    def test_receipt_upload(self):
        """Test receipt upload"""
        form_data = {
            'phone_number': '+1234567890',
            'shop_name': 'Test Shop',
            'amount': '25.99',
            'receipt_text': 'Test Shop\nItem 1 $10.00\nItem 2 $15.99\nTotal $25.99',
            'latitude': '40.7128',
            'longitude': '-74.0060'
        }
        return self.run_test("Upload Receipt", "POST", "receipts/upload", 200, form_data)

    def test_get_customer_receipts(self, phone_number="+1234567890"):
        """Test getting customer receipts"""
        return self.run_test("Get Customer Receipts", "GET", f"receipts/customer/{phone_number}", 200)

    def test_list_receipts(self):
        """Test listing all receipts"""
        return self.run_test("List Receipts", "GET", "receipts", 200)

    def test_list_shops(self):
        """Test listing shops"""
        return self.run_test("List Shops", "GET", "shops", 200)

    def test_map_shops(self):
        """Test map shops endpoint"""
        return self.run_test("Map Shops", "GET", "map/shops", 200)

    def test_map_receipts(self):
        """Test map receipts endpoint"""
        return self.run_test("Map Receipts", "GET", "map/receipts", 200)

    def test_run_draw(self):
        """Test running a daily draw"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.run_test("Run Daily Draw", "POST", f"draws/run?draw_date={today}", 200)

    def test_list_draws(self):
        """Test listing draws"""
        return self.run_test("List Draws", "GET", "draws", 200)

    def test_analytics_endpoints(self):
        """Test various analytics endpoints"""
        endpoints = [
            ("Spending by Day", "analytics/spending-by-day"),
            ("Popular Shops", "analytics/popular-shops"),
            ("Top Spenders", "analytics/top-spenders"),
            ("Receipts by Hour", "analytics/receipts-by-hour"),
            ("Spending by Shop", "analytics/spending-by-shop")
        ]
        
        results = []
        for name, endpoint in endpoints:
            success, data = self.run_test(name, "GET", endpoint, 200)
            results.append((name, success, data))
        
        return results

    def test_whatsapp_endpoints(self):
        """Test WhatsApp endpoints (expected to be mocked)"""
        endpoints = [
            ("WhatsApp Status", "whatsapp/status"),
            ("WhatsApp QR", "whatsapp/qr")
        ]
        
        results = []
        for name, endpoint in endpoints:
            success, data = self.run_test(name, "GET", endpoint, 200)
            results.append((name, success, data))
            
            # Verify mocked response
            if success and name == "WhatsApp Status":
                if data.get("connected") == False:
                    print(f"✅ WhatsApp correctly shows as disconnected (mocked)")
                else:
                    print(f"⚠️  WhatsApp status unexpected: {data}")
        
        return results

def main():
    print("🚀 Starting Retail Rewards Platform API Tests")
    print("=" * 60)
    
    tester = RetailRewardsAPITester()
    
    # Test basic endpoints
    print("\n📋 Testing Basic Endpoints...")
    tester.test_health_check()
    tester.test_analytics_overview()
    
    # Test demo data seeding
    print("\n🌱 Testing Demo Data...")
    tester.test_demo_seed()
    
    # Test customer endpoints
    print("\n👥 Testing Customer Endpoints...")
    tester.test_customer_creation()
    tester.test_get_customer()
    tester.test_list_customers()
    
    # Test receipt endpoints
    print("\n🧾 Testing Receipt Endpoints...")
    tester.test_receipt_upload()
    tester.test_get_customer_receipts()
    tester.test_list_receipts()
    
    # Test shop endpoints
    print("\n🏪 Testing Shop Endpoints...")
    tester.test_list_shops()
    
    # Test map endpoints
    print("\n🗺️  Testing Map Endpoints...")
    tester.test_map_shops()
    tester.test_map_receipts()
    
    # Test draw endpoints
    print("\n🎰 Testing Draw Endpoints...")
    tester.test_run_draw()
    tester.test_list_draws()
    
    # Test analytics endpoints
    print("\n📊 Testing Analytics Endpoints...")
    tester.test_analytics_endpoints()
    
    # Test WhatsApp endpoints (mocked)
    print("\n📱 Testing WhatsApp Endpoints (Mocked)...")
    tester.test_whatsapp_endpoints()
    
    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 Final Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"❌ {tester.tests_run - tester.tests_passed} tests failed")
        
        # Print failed tests
        print("\n❌ Failed Tests:")
        for result in tester.test_results:
            if result["status"] in ["FAIL", "ERROR"]:
                print(f"  - {result['test']}: {result.get('error', 'Status code mismatch')}")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())