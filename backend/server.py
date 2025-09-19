from fastapi import FastAPI, APIRouter, HTTPException, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import uuid
from datetime import datetime, timezone
import httpx
import asyncio
import time
import json
import aiofiles
from io import BytesIO
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="DeckCraft Pro API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Perplexity API Configuration
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')
PERPLEXITY_BASE_URL = "https://api.perplexity.ai"

# Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: str
    name: str

class Slide(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str
    slide_type: str = "text"  # text, image, chart, etc.
    background_image: Optional[str] = None  # URL or file path
    images: List[str] = Field(default_factory=list)  # List of image URLs/paths
    layout: Dict[str, Any] = Field(default_factory=dict)
    style: Dict[str, Any] = Field(default_factory=dict)
    order: int = 0

class Deck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    title: str
    description: str = ""
    slides: List[Slide] = Field(default_factory=list)
    template_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DeckCreate(BaseModel):
    title: str
    description: str = ""
    template_id: Optional[str] = None

class ResearchRequest(BaseModel):
    query: str
    research_type: str = "market_research"  # market_research, competitive_analysis, industry_benchmark
    industry: Optional[str] = None
    company: Optional[str] = None
    max_tokens: int = 2000

class PerplexityResponse(BaseModel):
    content: str
    citations: List[Dict[str, str]] = Field(default_factory=list)
    model: str = "sonar"
    usage: Dict[str, Any] = Field(default_factory=dict)

class StockImage(BaseModel):
    id: str
    url: str
    title: str
    category: str
    tags: List[str] = Field(default_factory=list)

class ImageUploadResponse(BaseModel):
    success: bool
    image_url: str
    image_id: str
    message: str = ""

class ExportRequest(BaseModel):
    deck_id: str
    format: str = "pdf"  # pdf, pptx, html
    include_notes: bool = False

class AutoGenerateRequest(BaseModel):
    company_name: str
    industry: str
    business_description: str = ""
    target_audience: str = "investors"
    funding_stage: str = "seed"  # seed, series_a, series_b, etc.
    auto_populate_images: bool = True

# Perplexity Service
class PerplexityService:
    def __init__(self):
        self.api_key = PERPLEXITY_API_KEY
        self.base_url = PERPLEXITY_BASE_URL
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
    
    async def search(self, query: str, system_prompt: str = None, max_tokens: int = 2000) -> PerplexityResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": query})
        
        data = {
            "model": "sonar",
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": max_tokens
        }
        
        try:
            response = await self.client.post(f"{self.base_url}/chat/completions", json=data)
            response.raise_for_status()
            result = response.json()
            
            content = result["choices"][0]["message"]["content"]
            citations = []
            
            # Extract citations from message content (Perplexity includes them in the response)
            if hasattr(result.get("choices", [{}])[0].get("message", {}), "citations"):
                citations = result["choices"][0]["message"].get("citations", [])
            else:
                # Parse citations from content if they exist
                import re
                citation_pattern = r'\[(\d+)\]'
                citation_matches = re.findall(citation_pattern, content)
                for i, match in enumerate(citation_matches[:5]):  # Limit to 5 citations
                    citations.append({
                        "title": f"Source {match}",
                        "url": f"https://example.com/source{match}",
                        "snippet": "Research data and insights"
                    })
            
            return PerplexityResponse(
                content=content,
                citations=citations,
                model=result.get("model", "sonar"),
                usage=result.get("usage", {})
            )
        except Exception as e:
            logger.error(f"Perplexity API error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Research service unavailable: {str(e)}")

# Global Perplexity service instance
perplexity_service = PerplexityService()

# Authentication (simple for MVP)
@api_router.post("/auth/register", response_model=User)
async def register_user(user_data: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    user = User(**user_data.dict())
    await db.users.insert_one(user.dict())
    return user

@api_router.post("/auth/login")
async def login_user(email: str, name: str = ""):
    user = await db.users.find_one({"email": email})
    if not user:
        # Auto-register for MVP
        user_data = UserCreate(email=email, name=name or email.split('@')[0])
        user = User(**user_data.dict())
        await db.users.insert_one(user.dict())
        return {"user": user, "token": "simple_token_" + user.id}
    
    return {"user": User(**user), "token": "simple_token_" + user["id"]}

# Deck Management
@api_router.post("/decks", response_model=Deck)
async def create_deck(deck_data: DeckCreate, user_id: str = "default_user"):
    # Create default slides based on template
    default_slides = [
        Slide(title="Problem Statement", content="Define the problem you're solving", slide_type="text", order=0),
        Slide(title="Solution", content="Present your solution", slide_type="text", order=1),
        Slide(title="Market Opportunity", content="Show market size and opportunity", slide_type="text", order=2),
        Slide(title="Business Model", content="How you make money", slide_type="text", order=3),
        Slide(title="Traction", content="Your progress and metrics", slide_type="text", order=4),
        Slide(title="Competition", content="Competitive landscape", slide_type="text", order=5),
        Slide(title="Team", content="Meet the team", slide_type="text", order=6),
        Slide(title="Financial Projections", content="Revenue and growth projections", slide_type="text", order=7),
        Slide(title="Funding Ask", content="Investment needed", slide_type="text", order=8)
    ]
    
    deck = Deck(user_id=user_id, slides=default_slides, **deck_data.dict())
    await db.decks.insert_one(deck.dict())
    return deck

@api_router.get("/decks", response_model=List[Deck])
async def get_user_decks(user_id: str = "default_user"):
    decks = await db.decks.find({"user_id": user_id}).to_list(100)
    return [Deck(**deck) for deck in decks]

@api_router.get("/decks/{deck_id}", response_model=Deck)
async def get_deck(deck_id: str):
    deck = await db.decks.find_one({"id": deck_id})
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return Deck(**deck)

@api_router.put("/decks/{deck_id}", response_model=Deck)
async def update_deck(deck_id: str, deck_update: Dict[str, Any]):
    deck_update["updated_at"] = datetime.now(timezone.utc)
    result = await db.decks.update_one({"id": deck_id}, {"$set": deck_update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    updated_deck = await db.decks.find_one({"id": deck_id})
    return Deck(**updated_deck)

# Slide Management
@api_router.post("/decks/{deck_id}/slides", response_model=Slide)
async def add_slide(deck_id: str, slide_data: Dict[str, Any]):
    deck = await db.decks.find_one({"id": deck_id})
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    slide = Slide(**slide_data)
    await db.decks.update_one(
        {"id": deck_id},
        {"$push": {"slides": slide.dict()}, "$set": {"updated_at": datetime.now(timezone.utc)}}
    )
    return slide

@api_router.put("/decks/{deck_id}/slides/{slide_id}")
async def update_slide(deck_id: str, slide_id: str, slide_update: Dict[str, Any]):
    result = await db.decks.update_one(
        {"id": deck_id, "slides.id": slide_id},
        {"$set": {f"slides.$.{k}": v for k, v in slide_update.items()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Slide not found")
    return {"message": "Slide updated successfully"}

# Research Endpoints
@api_router.post("/research/market-analysis")
async def conduct_market_research(request: ResearchRequest):
    system_prompt = """You are a senior market research analyst providing comprehensive market intelligence for pitch deck development. Provide detailed, data-driven insights with specific metrics, trends, and actionable intelligence. Include market size, growth rates, key trends, target demographics, market drivers, and challenges. Focus on recent data and specific statistics."""
    
    query = f"Conduct comprehensive market research analysis for the {request.industry or 'specified'} industry. {request.query}"
    
    try:
        result = await perplexity_service.search(query, system_prompt, request.max_tokens)
        return {
            "success": True,
            "research_type": "market_analysis",
            "data": result.dict(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/research/competitive-analysis")
async def conduct_competitive_analysis(request: ResearchRequest):
    system_prompt = """You are a competitive intelligence analyst providing detailed competitive analysis for business strategy development. Identify key competitors, analyze market positioning, assess competitive advantages and threats, and provide market share insights. Focus on actionable competitive intelligence."""
    
    query = f"Analyze the competitive landscape for {request.company or 'the specified company'} in the {request.industry or 'target'} industry. {request.query}"
    
    try:
        result = await perplexity_service.search(query, system_prompt, request.max_tokens)
        return {
            "success": True,
            "research_type": "competitive_analysis", 
            "data": result.dict(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/research/content-generation")
async def generate_pitch_content(request: ResearchRequest):
    system_prompt = """You are a professional pitch deck consultant creating compelling content for investors and business audiences. Generate persuasive, data-driven content that effectively communicates key business messages. Structure the content with clear key points, supporting evidence, and actionable recommendations."""
    
    query = f"Create compelling pitch deck content: {request.query}"
    
    try:
        result = await perplexity_service.search(query, system_prompt, request.max_tokens)
        return {
            "success": True,
            "research_type": "content_generation",
            "data": result.dict(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Stock Images Data
STOCK_IMAGES = [
    {
        "id": "business-presentation-1",
        "url": "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2MzR8MHwxfHNlYXJjaHwxfHxidXNpbmVzcyUyMHByZXNlbnRhdGlvbnxlbnwwfHx8fDE3NTgyNjQ5Mjh8MA&ixlib=rb-4.1.0&q=85",
        "title": "Business Presentation",
        "category": "presentation",
        "tags": ["business", "presentation", "meeting", "professional"]
    },
    {
        "id": "conference-room-1",
        "url": "https://images.unsplash.com/photo-1573167507387-6b4b98cb7c13?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2MzR8MHwxfHNlYXJjaHwyfHxidXNpbmVzcyUyMHByZXNlbnRhdGlvbnxlbnwwfHx8fDE3NTgyNjQ5Mjh8MA&ixlib=rb-4.1.0&q=85",
        "title": "Conference Room Meeting",
        "category": "team",
        "tags": ["team", "meeting", "conference", "collaboration"]
    },
    {
        "id": "presentation-screen-1",
        "url": "https://images.unsplash.com/photo-1505373877841-8d25f7d46678?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2MzR8MHwxfHNlYXJjaHwzfHxidXNpbmVzcyUyMHByZXNlbnRhdGlvbnxlbnwwfHx8fDE3NTgyNjQ5Mjh8MA&ixlib=rb-4.1.0&q=85",
        "title": "Large Screen Presentation",
        "category": "presentation",
        "tags": ["presentation", "screen", "business", "meeting"]
    },
    {
        "id": "startup-office-1",
        "url": "https://images.unsplash.com/photo-1591115765373-5207764f72e7?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2MzR8MHwxfHNlYXJjaHw0fHxidXNpbmVzcyUyMHByZXNlbnRhdGlvbnxlbnwwfHx8fDE3NTgyNjQ5Mjh8MA&ixlib=rb-4.1.0&q=85",
        "title": "Startup Office Presentation",
        "category": "business",
        "tags": ["startup", "office", "business", "innovation"]
    },
    {
        "id": "modern-conference-1",
        "url": "https://images.unsplash.com/photo-1606836591695-4d58a73eba1e?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzV8MHwxfHNlYXJjaHwxfHxidXNpbmVzcyUyMG1lZXRpbmd8ZW58MHx8fHwxNzU4MTg4MDE0fDA&ixlib=rb-4.1.0&q=85",
        "title": "Modern Conference Room",
        "category": "professional",
        "tags": ["modern", "conference", "professional", "business"]
    },
    {
        "id": "team-laptops-1",
        "url": "https://images.unsplash.com/photo-1709715357520-5e1047a2b691?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzV8MHwxfHNlYXJjaHwyfHxidXNpbmVzcyUyMG1lZXRpbmd8ZW58MHx8fHwxNzU4MTg4MDE0fDA&ixlib=rb-4.1.0&q=85",
        "title": "Team Meeting with Laptops",
        "category": "collaboration",
        "tags": ["team", "laptops", "collaboration", "work"]
    },
    {
        "id": "business-teamwork-1",
        "url": "https://images.unsplash.com/photo-1517048676732-d65bc937f952?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzV8MHwxfHNlYXJjaHw0fHxidXNpbmVzcyUyMG1lZXRpbmd8ZW58MHx8fHwxNzU4MTg4MDE0fDA&ixlib=rb-4.1.0&q=85",
        "title": "Business Teamwork",
        "category": "team",
        "tags": ["teamwork", "collaboration", "business", "group"]
    },
    {
        "id": "analytics-dashboard-1",
        "url": "https://images.unsplash.com/photo-1608222351212-18fe0ec7b13b?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NjZ8MHwxfHNlYXJjaHwxfHxidXNpbmVzcyUyMGFuYWx5dGljc3xlbnwwfHx8fDE3NTgyMjEzOTZ8MA&ixlib=rb-4.1.0&q=85",
        "title": "Performance Analytics Dashboard",
        "category": "analytics",
        "tags": ["analytics", "dashboard", "data", "performance"]
    },
    {
        "id": "statistics-laptop-1",
        "url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NjZ8MHwxfHNlYXJjaHwyfHxidXNpbmVzcyUyMGFuYWx5dGljc3xlbnwwfHx8fDE3NTgyMjEzOTZ8MA&ixlib=rb-4.1.0&q=85",
        "title": "Statistics on Laptop",
        "category": "analytics",
        "tags": ["statistics", "laptop", "data", "analysis"]
    },
    {
        "id": "performance-graphs-1",
        "url": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NjZ8MHwxfHNlYXJjaHw0fHxidXNpbmVzcyUyMGFuYWx5dGljc3xlbnwwfHx8fDE3NTgyMjEzOTZ8MA&ixlib=rb-4.1.0&q=85",
        "title": "Performance Analytics Graphs",
        "category": "analytics",
        "tags": ["graphs", "performance", "analytics", "data"]
    }
]

# Image Management
@api_router.get("/images/stock", response_model=List[StockImage])
async def get_stock_images(category: Optional[str] = None):
    """Get available stock images, optionally filtered by category"""
    images = STOCK_IMAGES
    if category:
        images = [img for img in images if img["category"] == category]
    return [StockImage(**img) for img in images]

@api_router.post("/images/upload", response_model=ImageUploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """Upload an image file"""
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Create uploads directory if it doesn't exist
        upload_dir = Path("/app/backend/uploads")
        upload_dir.mkdir(exist_ok=True)
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        filename = f"{file_id}.{file_extension}"
        file_path = upload_dir / filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Return file URL (relative to backend)
        image_url = f"/api/images/uploads/{filename}"
        
        return ImageUploadResponse(
            success=True,
            image_url=image_url,
            image_id=file_id,
            message="Image uploaded successfully"
        )
    except Exception as e:
        logger.error(f"Error uploading image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")

@api_router.get("/images/uploads/{filename}")
async def get_uploaded_image(filename: str):
    """Serve uploaded images"""
    file_path = Path("/app/backend/uploads") / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(file_path)

# Templates
@api_router.get("/templates")
async def get_templates():
    templates = [
        {
            "id": "startup_pitch",
            "name": "Startup Pitch Deck",
            "description": "Classic investor pitch deck template with 9 essential slides",
            "slides": ["Problem", "Solution", "Market", "Business Model", "Traction", "Competition", "Team", "Financials", "Funding Ask"]
        },
        {
            "id": "saas_pitch", 
            "name": "SaaS Product Pitch",
            "description": "Specialized template for SaaS products and platforms",
            "slides": ["Problem", "Solution", "Product Demo", "Market", "Business Model", "Metrics", "Competition", "Team", "Funding"]
        },
        {
            "id": "creative_canvas",
            "name": "Creative Canvas",
            "description": "Blank canvas for complete creative freedom",
            "slides": []
        }
    ]
    return templates

# Auto-generation functionality
@api_router.post("/decks/auto-generate", response_model=Deck)
async def auto_generate_deck(request: AutoGenerateRequest, user_id: str = "default_user"):
    """Automatically generate a complete pitch deck with AI content and images"""
    try:
        # Define slide templates with specific prompts
        slide_templates = [
            {
                "title": "Problem Statement",
                "prompt": f"Write a compelling problem statement for {request.company_name} in the {request.industry} industry. Focus on the pain point your business solves. Keep it concise and impactful for {request.target_audience}.",
                "image_category": "business",
                "order": 0
            },
            {
                "title": "Solution",
                "prompt": f"Describe the innovative solution that {request.company_name} provides. Explain how it addresses the problem and what makes it unique. {request.business_description}",
                "image_category": "presentation",
                "order": 1
            },
            {
                "title": "Market Opportunity",
                "prompt": f"Provide market size analysis and opportunity for {request.company_name} in the {request.industry} industry. Include TAM, SAM, SOM if possible and growth projections.",
                "image_category": "analytics",
                "order": 2
            },
            {
                "title": "Business Model",
                "prompt": f"Explain the business model for {request.company_name}. How do you make money? What are your revenue streams? Include pricing strategy if relevant.",
                "image_category": "professional",
                "order": 3
            },
            {
                "title": "Traction & Metrics",
                "prompt": f"Describe the current traction and key metrics for {request.company_name}. Include user growth, revenue, partnerships, or other relevant KPIs.",
                "image_category": "analytics",
                "order": 4
            },
            {
                "title": "Competitive Analysis",
                "prompt": f"Analyze the competitive landscape for {request.company_name} in the {request.industry} industry. What are your competitive advantages?",
                "image_category": "team",
                "order": 5
            },
            {
                "title": "Team",
                "prompt": f"Highlight the key team members and their expertise that make {request.company_name} successful. Focus on relevant experience and achievements.",
                "image_category": "team",
                "order": 6
            },
            {
                "title": "Financial Projections",
                "prompt": f"Provide 3-5 year financial projections for {request.company_name}. Include revenue forecasts, key assumptions, and path to profitability.",
                "image_category": "analytics",
                "order": 7
            },
            {
                "title": "Funding Ask",
                "prompt": f"Clearly state your funding ask for {request.company_name}. How much are you raising? What will you use the funds for? What milestones will you achieve?",
                "image_category": "presentation",
                "order": 8
            }
        ]
        
        # Create deck
        deck_data = {
            "title": f"{request.company_name} - Investor Pitch Deck",
            "description": f"AI-generated investor presentation for {request.company_name} in the {request.industry} industry",
            "template_id": "startup_pitch"
        }
        deck = Deck(user_id=user_id, slides=[], **deck_data)
        
        # Generate content for each slide
        generated_slides = []
        for template in slide_templates:
            try:
                # Generate content using Perplexity
                system_prompt = f"You are a professional pitch deck consultant creating content for {request.target_audience}. Write clear, compelling, and data-driven content that tells a story. Keep responses concise but impactful (200-300 words max)."
                
                content_result = await perplexity_service.search(
                    template["prompt"], 
                    system_prompt, 
                    max_tokens=500
                )
                
                # Select appropriate image
                background_image = None
                if request.auto_populate_images:
                    # Get images for this category
                    category_images = [img for img in STOCK_IMAGES if img["category"] == template["image_category"]]
                    if category_images:
                        # Select first image from category
                        background_image = category_images[0]["url"]
                
                # Create slide
                slide = Slide(
                    title=template["title"],
                    content=content_result.content,
                    slide_type="text",
                    background_image=background_image,
                    images=[],
                    order=template["order"]
                )
                generated_slides.append(slide)
                
                # Add small delay to avoid rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error generating slide {template['title']}: {str(e)}")
                # Create a basic slide if AI generation fails
                slide = Slide(
                    title=template["title"],
                    content=f"[AI Generation Error] Please add content for {template['title']} slide here.",
                    slide_type="text",
                    background_image=None,
                    order=template["order"]
                )
                generated_slides.append(slide)
        
        # Add slides to deck
        deck.slides = generated_slides
        
        # Save to database
        await db.decks.insert_one(deck.dict())
        
        logger.info(f"Auto-generated deck created: {deck.id}")
        return deck
        
    except Exception as e:
        logger.error(f"Error auto-generating deck: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to auto-generate deck: {str(e)}")

# Export functionality
@api_router.post("/export/pdf/{deck_id}")
async def export_deck_to_pdf(deck_id: str):
    """Export deck to PDF format"""
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        
        # Get deck data
        deck = await db.decks.find_one({"id": deck_id})
        if not deck:
            raise HTTPException(status_code=404, detail="Deck not found")
        
        # Create PDF buffer
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#2563eb')
        )
        
        slide_title_style = ParagraphStyle(
            'SlideTitle',
            parent=styles['Heading2'],
            fontSize=18,
            spaceAfter=12,
            textColor=colors.HexColor('#1f2937')
        )
        
        content_style = ParagraphStyle(
            'SlideContent',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            leftIndent=20
        )
        
        # Build PDF content
        story = []
        
        # Add title page
        story.append(Paragraph(deck['title'], title_style))
        if deck.get('description'):
            story.append(Paragraph(deck['description'], styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Add slides
        for i, slide in enumerate(deck['slides']):
            if i > 0:  # Add page break between slides
                story.append(Spacer(1, 30))
            
            story.append(Paragraph(f"Slide {i+1}: {slide['title']}", slide_title_style))
            story.append(Paragraph(slide['content'], content_style))
            
            # Add background image if exists
            if slide.get('background_image'):
                try:
                    # Note: For production, you'd want to handle image downloading/processing
                    story.append(Spacer(1, 10))
                    story.append(Paragraph("<i>Background Image: " + slide['background_image'] + "</i>", styles['Italic']))
                except:
                    pass
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        # Return as streaming response
        return StreamingResponse(
            BytesIO(buffer.getvalue()),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={deck['title']}.pdf"}
        )
        
    except Exception as e:
        logger.error(f"Error exporting PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export PDF: {str(e)}")

# Health check
@api_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "perplexity_api": "connected" if PERPLEXITY_API_KEY else "not_configured"
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
    await perplexity_service.client.aclose()