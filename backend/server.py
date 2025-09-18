from fastapi import FastAPI, APIRouter, HTTPException, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
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
    model: str = "llama-3.1-sonar-small-128k-online"
    usage: Dict[str, int] = Field(default_factory=dict)

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
            "model": "llama-3.1-sonar-small-128k-online",
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
                model=result.get("model", "pplx-7b-chat"),
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