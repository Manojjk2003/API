from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy import Column, String, Integer, Date, TIMESTAMP
import logging
from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column

# Load environment variables from .env file
load_dotenv()

# Fetch DB credentials from .env
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")

# Database URL
DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

# SQLAlchemy setup
engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Users(Base):
    __tablename__ = "users"
    users_id = Column(String(100), primary_key=True, index=True)
    email = Column(String(255))
    role = Column(String(50))
    created_at = Column(TIMESTAMP)

class Admin(Base):
    __tablename__ = "admin"
    admin_id = Column(String(100), primary_key=True)
    users_id = Column(String(100))
    admin_name = Column(String(255))
    email = Column(String(255))
    ph_no = Column(String(20))
    gender =Column(String(20))
    created_by = Column(String(100))
    created_at = Column(TIMESTAMP)

class Teacher(Base):
    __tablename__ = "teacher"
    teacher_id = Column(String(100), primary_key=True)
    users_id = Column(String(100))
    teacher_name = Column(String(255))
    school_id = Column(String(100))
    classes: Mapped[List[int]] = mapped_column(String)
    number_of_students = Column(Integer)
    gender = Column(String(10))
    email = Column(String(255))
    dob: Mapped[str]
    age = Column(Integer)
    ph_no = Column(String(20))
    created_at = Column(TIMESTAMP)

class Tsc(Base):
    __tablename__ = "tsc"
    tsc_id = Column(String(100), primary_key=True)
    users_id = Column(String(100))
    tsc_name = Column(String(255))
    email = Column(String(255))
    ph_no = Column(String(20))
    gender = Column(String(10))
    created_at = Column(TIMESTAMP)


class UserProfile(BaseModel):
    email: str
    name: str
    ph_no: str
    gender: str


class TeacherProfile(UserProfile):
    teacher_name: str
    school_id: str
    classes: List[int]
    number_of_students: int
    dob: Optional[date] = None
    age: Optional[int] = None


class TscProfile(UserProfile):
    tsc_name: str

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPI setup

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic response model
class UserResponse(BaseModel):
    users_id: str
    email: str
    role: str

    class Config:
        orm_mode = True

# Endpoint to fetch user details by uid
@app.get("/get-user/{users_id}", response_model=UserResponse)
async def get_user(users_id: str, db: Session = Depends(get_db)):
    print("hellow")
    print(users_id)
    try:
        user = db.query(Users).filter(Users.users_id == users_id).first()
        print(type(user))
    except Exception as e:
        print(f"Error querying the database: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    print(user)
    if user:
        print("world")
        return user
    else:
        raise HTTPException(status_code=404, detail="User not found")


@app.get("/profileget/{users_id}")
async def get_user_profile(users_id: str, db: Session = Depends(get_db)):
    logger.info(f"Fetching profile for users_id: {users_id}")

    try:
        # Check if user exists in the Users table
        user = db.query(Users).filter(Users.users_id == users_id).first()
        print("Found user: ", user.role)
        if not user:
            logger.error(f"User with users_id {users_id} not found in the Users table")
            raise HTTPException(status_code=404, detail="User not found")

        logger.info(f"Found user: {user}")

        # Fetch the profile based on the user's role
        if user.role == "teacher":
            profile = db.query(Teacher).filter(Teacher.users_id == users_id).first()
            if not profile:
                logger.error(f"Teacher profile not found for users_id {users_id}")
                raise HTTPException(status_code=404, detail="Teacher profile not found")
            logger.info(f"Found Teacher profile: {profile}")

            # Parse 'classes' from string to list of integers
            if profile.classes:
                classes_list = [int(x.strip()) for x in profile.classes.split(',')]
            else:
                classes_list = []

            # Convert 'dob' to string if it is a date
            dob_str = profile.dob.strftime('%Y-%m-%d') if isinstance(profile.dob, date) else profile.dob

            # Prepare the data for TeacherProfile
            teacher_profile_data = {key: value for key, value in profile.__dict__.items() if not key.startswith('_')}
            teacher_profile_data['classes'] = classes_list
            teacher_profile_data['dob'] = dob_str
            teacher_profile_data['name'] = profile.teacher_name

            return TeacherProfile(**teacher_profile_data)
        elif user.role == "tsc":
            profile = db.query(Tsc).filter(Tsc.users_id == users_id).first()
            if not profile:
                logger.error(f"TSC profile not found for users_id {users_id}")
                raise HTTPException(status_code=404, detail="TSC profile not found")
            logger.info(f"Found TSC profile: {profile}")
            tsc_profile_data = {key: value for key, value in profile.__dict__.items() if not key.startswith('_')}
            tsc_profile_data['name'] = profile.tsc_name
            return TscProfile(**tsc_profile_data)

        elif user.role == "admin":
            # Fetch data from admin table
            profile = db.query(Admin).filter(Admin.users_id == users_id).first()
            if not profile:
                logger.error(f"Admin profile not found for users_id {users_id}")
                raise HTTPException(status_code=404, detail="Admin profile not found")
            logger.info(f"Found Admin profile: {profile}")
            admin_profile_data = {key: value for key, value in profile.__dict__.items() if not key.startswith('_')}
            admin_profile_data['name'] = profile.admin_name  # Add name as admin_name
            return UserProfile(**admin_profile_data)

        else:
            logger.error(f"Invalid role {user.role} for users_id {users_id}")
            raise HTTPException(status_code=400, detail="Invalid role")

    except HTTPException as http_error:
        logger.error(f"HTTPException occurred: {str(http_error.detail)}")
        raise http_error

    except Exception as e:
        logger.error(f"Error fetching profile for users_id {users_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.put("/profileput/{user_id}")
async def update_user_profile(user_id: str, profile_data: UserProfile, db: Session = Depends(get_db)):
    logger.info(f"Updating profile for user_id: {user_id}")
    try:
        # Check if user exists and get the role
        user = db.query(Users).filter(Users.users_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update the profile based on the role
        if user.role == "tsc":
            tsc = db.query(Tsc).filter(Tsc.users_id == user_id).first()
            if not tsc:
                raise HTTPException(status_code=404, detail="TSC profile not found")
            tsc.email = profile_data.email
            tsc.ph_no = profile_data.ph_no
            tsc.gender = profile_data.gender


            if profile_data.name:
                tsc.tsc_name = profile_data.name


            db.commit()  # Commit the changes
            return {"message": "TSC profile updated"}
        elif user.role == "teacher":
            teacher = db.query(Teacher).filter(Teacher.users_id == user_id).first()
            if not teacher:
                raise HTTPException(status_code=404, detail="Teacher profile not found")
            teacher.email = profile_data.email
            teacher.ph_no = profile_data.ph_no
            teacher.gender = profile_data.gender


            if profile_data.name:
                teacher.teacher_name = profile_data.name

            db.commit()
            return {"message": "Teacher profile updated"}
        elif user.role == "admin":
            admin = db.query(Admin).filter(Admin.users_id == user_id).first()
            if not admin:
                raise HTTPException(status_code=404, detail="Admin profile not found")
            admin.email = profile_data.email
            admin.ph_no = profile_data.ph_no
            admin.admin_name = profile_data.name
            admin.gender = profile_data.gender
            db.commit()
            return {"message": "Admin profile updated"}
        else:
            raise HTTPException(status_code=400, detail="Invalid role")
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")