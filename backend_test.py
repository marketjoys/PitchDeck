import requests
import sys
import json
from datetime import datetime
try:
    from PIL import Image
except ImportError:
    print("Warning: PIL not available, image upload test may fail")

class DeckCraftAPITester:
    def __init__(self, base_url="https://deck-sync-upgrade.preview.emergentagent.com"):
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

    def test_get_stock_images(self):
        """Test stock images endpoint"""
        success, response = self.run_test(
            "Get Stock Images",
            "GET",
            "images/stock",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   Found {len(response)} stock images")
            if response:
                first_image = response[0]
                print(f"   Sample image: {first_image.get('title', 'Unknown')} ({first_image.get('category', 'No category')})")
                print(f"   Image has URL: {'url' in first_image}")
                print(f"   Image has tags: {len(first_image.get('tags', []))} tags")
        return success

    def test_get_stock_images_by_category(self):
        """Test stock images endpoint with category filter"""
        success, response = self.run_test(
            "Get Stock Images by Category",
            "GET",
            "images/stock?category=presentation",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   Found {len(response)} presentation images")
            # Verify all returned images are in the presentation category
            if response:
                categories = [img.get('category') for img in response]
                all_presentation = all(cat == 'presentation' for cat in categories)
                print(f"   All images in presentation category: {all_presentation}")
        return success

    def test_image_upload(self):
        """Test image upload endpoint"""
        # Create a simple test image file in memory
        import io
        from PIL import Image
        
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        img_buffer.seek(0)
        
        # Prepare multipart form data
        files = {'file': ('test_image.jpg', img_buffer, 'image/jpeg')}
        
        url = f"{self.api_url}/images/upload"
        print(f"\n🔍 Testing Image Upload...")
        print(f"   URL: {url}")
        
        self.tests_run += 1
        
        try:
            response = requests.post(url, files=files, timeout=30)
            success = response.status_code == 200
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                response_data = response.json()
                print(f"   Response: {response_data}")
                
                # Test accessing the uploaded image
                if response_data.get('image_url'):
                    image_url = f"{self.base_url}{response_data['image_url']}"
                    img_response = requests.get(image_url, timeout=10)
                    if img_response.status_code == 200:
                        print(f"   ✅ Uploaded image accessible at: {image_url}")
                    else:
                        print(f"   ❌ Uploaded image not accessible: {img_response.status_code}")
                        
            else:
                print(f"❌ Failed - Expected 200, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text[:200]}")
            
            return success
            
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False

    def test_pdf_export(self):
        """Test PDF export functionality"""
        # Use the test deck ID from review request or created deck
        test_deck_id = "ab6989bc-7ae5-4582-82cb-a422bddba988"
        if self.created_deck_id:
            test_deck_id = self.created_deck_id
            
        url = f"{self.api_url}/export/pdf/{test_deck_id}"
        print(f"\n🔍 Testing PDF Export...")
        print(f"   URL: {url}")
        print(f"   Deck ID: {test_deck_id}")
        
        self.tests_run += 1
        
        try:
            response = requests.post(url, timeout=60)  # Longer timeout for PDF generation
            success = response.status_code == 200
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                
                # Check if response is PDF
                content_type = response.headers.get('content-type', '')
                if 'application/pdf' in content_type:
                    print(f"   ✅ Response is PDF format")
                    print(f"   PDF size: {len(response.content)} bytes")
                else:
                    print(f"   ⚠️  Content type: {content_type}")
                    
                # Check content disposition header
                content_disposition = response.headers.get('content-disposition', '')
                if 'attachment' in content_disposition:
                    print(f"   ✅ PDF download header present")
                else:
                    print(f"   ⚠️  Content disposition: {content_disposition}")
                    
            else:
                print(f"❌ Failed - Expected 200, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text[:200]}")
            
            return success
            
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False

    def test_enhanced_slide_model(self):
        """Test enhanced slide model with background_image and images fields"""
        if not self.created_deck_id:
            print("❌ Skipping - No deck ID available")
            return False
            
        # First get the deck to find a slide ID
        try:
            deck_response = requests.get(f"{self.api_url}/decks/{self.created_deck_id}")
            deck_data = deck_response.json()
            if deck_data.get('slides'):
                slide_id = deck_data['slides'][0]['id']
                
                # Test updating slide with image fields
                slide_update = {
                    "title": "Enhanced Slide with Images",
                    "content": "This slide has background and additional images",
                    "background_image": "https://images.unsplash.com/photo-1542744173-8e7e53415bb0",
                    "images": [
                        "https://images.unsplash.com/photo-1573167507387-6b4b98cb7c13",
                        "https://images.unsplash.com/photo-1505373877841-8d25f7d46678"
                    ]
                }
                
                success, response = self.run_test(
                    "Update Slide with Images",
                    "PUT",
                    f"decks/{self.created_deck_id}/slides/{slide_id}",
                    200,
                    data=slide_update
                )
                
                if success:
                    # Verify the slide was updated by fetching the deck again
                    verify_response = requests.get(f"{self.api_url}/decks/{self.created_deck_id}")
                    if verify_response.status_code == 200:
                        updated_deck = verify_response.json()
                        updated_slide = next((s for s in updated_deck['slides'] if s['id'] == slide_id), None)
                        if updated_slide:
                            has_bg_image = 'background_image' in updated_slide and updated_slide['background_image']
                            has_images = 'images' in updated_slide and len(updated_slide['images']) > 0
                            print(f"   ✅ Slide has background_image: {has_bg_image}")
                            print(f"   ✅ Slide has images array: {has_images}")
                            if has_images:
                                print(f"   Images count: {len(updated_slide['images'])}")
                        else:
                            print(f"   ❌ Could not find updated slide")
                    
                return success
        except Exception as e:
            print(f"❌ Failed to test enhanced slide model: {str(e)}")
            return False

    def test_gemini_image_generation(self):
        """Test Google Gemini AI Image Generation"""
        test_prompts = [
            {
                "prompt": "Professional business meeting in modern conference room",
                "style": "professional"
            },
            {
                "prompt": "Creative startup office with innovative technology",
                "style": "creative"
            },
            {
                "prompt": "Clean minimal presentation slide background",
                "style": "minimal"
            },
            {
                "prompt": "Modern tech company workspace with sleek design",
                "style": "modern"
            }
        ]
        
        successful_generations = 0
        
        for i, test_data in enumerate(test_prompts):
            print(f"\n🔍 Testing Gemini Image Generation {i+1}/4...")
            print(f"   Prompt: {test_data['prompt']}")
            print(f"   Style: {test_data['style']}")
            
            url = f"{self.api_url}/images/generate"
            self.tests_run += 1
            
            try:
                start_time = datetime.now()
                response = requests.post(url, json=test_data, headers={'Content-Type': 'application/json'}, timeout=60)
                end_time = datetime.now()
                generation_time = (end_time - start_time).total_seconds()
                
                success = response.status_code == 200
                
                if success:
                    self.tests_passed += 1
                    successful_generations += 1
                    print(f"✅ Passed - Status: {response.status_code}")
                    print(f"   Generation time: {generation_time:.2f} seconds")
                    
                    response_data = response.json()
                    
                    if response_data.get('success'):
                        print(f"   ✅ Success flag: {response_data['success']}")
                    
                    if response_data.get('image_url'):
                        image_url = response_data['image_url']
                        print(f"   ✅ Image URL generated: {image_url}")
                        
                        # Test if image is accessible
                        full_image_url = f"{self.base_url}{image_url}"
                        img_response = requests.get(full_image_url, timeout=10)
                        if img_response.status_code == 200:
                            print(f"   ✅ Generated image accessible ({len(img_response.content)} bytes)")
                        else:
                            print(f"   ❌ Generated image not accessible: {img_response.status_code}")
                    else:
                        print(f"   ❌ No image URL in response")
                    
                    if response_data.get('prompt_used'):
                        enhanced_prompt = response_data['prompt_used']
                        if test_data['style'] in enhanced_prompt.lower():
                            print(f"   ✅ Style enhancement applied to prompt")
                        else:
                            print(f"   ⚠️  Style enhancement may not be applied")
                        
                else:
                    print(f"❌ Failed - Expected 200, got {response.status_code}")
                    try:
                        error_data = response.json()
                        print(f"   Error: {error_data}")
                    except:
                        print(f"   Error: {response.text[:200]}")
                        
            except requests.exceptions.Timeout:
                print(f"❌ Failed - Request timeout (60s)")
            except Exception as e:
                print(f"❌ Failed - Error: {str(e)}")
        
        print(f"\n📊 Gemini Image Generation Summary: {successful_generations}/4 successful")
        return successful_generations >= 3  # At least 3/4 should work

    def test_font_system(self):
        """Test Enhanced Font System"""
        # Test topic-based font recommendations
        topics = ["business", "tech", "creative", "startup", "finance"]
        slide_types = ["title", "header", "content", "subtitle"]
        
        successful_font_tests = 0
        total_font_tests = len(topics) + len(slide_types)
        
        # Test topic fonts
        for topic in topics:
            success, response = self.run_test(
                f"Get {topic.title()} Topic Fonts",
                "GET",
                f"fonts/topic/{topic}",
                200
            )
            
            if success:
                successful_font_tests += 1
                if response.get('fonts'):
                    fonts = response['fonts']
                    print(f"   Primary font: {fonts.get('primary', 'Unknown')}")
                    print(f"   Secondary font: {fonts.get('secondary', 'Unknown')}")
                    print(f"   Character: {fonts.get('character', 'Unknown')}")
                    
                    # Check Google Fonts URL
                    if response.get('google_fonts_url'):
                        google_url = response['google_fonts_url']
                        if 'fonts.googleapis.com' in google_url:
                            print(f"   ✅ Google Fonts URL generated")
                        else:
                            print(f"   ❌ Invalid Google Fonts URL")
                    else:
                        print(f"   ❌ No Google Fonts URL")
        
        # Test font sizes
        for slide_type in slide_types:
            success, response = self.run_test(
                f"Get {slide_type.title()} Font Sizes",
                "GET",
                f"fonts/sizes/{slide_type}",
                200
            )
            
            if success:
                successful_font_tests += 1
                if response.get('sizes'):
                    sizes = response['sizes']
                    print(f"   Main size: {sizes.get('main', 'Unknown')}")
                    print(f"   Subtitle size: {sizes.get('subtitle', 'Unknown')}")
                    print(f"   Description size: {sizes.get('description', 'Unknown')}")
        
        print(f"\n📊 Font System Summary: {successful_font_tests}/{total_font_tests} successful")
        return successful_font_tests >= (total_font_tests - 1)  # Allow 1 failure

    def test_enhanced_research(self):
        """Test Citation-Free Enhanced Research"""
        research_data = {
            "query": "Market analysis for AI-powered presentation software targeting enterprise clients",
            "research_type": "market_analysis",
            "industry": "software",
            "max_tokens": 1500
        }
        
        success, response = self.run_test(
            "Enhanced Research with Image Prompts",
            "POST",
            "research/enhanced-content",
            200,
            data=research_data
        )
        
        if success:
            data = response.get('data', {})
            content = data.get('content', '')
            image_prompt = data.get('image_prompt', '')
            citations = data.get('citations', [])
            
            print(f"   Content length: {len(content)} characters")
            print(f"   Image prompt length: {len(image_prompt)} characters")
            print(f"   Citations count: {len(citations)}")
            
            # Check if citations are removed
            citation_patterns = ['[1]', '[2]', '[3]', 'according to sources', 'as reported by']
            has_citations = any(pattern in content.lower() for pattern in citation_patterns)
            
            if not has_citations:
                print(f"   ✅ Citations successfully removed from content")
            else:
                print(f"   ❌ Citations still present in content")
            
            # Check if image prompt is generated
            if image_prompt and len(image_prompt) > 20:
                print(f"   ✅ Contextual image prompt generated")
                print(f"   Image prompt: {image_prompt[:100]}...")
            else:
                print(f"   ❌ No meaningful image prompt generated")
            
            # Check content quality (should still be comprehensive despite citation removal)
            if len(content) > 500:
                print(f"   ✅ Content maintains research depth")
            else:
                print(f"   ⚠️  Content may be too brief")
            
            return not has_citations and len(image_prompt) > 20 and len(content) > 500
        
        return False

    def test_optimized_auto_generation(self):
        """Test Optimized Auto-Generation with TechStart (Simple Company)"""
        auto_generate_data = {
            "company_name": "TechStart",
            "industry": "technology",
            "business_description": "AI-powered productivity tools",
            "target_audience": "investors",
            "funding_stage": "seed",
            "auto_populate_images": True
        }
        
        print(f"\n🔍 Testing Enhanced Auto-Generation...")
        print(f"   Company: {auto_generate_data['company_name']}")
        print(f"   Industry: {auto_generate_data['industry']}")
        print(f"   Target: {auto_generate_data['target_audience']}")
        print(f"   Stage: {auto_generate_data['funding_stage']}")
        
        url = f"{self.api_url}/decks/auto-generate"
        self.tests_run += 1
        
        try:
            start_time = datetime.now()
            response = requests.post(url, json=auto_generate_data, headers={'Content-Type': 'application/json'}, timeout=180)
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            success = response.status_code == 200
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                print(f"   Generation time: {generation_time:.2f} seconds")
                
                response_data = response.json()
                slides = response_data.get('slides', [])
                
                # Enhanced validation criteria
                ai_content_slides = 0
                ai_image_slides = 0
                citation_free_slides = 0
                contextual_slides = 0
                
                for slide in slides:
                    content = slide.get('content', '')
                    background_image = slide.get('background_image')
                    
                    # Check for AI-generated content quality
                    if len(content) > 100 and 'Please add content' not in content:
                        ai_content_slides += 1
                    
                    # Check for AI-generated images (should be from /api/images/uploads/ for Gemini)
                    if background_image and '/api/images/uploads/' in background_image:
                        ai_image_slides += 1
                        print(f"   ✅ AI-generated image: {slide.get('title')}")
                    elif background_image:
                        print(f"   📷 Stock image used: {slide.get('title')}")
                    
                    # Check if content is citation-free
                    citation_patterns = ['[1]', '[2]', '[3]', 'according to sources']
                    has_citations = any(pattern in content.lower() for pattern in citation_patterns)
                    if not has_citations:
                        citation_free_slides += 1
                    
                    # Check if content is contextual to company
                    company_terms = ['InnovateTech AI', 'machine learning', 'AI', 'artificial intelligence']
                    is_contextual = any(term.lower() in content.lower() for term in company_terms)
                    if is_contextual:
                        contextual_slides += 1
                
                print(f"\n   📊 Enhanced Auto-Generation Analysis:")
                print(f"   - AI content quality: {ai_content_slides}/9 slides")
                print(f"   - AI-generated images: {ai_image_slides}/9 slides")
                print(f"   - Citation-free content: {citation_free_slides}/9 slides")
                print(f"   - Contextual content: {contextual_slides}/9 slides")
                
                # Success criteria for enhanced version
                content_quality = ai_content_slides >= 8
                image_quality = ai_image_slides >= 6  # At least 6 AI images
                citation_removal = citation_free_slides >= 8
                contextual_quality = contextual_slides >= 7
                
                if content_quality and image_quality and citation_removal and contextual_quality:
                    print(f"   🎉 Enhanced auto-generation fully successful!")
                    return True
                else:
                    print(f"   ⚠️  Enhanced auto-generation needs improvement:")
                    if not content_quality:
                        print(f"     - Content quality: {ai_content_slides}/9")
                    if not image_quality:
                        print(f"     - AI image generation: {ai_image_slides}/9")
                    if not citation_removal:
                        print(f"     - Citation removal: {citation_free_slides}/9")
                    if not contextual_quality:
                        print(f"     - Contextual content: {contextual_slides}/9")
                    return False
                    
            else:
                print(f"❌ Failed - Expected 200, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text[:500]}")
                return False
                
        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout (180s)")
            return False
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False

    def test_enhanced_health_check(self):
        """Test Enhanced Health Check with new services"""
        success, response = self.run_test(
            "Enhanced Health Check",
            "GET",
            "health",
            200
        )
        
        if success:
            services = response.get('services', {})
            print(f"   Services status:")
            
            # Check each service
            perplexity_status = services.get('perplexity_api', 'unknown')
            gemini_status = services.get('gemini_api', 'unknown')
            font_status = services.get('font_system', 'unknown')
            research_status = services.get('enhanced_research', 'unknown')
            
            print(f"   - Perplexity API: {perplexity_status}")
            print(f"   - Gemini API: {gemini_status}")
            print(f"   - Font System: {font_status}")
            print(f"   - Enhanced Research: {research_status}")
            
            # All services should be connected/active
            all_services_ok = (
                perplexity_status == 'connected' and
                gemini_status == 'connected' and
                font_status == 'active' and
                research_status == 'active'
            )
            
            if all_services_ok:
                print(f"   ✅ All enhanced services are operational")
            else:
                print(f"   ⚠️  Some services may need attention")
            
            return all_services_ok
        
        return False

    def test_auto_generate_deck(self):
        """Test auto-generation functionality with realistic data"""
        auto_generate_data = {
            "company_name": "EcoTech Solutions",
            "industry": "CleanTech",
            "business_description": "Revolutionary solar energy storage system with AI-powered optimization",
            "target_audience": "investors",
            "funding_stage": "series_a",
            "auto_populate_images": True
        }
        
        print(f"\n🔍 Testing Auto-Generate Deck...")
        print(f"   Company: {auto_generate_data['company_name']}")
        print(f"   Industry: {auto_generate_data['industry']}")
        print(f"   Target: {auto_generate_data['target_audience']}")
        print(f"   Stage: {auto_generate_data['funding_stage']}")
        
        url = f"{self.api_url}/decks/auto-generate"
        self.tests_run += 1
        
        try:
            start_time = datetime.now()
            response = requests.post(url, json=auto_generate_data, headers={'Content-Type': 'application/json'}, timeout=120)
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            success = response.status_code == 200
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                print(f"   Generation time: {generation_time:.2f} seconds")
                
                response_data = response.json()
                
                # Verify deck structure
                if 'id' in response_data:
                    print(f"   ✅ Deck created with ID: {response_data['id']}")
                    self.created_deck_id = response_data['id']  # Store for potential future tests
                else:
                    print(f"   ❌ No deck ID in response")
                
                # Check title and description
                title = response_data.get('title', '')
                description = response_data.get('description', '')
                print(f"   Title: {title}")
                print(f"   Description: {description}")
                
                if "EcoTech Solutions" in title:
                    print(f"   ✅ Title contains company name")
                else:
                    print(f"   ❌ Title missing company name")
                
                # Verify slides
                slides = response_data.get('slides', [])
                print(f"   ✅ Generated {len(slides)} slides")
                
                if len(slides) != 9:
                    print(f"   ❌ Expected 9 slides, got {len(slides)}")
                    return False
                
                # Check each slide for AI content and images
                slides_with_content = 0
                slides_with_images = 0
                placeholder_slides = 0
                
                expected_slide_titles = [
                    "Problem Statement", "Solution", "Market Opportunity", 
                    "Business Model", "Traction & Metrics", "Competitive Analysis",
                    "Team", "Financial Projections", "Funding Ask"
                ]
                
                for i, slide in enumerate(slides):
                    slide_title = slide.get('title', '')
                    slide_content = slide.get('content', '')
                    background_image = slide.get('background_image')
                    slide_order = slide.get('order', -1)
                    
                    print(f"   Slide {i+1}: {slide_title} (Order: {slide_order})")
                    
                    # Check if slide has meaningful content (not placeholder)
                    if slide_content and len(slide_content) > 50 and "[AI Generation Error]" not in slide_content:
                        slides_with_content += 1
                        print(f"     ✅ Has AI-generated content ({len(slide_content)} chars)")
                        
                        # Check if content mentions the company
                        if "EcoTech Solutions" in slide_content or "solar" in slide_content.lower() or "cleantech" in slide_content.lower():
                            print(f"     ✅ Content is contextual to company")
                        else:
                            print(f"     ⚠️  Content may not be contextual")
                    else:
                        placeholder_slides += 1
                        if "[AI Generation Error]" in slide_content:
                            print(f"     ❌ AI Generation Error in content")
                        else:
                            print(f"     ❌ Content too short or missing ({len(slide_content)} chars)")
                    
                    # Check background image
                    if background_image:
                        slides_with_images += 1
                        print(f"     ✅ Has background image: {background_image[:50]}...")
                    else:
                        print(f"     ❌ No background image")
                    
                    # Verify slide order
                    if slide_order == i:
                        print(f"     ✅ Correct slide order")
                    else:
                        print(f"     ❌ Incorrect slide order: expected {i}, got {slide_order}")
                
                # Summary of content quality
                print(f"\n   📊 Content Quality Summary:")
                print(f"   - Slides with AI content: {slides_with_content}/9")
                print(f"   - Slides with images: {slides_with_images}/9")
                print(f"   - Placeholder slides: {placeholder_slides}/9")
                
                # Performance check
                if generation_time > 60:
                    print(f"   ⚠️  Generation took longer than expected: {generation_time:.2f}s")
                else:
                    print(f"   ✅ Generation completed in reasonable time: {generation_time:.2f}s")
                
                # Overall success criteria
                content_success = slides_with_content >= 7  # At least 7/9 slides should have good content
                image_success = slides_with_images >= 7     # At least 7/9 slides should have images
                performance_success = generation_time < 120  # Should complete within 2 minutes
                
                if content_success and image_success and performance_success:
                    print(f"   🎉 Auto-generation fully successful!")
                    return True
                else:
                    print(f"   ⚠️  Auto-generation partially successful:")
                    if not content_success:
                        print(f"     - Content quality needs improvement")
                    if not image_success:
                        print(f"     - Image assignment needs improvement")
                    if not performance_success:
                        print(f"     - Performance needs improvement")
                    return False
                    
            else:
                print(f"❌ Failed - Expected 200, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text[:500]}")
                return False
                
        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout (120s)")
            return False
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False

def main():
    print("🚀 Starting DeckCraft Pro API Testing...")
    print("=" * 60)
    
    tester = DeckCraftAPITester()
    
    # Run all tests - prioritizing new enhanced features
    tests = [
        tester.test_enhanced_health_check,
        tester.test_gemini_image_generation,
        tester.test_font_system,
        tester.test_enhanced_research,
        tester.test_enhanced_auto_generation,
        tester.test_get_templates,
        tester.test_create_deck,
        tester.test_get_decks,
        tester.test_get_deck_by_id,
        tester.test_update_slide,
        tester.test_market_research,
        tester.test_competitive_analysis,
        tester.test_content_generation,
        tester.test_get_stock_images,
        tester.test_get_stock_images_by_category,
        tester.test_image_upload,
        tester.test_pdf_export,
        tester.test_enhanced_slide_model,
        tester.test_auto_generate_deck
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