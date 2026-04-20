from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker, relationship
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
from jose import jwt
from jose.exceptions import JWTError
import os
import secrets
import json
from enum import Enum as PyEnum
from contextlib import asynccontextmanager

# ================================================================
# CONFIGURATION
# ================================================================

# For Vercel, use PostgreSQL or MySQL (I'll use SQLite for simplicity,
# but for production use a cloud database like Supabase, Neon, or Aiven)

# Option 1: Use SQLite (works but data resets on redeploy)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sports.db")

# Option 2: For production, use a cloud database like Supabase (PostgreSQL)
# DATABASE_URL = os.getenv("DATABASE_URL")

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "lebanon-sports-hub-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# Admin
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "tamernasr1717@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "TAML76")

# Database setup
if "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True
    )
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# ================================================================
# ENUMS
# ================================================================

class RegistrationStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class UserRole(str, PyEnum):
    USER = "user"
    ADMIN = "admin"

class PriceType(str, PyEnum):
    FREE = "free"
    BUDGET = "budget"
    MODERATE = "moderate"
    PREMIUM = "premium"

# ================================================================
# DATABASE MODELS
# ================================================================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=True)
    role = Column(String(50), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    location = Column(String(100), nullable=False)
    date = Column(String(50), nullable=False)
    time = Column(String(50), nullable=False)
    image = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    capacity = Column(Integer, nullable=False)
    venue = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    price = Column(Float, default=0)
    price_type = Column(String(50), nullable=False)
    price_display = Column(String(50), nullable=True)
    registered_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Registration(Base):
    __tablename__ = "registrations"
    id = Column(Integer, primary_key=True, index=True)
    registration_id = Column(String(50), unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_id = Column(Integer, ForeignKey("events.id"))
    status = Column(String(50), default="pending")
    registration_date = Column(DateTime, default=datetime.utcnow)
    approved_date = Column(DateTime, nullable=True)
    rejected_date = Column(DateTime, nullable=True)
    user_name = Column(String(255), nullable=True)
    user_email = Column(String(255), nullable=True)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class OTPCode(Base):
    __tablename__ = "otp_codes"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), index=True, nullable=False)
    code = Column(String(6), nullable=False)
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# ================================================================
# PYDANTIC SCHEMAS
# ================================================================

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class EventResponse(BaseModel):
    id: int
    title: str
    category: str
    location: str
    date: str
    time: str
    description: Optional[str]
    capacity: int
    venue: str
    price: float
    registered_count: int
    latitude: float
    longitude: float
    
    class Config:
        from_attributes = True

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str

class OTPVerifyRequest(BaseModel):
    email: EmailStr
    code: str

# ================================================================
# HELPER FUNCTIONS
# ================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def generate_otp() -> str:
    return f"{secrets.randbelow(900000) + 100000}"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ================================================================
# FASTAPI APPLICATION
# ================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 50)
    print("Lebanon Sports Hub API Starting on Vercel...")
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create admin user if not exists
    db = SessionLocal()
    admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    if not admin:
        admin = User(
            email=ADMIN_EMAIL,
            name="System Administrator",
            hashed_password=get_password_hash(ADMIN_PASSWORD),
            role="admin"
        )
        db.add(admin)
        db.commit()
        print(f"Admin user created: {ADMIN_EMAIL}")
    
    # Create sample events if none exist
    if db.query(Event).count() == 0:
        sample_events = [
            Event(title="Beirut International Marathon", category="Running", location="Beirut", date="Nov 19, 2026", time="7:00 AM", capacity=10000, venue="Martyr's Square", latitude=33.8938, longitude=35.5018, price=50, price_type="premium", price_display="$50"),
            Event(title="Beirut Basketball Tournament", category="Basketball", location="Beirut", date="Dec 5, 2026", time="2:00 PM", capacity=64, venue="Zaitunay Bay", latitude=33.8959, longitude=35.4785, price=20, price_type="budget", price_display="$20"),
            Event(title="Tripoli Football Championship", category="Football", location="Tripoli", date="Dec 10, 2026", time="4:00 PM", capacity=1000, venue="Tripoli Stadium", latitude=34.4367, longitude=35.8497, price=15, price_type="budget", price_display="$15"),
            Event(title="Byblos Coastal Run", category="Running", location="Byblos", date="Nov 25, 2026", time="6:30 AM", capacity=500, venue="Byblos Harbor", latitude=34.1191, longitude=35.6497, price=25, price_type="moderate", price_display="$25"),
            Event(title="Sidon Beach Volleyball", category="Volleyball", location="Sidon", date="Dec 2, 2026", time="9:00 AM", capacity=32, venue="Sidon Beach", latitude=33.5631, longitude=35.3689, price=50, price_type="moderate", price_display="$50"),
            Event(title="Community Football", category="Football", location="Beirut", date="Every Saturday", time="3:00 PM", capacity=100, venue="Sports City", latitude=33.8760, longitude=35.5200, price=0, price_type="free", price_display="FREE"),
        ]
        for event in sample_events:
            db.add(event)
        db.commit()
        print(f"Created {len(sample_events)} sample events")
    
    db.close()
    print("=" * 50)
    yield
    print("Shutting down...")

app = FastAPI(
    title="Lebanon Sports Hub API",
    description="Backend API for Lebanon Sports Hub",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================================================
# API ENDPOINTS
# ================================================================

@app.get("/")
async def root():
    return {"message": "Lebanon Sports Hub API", "status": "running"}

@app.get("/api/health")
async def health():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {e}"
    
    return {"status": "ok", "database": db_status}

# ================================================================
# AUTH ENDPOINTS
# ================================================================

@app.post("/api/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_data.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = User(
        email=user_data.email.lower(),
        name=user_data.name,
        hashed_password=get_password_hash(user_data.password),
        role="user"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login_data.email.lower()).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": user.id})
    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user)
    )

# ================================================================
# ADMIN AUTH
# ================================================================

otp_storage = {}

@app.post("/api/admin/login")
async def admin_login(request: AdminLoginRequest):
    if request.email != ADMIN_EMAIL or request.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    
    otp = generate_otp()
    otp_storage[request.email] = {"code": otp, "expires": datetime.utcnow() + timedelta(minutes=10)}
    
    print(f"Admin OTP for {request.email}: {otp}")
    
    return {"message": "OTP sent to admin email", "demo_otp": otp}

@app.post("/api/admin/verify", response_model=TokenResponse)
async def admin_verify(request: OTPVerifyRequest, db: Session = Depends(get_db)):
    stored = otp_storage.get(request.email)
    if not stored or stored["code"] != request.code or stored["expires"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    admin = db.query(User).filter(User.email == request.email).first()
    if not admin:
        admin = User(
            email=request.email,
            name="Admin",
            hashed_password=get_password_hash(ADMIN_PASSWORD),
            role="admin"
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
    
    access_token = create_access_token(data={"sub": admin.id})
    return TokenResponse(access_token=access_token, user=UserResponse.model_validate(admin))

# ================================================================
# EVENT ENDPOINTS
# ================================================================

@app.get("/api/events", response_model=List[EventResponse])
async def get_events(
    location: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Event).filter(Event.is_active == True)
    if location:
        query = query.filter(Event.location.ilike(f"%{location}%"))
    if category:
        query = query.filter(Event.category.ilike(f"%{category}%"))
    return query.all()

@app.get("/api/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

# ================================================================
# REGISTRATION ENDPOINTS
# ================================================================

@app.post("/api/registrations")
async def register_for_event(
    event_id: int = Query(...),
    user_name: str = Query(...),
    user_email: str = Query(...),
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    if event.registered_count >= event.capacity:
        raise HTTPException(status_code=400, detail="Event is full")
    
    existing = db.query(Registration).filter(
        Registration.event_id == event_id,
        Registration.user_email == user_email,
        Registration.status.in_(["pending", "approved"])
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Already registered")
    
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        user = User(email=user_email, name=user_name, role="user")
        db.add(user)
        db.commit()
        db.refresh(user)
    
    registration_id = f"REG{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{secrets.randbelow(1000):03d}"
    
    new_registration = Registration(
        registration_id=registration_id,
        user_id=user.id,
        event_id=event_id,
        status="pending",
        user_name=user_name,
        user_email=user_email
    )
    db.add(new_registration)
    db.commit()
    
    return {
        "message": "Registration submitted successfully",
        "registration_id": registration_id,
        "status": "pending"
    }

@app.get("/api/registrations/user")
async def get_user_registrations(email: str, db: Session = Depends(get_db)):
    registrations = db.query(Registration).filter(
        Registration.user_email == email
    ).all()
    
    result = []
    for reg in registrations:
        event = db.query(Event).filter(Event.id == reg.event_id).first()
        result.append({
            "registration_id": reg.registration_id,
            "event_title": event.title if event else "Unknown",
            "status": reg.status,
            "registration_date": reg.registration_date
        })
    return result

# ================================================================
# ADMIN REGISTRATION ENDPOINTS
# ================================================================

@app.get("/api/admin/registrations/pending")
async def get_pending_registrations(db: Session = Depends(get_db)):
    registrations = db.query(Registration).filter(
        Registration.status == "pending"
    ).order_by(Registration.registration_date.asc()).all()
    
    result = []
    for reg in registrations:
        event = db.query(Event).filter(Event.id == reg.event_id).first()
        result.append({
            "id": reg.id,
            "registration_id": reg.registration_id,
            "user_name": reg.user_name,
            "user_email": reg.user_email,
            "event_title": event.title if event else "Unknown",
            "event_location": event.location if event else "Unknown",
            "event_date": event.date if event else "Unknown",
            "event_price": event.price if event else 0,
            "status": reg.status,
            "registration_date": reg.registration_date
        })
    return result

@app.get("/api/admin/registrations/all")
async def get_all_registrations(db: Session = Depends(get_db)):
    registrations = db.query(Registration).order_by(
        Registration.registration_date.desc()
    ).all()
    
    result = []
    for reg in registrations:
        event = db.query(Event).filter(Event.id == reg.event_id).first()
        result.append({
            "id": reg.id,
            "registration_id": reg.registration_id,
            "user_name": reg.user_name,
            "user_email": reg.user_email,
            "event_title": event.title if event else "Unknown",
            "event_location": event.location if event else "Unknown",
            "event_date": event.date if event else "Unknown",
            "event_price": event.price if event else 0,
            "status": reg.status,
            "registration_date": reg.registration_date,
            "approved_date": reg.approved_date,
            "rejected_date": reg.rejected_date
        })
    return result

@app.put("/api/admin/registrations/{registration_id}/status")
async def update_registration_status(
    registration_id: int,
    status: str = Query(...),
    db: Session = Depends(get_db)
):
    registration = db.query(Registration).filter(Registration.id == registration_id).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    
    registration.status = status
    if status == "approved":
        registration.approved_date = datetime.utcnow()
        event = db.query(Event).filter(Event.id == registration.event_id).first()
        if event:
            event.registered_count += 1
    elif status == "rejected":
        registration.rejected_date = datetime.utcnow()
    
    # Create notification for user
    event = db.query(Event).filter(Event.id == registration.event_id).first()
    notification = Notification(
        user_id=registration.user_id,
        event_id=registration.event_id,
        title=f"Registration {status}",
        message=f'Your registration for "{event.title if event else "event"}" has been {status}.',
        is_read=False
    )
    db.add(notification)
    
    db.commit()
    
    return {"message": f"Registration {status} successfully"}

@app.get("/api/admin/dashboard/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    total_users = db.query(User).filter(User.role == "user").count()
    total_events = db.query(Event).filter(Event.is_active == True).count()
    pending = db.query(Registration).filter(Registration.status == "pending").count()
    approved = db.query(Registration).filter(Registration.status == "approved").count()
    rejected = db.query(Registration).filter(Registration.status == "rejected").count()
    
    return {
        "total_users": total_users,
        "total_events": total_events,
        "total_registrations": pending + approved + rejected,
        "pending_registrations": pending,
        "approved_registrations": approved,
        "rejected_registrations": rejected
    }

# For Vercel serverless
handler = app