# main.py
"""
Lebanon Sports Hub - Backend API with MySQL
Professional FastAPI application with MySQL database integration
"""

from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum, text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker, relationship
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
from jose import jwt
from jose.exceptions import JWTError
import os
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import json
from enum import Enum as PyEnum
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ================================================================
# CONFIGURATION
# ================================================================

class Settings:
    # Database - MySQL
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "taml7677")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "SportsFyp")
    
    DATABASE_URL: str = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "lebanon-sports-hub-secret-key-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    
    # Email (SMTP) - Optional for now
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "noreply@lebanonsportshub.com")
    
    # Admin
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "tamernasr1717@gmail.com")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "TAML76")
    
    # Frontend URL
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://sports-fyp.vercel.app")

settings = Settings()

# ================================================================
# DATABASE SETUP
# ================================================================

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
    echo=False,
    connect_args={"connect_timeout": 60}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ================================================================
# ENUMS
# ================================================================

class RegistrationStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class EventCategory(str, PyEnum):
    RUNNING = "Running"
    FOOTBALL = "Football"
    BASKETBALL = "Basketball"
    YOGA = "Yoga"
    TENNIS = "Tennis"
    WRESTLING = "Wrestling"
    FISHING = "Fishing"
    VOLLEYBALL = "Volleyball"
    KAYAKING = "Kayaking"
    TRIATHLON = "Triathlon"
    ROWING = "Rowing"
    CYCLING = "Cycling"
    EQUESTRIAN = "Equestrian"
    AIR_SPORTS = "Air Sports"
    WATER_SPORTS = "Water Sports"
    WINTER_SPORTS = "Winter Sports"
    HIKING = "Hiking"
    OTHER = "Other"

class PriceType(str, PyEnum):
    FREE = "free"
    BUDGET = "budget"
    MODERATE = "moderate"
    PREMIUM = "premium"

class UserRole(str, PyEnum):
    USER = "user"
    ADMIN = "admin"

# ================================================================
# DATABASE MODELS
# ================================================================

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=True)
    is_google_user = Column(Boolean, default=False)
    role = Column(SQLEnum(UserRole), default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    registrations = relationship("Registration", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    category = Column(SQLEnum(EventCategory), nullable=False)
    location = Column(String(100), nullable=False)
    date = Column(String(50), nullable=False)
    time = Column(String(50), nullable=False)
    image = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    registered_count = Column(Integer, default=0)
    capacity = Column(Integer, nullable=False)
    venue = Column(String(255), nullable=False)
    exact_location = Column(Text, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    price = Column(Float, default=0)
    price_type = Column(SQLEnum(PriceType), nullable=False)
    price_display = Column(String(50), nullable=True)
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    registrations = relationship("Registration", back_populates="event", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="event", cascade="all, delete-orphan")

class Registration(Base):
    __tablename__ = "registrations"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    registration_id = Column(String(50), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    status = Column(SQLEnum(RegistrationStatus), default=RegistrationStatus.PENDING)
    registration_date = Column(DateTime, default=datetime.utcnow)
    approved_date = Column(DateTime, nullable=True)
    rejected_date = Column(DateTime, nullable=True)
    cancelled_date = Column(DateTime, nullable=True)
    admin_notes = Column(Text, nullable=True)
    
    user = relationship("User", back_populates="registrations")
    event = relationship("Event", back_populates="registrations")

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="notifications")

class Favorite(Base):
    __tablename__ = "favorites"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="favorites")
    event = relationship("Event", back_populates="favorites")

class OTPCode(Base):
    __tablename__ = "otp_codes"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), index=True, nullable=False)
    code = Column(String(6), nullable=False)
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(500), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_revoked = Column(Boolean, default=False)
    
    user = relationship("User")

# ================================================================
# PYDANTIC SCHEMAS
# ================================================================

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: UserRole
    is_google_user: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

class EventResponse(BaseModel):
    id: int
    title: str
    category: EventCategory
    location: str
    date: str
    time: str
    image: Optional[str]
    description: Optional[str]
    registered_count: int
    capacity: int
    venue: str
    exact_location: Optional[str]
    latitude: float
    longitude: float
    price: float
    price_type: PriceType
    price_display: Optional[str]
    is_recurring: bool
    recurrence_pattern: Optional[str]
    is_active: bool
    
    class Config:
        from_attributes = True

class RegistrationResponse(BaseModel):
    id: int
    registration_id: str
    user_id: int
    event_id: int
    status: RegistrationStatus
    registration_date: datetime
    approved_date: Optional[datetime]
    rejected_date: Optional[datetime]
    cancelled_date: Optional[datetime]
    admin_notes: Optional[str]
    event: Optional[EventResponse]
    user_name: Optional[str]
    user_email: Optional[str]
    
    class Config:
        from_attributes = True

class RegistrationUpdate(BaseModel):
    status: RegistrationStatus
    admin_notes: Optional[str] = None

class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    notification_type: str
    is_read: bool
    created_at: datetime
    event_id: Optional[int]
    
    class Config:
        from_attributes = True

class OTPSendRequest(BaseModel):
    email: EmailStr

class OTPVerifyRequest(BaseModel):
    email: EmailStr
    code: str

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleAuthRequest(BaseModel):
    name: str
    email: EmailStr
    google_id: Optional[str] = None

# ================================================================
# AUTHENTICATION UTILITIES
# ================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode = data.copy()
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(lambda: SessionLocal())
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_token(token)
    user_id: int = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    return user

async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

# ================================================================
# EMAIL UTILITIES (Simplified for now)
# ================================================================

def generate_otp() -> str:
    return f"{secrets.randbelow(900000) + 100000}"

async def send_otp_and_save(email: str, db: Session) -> str:
    # Invalidate old unused OTPs
    db.query(OTPCode).filter(
        OTPCode.email == email,
        OTPCode.is_used == False,
        OTPCode.expires_at > datetime.utcnow()
    ).update({"is_used": True})
    
    otp_code = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    otp_record = OTPCode(email=email, code=otp_code, expires_at=expires_at)
    db.add(otp_record)
    db.commit()
    
    print(f"OTP for {email}: {otp_code}")  # Print to console for demo
    return otp_code

def verify_otp(email: str, code: str, db: Session) -> bool:
    otp_record = db.query(OTPCode).filter(
        OTPCode.email == email,
        OTPCode.code == code,
        OTPCode.is_used == False,
        OTPCode.expires_at > datetime.utcnow()
    ).first()
    
    if not otp_record:
        return False
    
    otp_record.is_used = True
    db.commit()
    return True

# ================================================================
# FASTAPI APPLICATION
# ================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 50)
    print("Lebanon Sports Hub API Starting...")
    print(f"Database: {settings.MYSQL_DATABASE} at {settings.MYSQL_HOST}")
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create admin user if not exists
    db = SessionLocal()
    admin = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
    if not admin:
        admin = User(
            email=settings.ADMIN_EMAIL,
            name="System Administrator",
            hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin)
        db.commit()
        print(f"Admin user created: {settings.ADMIN_EMAIL}")
    
    # Create sample events if none exist
    if db.query(Event).count() == 0:
        sample_events = [
            Event(title="Beirut International Marathon", category=EventCategory.RUNNING, location="Beirut", date="Nov 19, 2026", time="7:00 AM", capacity=10000, venue="Martyr's Square", latitude=33.8938, longitude=35.5018, price=50, price_type=PriceType.PREMIUM, price_display="$50"),
            Event(title="Beirut Basketball Tournament", category=EventCategory.BASKETBALL, location="Beirut", date="Dec 5, 2026", time="2:00 PM", capacity=64, venue="Zaitunay Bay", latitude=33.8959, longitude=35.4785, price=20, price_type=PriceType.BUDGET, price_display="$20"),
            Event(title="Tripoli Football Championship", category=EventCategory.FOOTBALL, location="Tripoli", date="Dec 10, 2026", time="4:00 PM", capacity=1000, venue="Tripoli Stadium", latitude=34.4367, longitude=35.8497, price=15, price_type=PriceType.BUDGET, price_display="$15"),
            Event(title="Byblos Coastal Run", category=EventCategory.RUNNING, location="Byblos", date="Nov 25, 2026", time="6:30 AM", capacity=500, venue="Byblos Harbor", latitude=34.1191, longitude=35.6497, price=25, price_type=PriceType.MODERATE, price_display="$25"),
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
    description="Professional backend for Lebanon Sports Hub with MySQL",
    version="2.0.0",
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
    return {
        "message": "Welcome to Lebanon Sports Hub API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {e}"
    
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "service": "Lebanon Sports Hub API"
    }

# ================================================================
# AUTH ENDPOINTS
# ================================================================

@app.post("/api/auth/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, db: Session = Depends(lambda: SessionLocal())):
    existing_user = db.query(User).filter(User.email == user_data.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = User(
        email=user_data.email.lower(),
        name=user_data.name,
        hashed_password=get_password_hash(user_data.password),
        role=UserRole.USER,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

@app.post("/api/auth/login", response_model=TokenResponse)
async def login_user(login_data: UserLogin, db: Session = Depends(lambda: SessionLocal())):
    user = db.query(User).filter(User.email == login_data.email.lower()).first()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    
    refresh_token_expiry = datetime.utcnow() + timedelta(days=7)
    db_refresh = RefreshToken(user_id=user.id, token=refresh_token, expires_at=refresh_token_expiry)
    db.add(db_refresh)
    db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user)
    )

# ================================================================
# ADMIN AUTH (with OTP)
# ================================================================

@app.post("/api/admin/login")
async def admin_login(request: AdminLoginRequest, db: Session = Depends(lambda: SessionLocal())):
    if request.email != settings.ADMIN_EMAIL:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    
    admin_user = db.query(User).filter(User.email == request.email, User.role == UserRole.ADMIN).first()
    if not admin_user:
        admin_user = User(
            email=settings.ADMIN_EMAIL,
            name="System Administrator",
            hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
    
    otp_code = await send_otp_and_save(request.email, db)
    
    return {
        "message": "OTP sent to admin email",
        "otp_sent": True,
        "demo_otp": otp_code
    }

@app.post("/api/admin/verify", response_model=TokenResponse)
async def admin_verify_otp(request: OTPVerifyRequest, db: Session = Depends(lambda: SessionLocal())):
    if not verify_otp(request.email.lower(), request.code, db):
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
    
    admin_user = db.query(User).filter(User.email == request.email.lower(), User.role == UserRole.ADMIN).first()
    if not admin_user:
        raise HTTPException(status_code=401, detail="Admin user not found")
    
    access_token = create_access_token(data={"sub": admin_user.id})
    refresh_token = create_refresh_token(data={"sub": admin_user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(admin_user)
    )

# ================================================================
# EVENT ENDPOINTS
# ================================================================

@app.get("/api/events", response_model=List[EventResponse])
async def get_events(
    location: Optional[str] = None,
    category: Optional[EventCategory] = None,
    search: Optional[str] = None,
    db: Session = Depends(lambda: SessionLocal())
):
    query = db.query(Event).filter(Event.is_active == True)
    
    if location:
        query = query.filter(Event.location.ilike(f"%{location}%"))
    if category:
        query = query.filter(Event.category == category)
    if search:
        query = query.filter(
            (Event.title.ilike(f"%{search}%")) |
            (Event.description.ilike(f"%{search}%"))
        )
    
    return query.order_by(Event.date).all()

@app.get("/api/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: int, db: Session = Depends(lambda: SessionLocal())):
    event = db.query(Event).filter(Event.id == event_id, Event.is_active == True).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

# ================================================================
# REGISTRATION ENDPOINTS
# ================================================================

@app.post("/api/registrations")
async def create_registration(
    event_id: int,
    user_name: str,
    user_email: str,
    db: Session = Depends(lambda: SessionLocal())
):
    """Register for an event (no auth required for demo)"""
    event = db.query(Event).filter(Event.id == event_id, Event.is_active == True).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Check if already registered
    existing = db.query(Registration).filter(
        Registration.event_id == event_id,
        Registration.user_email == user_email,
        Registration.status.in_([RegistrationStatus.PENDING, RegistrationStatus.APPROVED])
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Already registered for this event")
    
    if event.registered_count >= event.capacity:
        raise HTTPException(status_code=400, detail="Event is at full capacity")
    
    # Get or create user
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        user = User(
            email=user_email,
            name=user_name,
            role=UserRole.USER,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    registration_id = f"REG{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{secrets.randbelow(1000):03d}"
    
    new_registration = Registration(
        registration_id=registration_id,
        user_id=user.id,
        event_id=event_id,
        status=RegistrationStatus.PENDING
    )
    db.add(new_registration)
    db.commit()
    db.refresh(new_registration)
    
    return {
        "message": "Registration submitted successfully",
        "registration_id": registration_id,
        "status": "pending",
        "event_title": event.title
    }

@app.get("/api/registrations/user")
async def get_user_registrations(email: str, db: Session = Depends(lambda: SessionLocal())):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return []
    
    registrations = db.query(Registration).filter(Registration.user_id == user.id).all()
    result = []
    for reg in registrations:
        event = db.query(Event).filter(Event.id == reg.event_id).first()
        result.append({
            "id": reg.id,
            "registration_id": reg.registration_id,
            "event_title": event.title if event else "Unknown",
            "event_date": event.date if event else "Unknown",
            "status": reg.status,
            "registration_date": reg.registration_date
        })
    
    return result

# ================================================================
# ADMIN REGISTRATION ENDPOINTS
# ================================================================

@app.get("/api/admin/registrations/pending")
async def get_pending_registrations(db: Session = Depends(lambda: SessionLocal())):
    registrations = db.query(Registration).filter(
        Registration.status == RegistrationStatus.PENDING
    ).order_by(Registration.registration_date.asc()).all()
    
    result = []
    for reg in registrations:
        event = db.query(Event).filter(Event.id == reg.event_id).first()
        user = db.query(User).filter(User.id == reg.user_id).first()
        result.append({
            "id": reg.id,
            "registration_id": reg.registration_id,
            "user_name": user.name if user else "Unknown",
            "user_email": user.email if user else "Unknown",
            "event_title": event.title if event else "Unknown",
            "event_location": event.location if event else "Unknown",
            "event_date": event.date if event else "Unknown",
            "event_price": event.price if event else 0,
            "status": reg.status,
            "registration_date": reg.registration_date
        })
    
    return result

@app.get("/api/admin/registrations/all")
async def get_all_registrations(db: Session = Depends(lambda: SessionLocal())):
    registrations = db.query(Registration).order_by(Registration.registration_date.desc()).all()
    
    result = []
    for reg in registrations:
        event = db.query(Event).filter(Event.id == reg.event_id).first()
        user = db.query(User).filter(User.id == reg.user_id).first()
        result.append({
            "id": reg.id,
            "registration_id": reg.registration_id,
            "user_name": user.name if user else "Unknown",
            "user_email": user.email if user else "Unknown",
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
    status: str,
    db: Session = Depends(lambda: SessionLocal())
):
    registration = db.query(Registration).filter(Registration.id == registration_id).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    
    registration.status = RegistrationStatus(status)
    if status == "approved":
        registration.approved_date = datetime.utcnow()
        event = db.query(Event).filter(Event.id == registration.event_id).first()
        if event:
            event.registered_count += 1
    elif status == "rejected":
        registration.rejected_date = datetime.utcnow()
    
    db.commit()
    
    return {"message": f"Registration {status} successfully"}

@app.get("/api/admin/dashboard/stats")
async def get_dashboard_stats(db: Session = Depends(lambda: SessionLocal())):
    total_users = db.query(User).filter(User.role == UserRole.USER).count()
    total_events = db.query(Event).filter(Event.is_active == True).count()
    pending = db.query(Registration).filter(Registration.status == RegistrationStatus.PENDING).count()
    approved = db.query(Registration).filter(Registration.status == RegistrationStatus.APPROVED).count()
    rejected = db.query(Registration).filter(Registration.status == RegistrationStatus.REJECTED).count()
    
    return {
        "total_users": total_users,
        "total_events": total_events,
        "total_registrations": pending + approved + rejected,
        "pending_registrations": pending,
        "approved_registrations": approved,
        "rejected_registrations": rejected
    }

# ================================================================
# RUN THE APPLICATION
# ================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )