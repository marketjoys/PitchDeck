import requests
import sys
import json
from datetime import datetime

class DeckCraftAPITester:
    def __init__(self, base_url="https://pitchscore-dash.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.created_deck_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and len(str(response_data)) < 500:
                        print(f"   Response: {response_data}")
                    elif isinstance(response_data, list):
                        print(f"   Response: List with {len(response_data)} items")
                    else:
                        print(f"   Response: Large data object")
                except:
                    print(f"   Response: Non-JSON response")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text[:200]}")

            return success, response.json() if response.content else {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout (30s)")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "health",
            200
        )
        if success:
            perplexity_status = response.get('perplexity_api', 'unknown')
            print(f"   Perplexity API Status: {perplexity_status}")
        return success

    def test_get_templates(self):
        """Test templates endpoint"""
        success, response = self.run_test(
            "Get Templates",
            "GET", 
            "templates",
            200
        )
        if success and isinstance(response, list):
            print(f"   Found {len(response)} templates")
            for template in response:
                print(f"   - {template.get('name', 'Unknown')}: {template.get('description', 'No description')}")
        return success

    def test_create_deck(self):
        """Test deck creation"""
        deck_data = {
            "title": f"Test Deck {datetime.now().strftime('%H%M%S')}",
            "description": "This is a test deck created by automated testing",
            "template_id": "startup_pitch"
        }
        
        success, response = self.run_test(
            "Create Deck",
            "POST",
            "decks",
            200,
            data=deck_data
        )
        
        if success and 'id' in response:
            self.created_deck_id = response['id']
            print(f"   Created deck with ID: {self.created_deck_id}")
            print(f"   Deck has {len(response.get('slides', []))} slides")
        return success

    def test_get_decks(self):
        """Test getting user decks"""
        success, response = self.run_test(
            "Get User Decks",
            "GET",
            "decks",
            200
        )
        if success and isinstance(response, list):
            print(f"   Found {len(response)} decks")
        return success

    def test_get_deck_by_id(self):
        """Test getting specific deck"""
        if not self.created_deck_id:
            print("❌ Skipping - No deck ID available")
            return False
            
        success, response = self.run_test(
            "Get Deck by ID",
            "GET",
            f"decks/{self.created_deck_id}",
            200
        )
        if success:
            print(f"   Retrieved deck: {response.get('title', 'Unknown')}")
        return success

    def test_update_slide(self):
        """Test updating a slide"""
        if not self.created_deck_id:
            print("❌ Skipping - No deck ID available")
            return False
            
        # First get the deck to find a slide ID
        try:
            deck_response = requests.get(f"{self.api_url}/decks/{self.created_deck_id}")
            deck_data = deck_response.json()
            if deck_data.get('slides'):
                slide_id = deck_data['slides'][0]['id']
                
                slide_update = {
                    "title": "Updated Test Slide",
                    "content": "This slide was updated by automated testing"
                }
                
                success, response = self.run_test(
                    "Update Slide",
                    "PUT",
                    f"decks/{self.created_deck_id}/slides/{slide_id}",
                    200,
                    data=slide_update
                )
                return success
        except Exception as e:
            print(f"❌ Failed to update slide: {str(e)}")
            return False

    def test_market_research(self):
        """Test market research endpoint"""
        research_data = {
            "query": "AI market size and growth trends in 2024",
            "industry": "artificial intelligence",
            "max_tokens": 1000
        }
        
        success, response = self.run_test(
            "Market Research",
            "POST",
            "research/market-analysis",
            200,
            data=research_data
        )
        
        if success:
            print(f"   Research type: {response.get('research_type', 'unknown')}")
            if response.get('data', {}).get('content'):
                content_length = len(response['data']['content'])
                print(f"   Content length: {content_length} characters")
                print(f"   Citations: {len(response.get('data', {}).get('citations', []))}")
        return success

    def test_competitive_analysis(self):
        """Test competitive analysis endpoint"""
        research_data = {
            "query": "Competitive analysis for pitch deck software",
            "company": "DeckCraft Pro",
            "industry": "software",
            "max_tokens": 1000
        }
        
        success, response = self.run_test(
            "Competitive Analysis",
            "POST",
            "research/competitive-analysis",
            200,
            data=research_data
        )
        
        if success:
            print(f"   Research type: {response.get('research_type', 'unknown')}")
            if response.get('data', {}).get('content'):
                content_length = len(response['data']['content'])
                print(f"   Content length: {content_length} characters")
        return success

    def test_content_generation(self):
        """Test content generation endpoint"""
        research_data = {
            "query": "Generate compelling problem statement for AI startup pitch deck",
            "max_tokens": 800
        }
        
        success, response = self.run_test(
            "Content Generation",
            "POST",
            "research/content-generation",
            200,
            data=research_data
        )
        
        if success:
            print(f"   Research type: {response.get('research_type', 'unknown')}")
            if response.get('data', {}).get('content'):
                content_length = len(response['data']['content'])
                print(f"   Content length: {content_length} characters")
        return success

def main():
    print("🚀 Starting DeckCraft Pro API Testing...")
    print("=" * 60)
    
    tester = DeckCraftAPITester()
    
    # Run all tests
    tests = [
        tester.test_health_check,
        tester.test_get_templates,
        tester.test_create_deck,
        tester.test_get_decks,
        tester.test_get_deck_by_id,
        tester.test_update_slide,
        tester.test_market_research,
        tester.test_competitive_analysis,
        tester.test_content_generation
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
    
    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 Final Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed! Backend is working correctly.")
        return 0
    else:
        failed_tests = tester.tests_run - tester.tests_passed
        print(f"⚠️  {failed_tests} test(s) failed. Check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())