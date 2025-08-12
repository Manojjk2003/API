import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, Integer, ForeignKey, func, Date, TIMESTAMP, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from pydantic import BaseModel
from typing import List
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from dotenv import load_dotenv
import uuid
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import urlparse
from datetime import datetime
import re
from sqlalchemy.exc import IntegrityError


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

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


        
class ProjectLink(BaseModel):
    project_id: str
    project_link: str   
    uploaded_time: datetime   
    status: str   

# Pydantic model for the response (Dashboard)
class DashboardResponse(BaseModel):
    teacher_id: str
    teacher_name: str
    school_name: str
    bread_crumb: str
    num_teacher_projects: int
    num_student_projects: int
    distinct_grades: List[int]
    total_students: int
    teacher_project_links: List[ProjectLink]
    student_project_links: List[ProjectLink]

# Pydantic model for Teacher Project Upload
class TeacherProjectUpload(BaseModel):
    project_link: str
    
    feedback: Optional[str] = None

# Pydantic model for Session Student Data (Session Data for Student Project)
class SessionStudentData(BaseModel):
    no_of_students: int
    grade: int
    section: str
    feedback: str

# Pydantic model for Student Project Upload
class StudentProjectUpload(BaseModel):
    project_link: str

class StudentProjectBatchUpload(BaseModel):
    session_data: SessionStudentData
    projects: List[StudentProjectUpload]

# FastAPI app
app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

# SQLAlchemy models


class Admin(Base):
    __tablename__ = 'admin'

    admin_id = Column(String(100), primary_key=True)  
    users_id = Column(String(100), ForeignKey('users.users_id'), nullable=True)  
    admin_name = Column(String(255), nullable=True)  
    email = Column(String(255), nullable=True)  
    ph_no = Column(String(20), nullable=True)  
    created_by = Column(String(100), ForeignKey('users.users_id'), nullable=True)  
    created_at = Column(TIMESTAMP, default=func.current_timestamp())  

    
    user = relationship("User", foreign_keys=[users_id]) 
    creator = relationship("User", foreign_keys=[created_by]) 

class User(Base):
    __tablename__ = 'users'
    users_id = Column(String(100), primary_key=True)
    email = Column(String(255), unique=True)
    role = Column(String(50))
    created_at = Column(TIMESTAMP, default=func.current_timestamp())

# Define the Organization table
class Organization(Base):
    __tablename__ = 'organization'
    
    organization_id = Column(String(100), primary_key=True)
    organization_name = Column(String(255), nullable=False)
    contact_person = Column(String(255), nullable=True)  
    email = Column(String(255), nullable=True)  
    ph_no = Column(String(20), nullable=True)  
    address = Column(Text, nullable=True)  
    created_at = Column(TIMESTAMP, default=func.current_timestamp())
    created_by = Column(String(100), ForeignKey('users.users_id'))

    # Define the relationship with School
    schools = relationship("School", back_populates="organization") 
 

class School(Base):
    __tablename__ = 'school'
    
    school_id = Column(String(100), primary_key=True)
    school_name = Column(String(255))
    email = Column(String(255), unique=True)
    ph_no = Column(String(20))
    addr = Column(String(255))
    created_at = Column(TIMESTAMP, default=func.current_timestamp())
    
    organization_id = Column(String(100), ForeignKey('organization.organization_id'))
    created_by = Column(String(100), ForeignKey('users.users_id'))

    created_by_user = relationship("User", backref="school_created", foreign_keys=[created_by])

    
    
    organization = relationship("Organization", back_populates="schools")

  
    school_tsc_mappings = relationship("SchoolTscMapping", back_populates="school")

class Tsc(Base):
    __tablename__ = 'tsc'
    
    tsc_id = Column(String(100), primary_key=True)
    users_id = Column(String(100), ForeignKey('users.users_id'))
    tsc_name = Column(String(255))
    email = Column(String(255), unique=True)
    ph_no = Column(String(20))
    gender = Column(String(10))
    created_at = Column(TIMESTAMP, default=func.current_timestamp())
    created_by = Column(String(100), ForeignKey('users.users_id'))

    created_by_user = relationship("User", backref="tsc_created", foreign_keys=[created_by])
    
    
    school_tsc_mappings = relationship("SchoolTscMapping", back_populates="tsc")

class Teacher(Base):
    __tablename__ = 'teacher'
    teacher_id = Column(String(100), primary_key=True)
    users_id = Column(String(100), ForeignKey('users.users_id'))
    teacher_name = Column(String(255))
    school_id = Column(String(50), ForeignKey('school.school_id'))
    classes = Column(Integer)
    number_of_students = Column(Integer)
    gender = Column(String(10))
    email = Column(String(255), unique=True)
    dob = Column(Date)
    age = Column(Integer)
    ph_no = Column(String(20))
    created_at = Column(TIMESTAMP, default=func.current_timestamp())
    created_by = Column(String(100), ForeignKey('users.users_id'))

    created_by_user = relationship("User", backref="teachers_created", foreign_keys=[created_by])


class SchoolTscMapping(Base):
    __tablename__ = 'school_tsc_mapping'
    
    mapping_id = Column(String(100), primary_key=True)
    school_id = Column(String(50), ForeignKey('school.school_id'))
    tsc_id = Column(String(100), ForeignKey('tsc.tsc_id'))
    created_at = Column(TIMESTAMP, default=func.current_timestamp())
    
    
    school = relationship("School", back_populates="school_tsc_mappings")
    tsc = relationship("Tsc", back_populates="school_tsc_mappings")

class SessionStudentsDetails(Base):
    __tablename__ = 'session_students_details'
    se_st_det_id = Column(String(100), primary_key=True)
    no_of_students = Column(Integer)
    grade = Column(Integer)
    section = Column(String(255))
    feedback = Column(String(255))
    created_at = Column(TIMESTAMP, default=func.current_timestamp())

class TeachersProjects(Base):
    __tablename__ = 'teachers_projects'
    tea_pro_id = Column(String(100), primary_key=True)
    teacher_id = Column(String(100), ForeignKey('teacher.teacher_id'))
    project_link = Column(String(255))
    feedback = Column(String(255))
    status = Column(String(50), default='pending')
    created_at = Column(TIMESTAMP, default=func.current_timestamp())

class StudentProjects(Base):
    __tablename__ = 'student_projects'
    stu_pro_id = Column(String(100), primary_key=True)
    teacher_id = Column(String(100), ForeignKey('teacher.teacher_id'))
    project_link = Column(String(255))
    status = Column(String(50), default='pending')
    se_st_det_id = Column(String(100), ForeignKey('session_students_details.se_st_det_id'))
    created_at = Column(TIMESTAMP, default=func.current_timestamp())

class TeachersScore(Base):
    __tablename__ = 'teachers_score'
    tea_sc_id = Column(String(100), primary_key=True)
    tea_pro_id = Column(String(100), ForeignKey('teachers_projects.tea_pro_id'))
    tsc_id = Column(String(100), ForeignKey('tsc.tsc_id'))
    creativity = Column(Integer)
    code_complexity = Column(Integer)
    originality_of_code = Column(Integer)
    usage_of_spr_bd = Column(Integer)
    animations_sounds = Column(Integer)
    total = Column(Integer)
    feedback = Column(String(255))
    evaluated_by = Column(String(100), ForeignKey('users.users_id'))
    created_at = Column(TIMESTAMP, default=func.current_timestamp())

class StudentsScore(Base):
    __tablename__ = 'students_score'
    st_sc_id = Column(String(100), primary_key=True)
    stu_pro_id = Column(String(100), ForeignKey('student_projects.stu_pro_id'))
    tsc_id = Column(String(100), ForeignKey('tsc.tsc_id'))
    creativity = Column(Integer)
    code_complexity = Column(Integer)
    originality_of_code = Column(Integer)
    usage_of_spr_bd = Column(Integer)
    animations_sounds = Column(Integer)
    total = Column(Integer)
    feedback = Column(String(255))
    evaluated_by = Column(String(100), ForeignKey('users.users_id'))
    created_at = Column(TIMESTAMP, default=func.current_timestamp())