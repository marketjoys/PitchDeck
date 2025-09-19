#!/usr/bin/env python3
import requests
import sys
import json
from datetime import datetime

class OptimizedAutoGenTester:
    def __init__(self, base_url="https://deck-sync-upgrade.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0

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
                response = requests.post(url, json=data, headers=headers, timeout=300)  # Extended timeout

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    return success, response_data
                except:
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text[:200]}")

            return success, response.json() if response.content else {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_individual_components(self):
        """Test individual components work in isolation"""
        print(f"\n🔍 Testing Individual Components in Isolation...")
        
        # Test 1: Enhanced Research Component
        print(f"\n   1️⃣ Testing Enhanced Research Component...")
        research_data = {
            "query": "Market analysis for TechStart AI-powered productivity tools targeting seed investors",
            "research_type": "market_analysis",
            "industry": "technology",
            "max_tokens": 800
        }
        
        research_success, research_response = self.run_test(
            "Enhanced Research Component",
            "POST",
            "research/enhanced-content",
            200,
            data=research_data
        )
        
        if research_success:
            content = research_response.get('data', {}).get('content', '')
            image_prompt = research_response.get('data', {}).get('image_prompt', '')
            print(f"     ✅ Research content: {len(content)} chars")
            print(f"     ✅ Image prompt: {len(image_prompt)} chars")
        
        # Test 2: AI Image Generation Component
        print(f"\n   2️⃣ Testing AI Image Generation Component...")
        image_data = {
            "prompt": "Professional technology startup office with modern AI productivity tools",
            "style": "professional"
        }
        
        image_success, image_response = self.run_test(
            "AI Image Generation Component",
            "POST",
            "images/generate",
            200,
            data=image_data
        )
        
        if image_success:
            image_url = image_response.get('image_url', '')
            print(f"     ✅ AI image generated: {image_url}")
        
        # Test 3: Stock Images Fallback
        print(f"\n   3️⃣ Testing Stock Images Fallback...")
        stock_success, stock_response = self.run_test(
            "Stock Images Fallback",
            "GET",
            "images/stock?category=business",
            200
        )
        
        if stock_success and isinstance(stock_response, list):
            print(f"     ✅ Stock images available: {len(stock_response)} images")
        
        # Summary
        components_working = sum([research_success, image_success, stock_success])
        print(f"\n   📊 Individual Components Summary: {components_working}/3 working")
        
        return components_working >= 2

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
        
        print(f"\n🔍 Testing Optimized Auto-Generation...")
        print(f"   Company: {auto_generate_data['company_name']}")
        print(f"   Industry: {auto_generate_data['industry']}")
        print(f"   Target: {auto_generate_data['target_audience']}")
        print(f"   Stage: {auto_generate_data['funding_stage']}")
        print(f"   Focus: Testing optimized performance with simple company data")
        
        url = f"{self.api_url}/decks/auto-generate"
        self.tests_run += 1
        
        try:
            start_time = datetime.now()
            response = requests.post(url, json=auto_generate_data, headers={'Content-Type': 'application/json'}, timeout=300)
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            success = response.status_code == 200
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                print(f"   Generation time: {generation_time:.2f} seconds")
                
                response_data = response.json()
                slides = response_data.get('slides', [])
                
                # Optimized validation criteria
                ai_content_slides = 0
                ai_image_slides = 0
                stock_image_slides = 0
                citation_free_slides = 0
                contextual_slides = 0
                proper_ordering = 0
                
                for slide in slides:
                    content = slide.get('content', '')
                    background_image = slide.get('background_image')
                    slide_order = slide.get('order', -1)
                    
                    # Check for AI-generated content quality (citation-free and investor-ready)
                    if len(content) > 100 and 'Please add content' not in content:
                        ai_content_slides += 1
                    
                    # Check for AI-generated images vs stock fallback
                    if background_image:
                        if '/api/images/uploads/' in background_image:
                            ai_image_slides += 1
                            print(f"   🎨 AI-generated image: {slide.get('title')}")
                        elif 'unsplash.com' in background_image or 'images.unsplash.com' in background_image:
                            stock_image_slides += 1
                            print(f"   📷 Stock image fallback: {slide.get('title')}")
                    
                    # Check if content is citation-free
                    citation_patterns = ['[1]', '[2]', '[3]', 'according to sources', 'as reported by']
                    has_citations = any(pattern in content.lower() for pattern in citation_patterns)
                    if not has_citations:
                        citation_free_slides += 1
                    
                    # Check if content is contextual to TechStart
                    company_terms = ['TechStart', 'AI-powered', 'productivity tools', 'technology']
                    is_contextual = any(term.lower() in content.lower() for term in company_terms)
                    if is_contextual:
                        contextual_slides += 1
                    
                    # Check proper slide ordering (0-8)
                    if 0 <= slide_order <= 8:
                        proper_ordering += 1
                
                print(f"\n   📊 Optimized Auto-Generation Analysis:")
                print(f"   - Total slides generated: {len(slides)}/9")
                print(f"   - AI content quality: {ai_content_slides}/9 slides")
                print(f"   - AI-generated images: {ai_image_slides}/9 slides")
                print(f"   - Stock image fallbacks: {stock_image_slides}/9 slides")
                print(f"   - Citation-free content: {citation_free_slides}/9 slides")
                print(f"   - Contextual content: {contextual_slides}/9 slides")
                print(f"   - Proper slide ordering: {proper_ordering}/9 slides")
                print(f"   - Generation time: {generation_time:.2f} seconds")
                
                # Performance optimization checks
                performance_optimized = generation_time < 180  # Should complete within 3 minutes
                fallback_working = (ai_image_slides + stock_image_slides) >= 8  # Images should be present (AI or fallback)
                content_quality = ai_content_slides >= 8  # Most slides should have quality content
                citation_removal = citation_free_slides >= 8  # Citations should be removed
                contextual_quality = contextual_slides >= 7  # Content should be contextual
                proper_structure = proper_ordering == 9 and len(slides) == 9  # All 9 slides with proper ordering
                
                print(f"\n   🔍 Optimization Verification:")
                print(f"   - Performance optimized (< 3min): {'✅' if performance_optimized else '❌'} ({generation_time:.2f}s)")
                print(f"   - Fallback mechanism working: {'✅' if fallback_working else '❌'} ({ai_image_slides + stock_image_slides}/9 images)")
                print(f"   - Content quality maintained: {'✅' if content_quality else '❌'} ({ai_content_slides}/9 slides)")
                print(f"   - Citation removal working: {'✅' if citation_removal else '❌'} ({citation_free_slides}/9 slides)")
                print(f"   - Contextual content: {'✅' if contextual_quality else '❌'} ({contextual_slides}/9 slides)")
                print(f"   - Proper slide structure: {'✅' if proper_structure else '❌'} ({len(slides)} slides, order 0-8)")
                
                # Success criteria for optimized version
                if (performance_optimized and fallback_working and content_quality and 
                    citation_removal and contextual_quality and proper_structure):
                    print(f"   🎉 Optimized auto-generation fully successful!")
                    print(f"   ✅ All optimizations working: reduced delays, fallback images, citation removal, error handling")
                    return True
                else:
                    print(f"   ⚠️  Optimized auto-generation needs improvement:")
                    if not performance_optimized:
                        print(f"     - Performance: {generation_time:.2f}s (target: <180s)")
                    if not fallback_working:
                        print(f"     - Image fallback: {ai_image_slides + stock_image_slides}/9")
                    if not content_quality:
                        print(f"     - Content quality: {ai_content_slides}/9")
                    if not citation_removal:
                        print(f"     - Citation removal: {citation_free_slides}/9")
                    if not contextual_quality:
                        print(f"     - Contextual content: {contextual_slides}/9")
                    if not proper_structure:
                        print(f"     - Slide structure: {len(slides)} slides, ordering issues")
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
            print(f"❌ Failed - Request timeout (300s)")
            print(f"   This indicates the optimization may not be working as expected")
            return False
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False

def main():
    print("🚀 Testing Optimized Auto-Generation Functionality...")
    print("=" * 60)
    
    tester = OptimizedAutoGenTester()
    
    # Test individual components first
    components_ok = tester.test_individual_components()
    
    if components_ok:
        print(f"\n✅ Individual components working - proceeding with auto-generation test")
        auto_gen_success = tester.test_optimized_auto_generation()
    else:
        print(f"\n❌ Individual components failing - auto-generation likely to fail")
        auto_gen_success = False
    
    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 Final Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if auto_gen_success:
        print("🎉 Optimized auto-generation is working correctly!")
        return 0
    else:
        print("⚠️  Optimized auto-generation needs attention.")
        return 1

if __name__ == "__main__":
    sys.exit(main())