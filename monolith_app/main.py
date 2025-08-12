from models import *
from sqlalchemy.exc import SQLAlchemyError
from fastapi import FastAPI, Depends, HTTPException, status, Response, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, select, func
from sqlalchemy import Column, String, Integer, Date, TIMESTAMP
import logging
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Mapped, mapped_column, Session, sessionmaker, relationship
import firebase_admin
from firebase_admin import credentials, auth, firestore
import secrets
import string
import uuid
import uvicorn
from sqlalchemy.exc import IntegrityError
import re

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

# FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize Firebase app if it's not already initialized
cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
if cred_path and os.path.isfile(cred_path):
    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
else:
    print("Firebase credentials file not found at the specified path.")

def generate_random_password(length: int = 12) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

# Pydantic models
class UserResponse(BaseModel):
    users_id: str
    email: str
    role: str

    class Config:
        orm_mode = True

class TeachersScoreCreate(BaseModel):
    creativity: Optional[int] = None
    code_complexity: Optional[int] = None
    originality_of_code: Optional[int] = None
    usage_of_spr_bd: Optional[int] = None
    animations_sounds: Optional[int] = None
    total: Optional[int] = None
    feedback: Optional[str] = None
    evaluated_by: Optional[str] = None

    class Config:
        orm_mode = True

class StudentsScoreCreate(BaseModel):
    creativity: Optional[int] = None
    code_complexity: Optional[int] = None
    originality_of_code: Optional[int] = None
    usage_of_spr_bd: Optional[int] = None
    animations_sounds: Optional[int] = None
    total: Optional[int] = None
    feedback: Optional[str] = None
    evaluated_by: Optional[str] = None

    class Config:
        orm_mode = True

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

class ProjectLink(BaseModel):
    project_id: str
    project_link: str
    uploaded_time: datetime
    status: str

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

class TeacherProjectUpload(BaseModel):
    project_link: str

    feedback: Optional[str] = None

class SessionStudentData(BaseModel):
    no_of_students: int
    grade: int
    section: str
    feedback: str

class StudentProjectUpload(BaseModel):
    project_link: str

class StudentProjectBatchUpload(BaseModel):
    session_data: SessionStudentData
    projects: List[StudentProjectUpload]

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#
# Admins Endpoints
#

@app.get("/get-user/{users_id}", response_model=UserResponse)
async def get_user(users_id: str, db: Session = Depends(get_db)):
    print("hellow")
    print(users_id)
    try:
        user = db.query(User).filter(User.users_id == users_id).first()
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


@app.post("/add-admin/{users_id}")
def add_admin(
    users_id: str,
    name: str,
    email: str,
    ph_no: str,
    db: Session = Depends(get_db)
):
    """Creates a admin user in Firebase, inserts user details into MySQL,
       and links the admin to a school in the school_tsc_mapping table."""

    firebase_uid = None
    generated_password = None
    try:
        # Step 1: Generate a random password (e.g., 12 characters long)
        generated_password = generate_random_password()
        # Step 2: Create a user in Firebase Authentication
        user = auth.create_user(email=email, password=generated_password)
        firebase_uid = user.uid

        # Step 3: Create User record in MySQL using SQLAlchemy
        new_user = User(users_id=firebase_uid, email=email, role="admin")
        db.add(new_user)
        db.commit()

         # Step 4: Create Admin record in MySQL using SQLAlchemy
        new_admin = Admin(
            admin_id=str(uuid4()),
            users_id=firebase_uid,
            admin_name=name,
            email=email,
            ph_no=ph_no,
            created_by=users_id,
        )
        db.add(new_admin)
        db.commit()

        # Return success response
        return {
            "message": "Admin added successfully",
            "firebase_uid": firebase_uid,
            "admin_id": new_admin.admin_id
        }
    except firebase_admin.exceptions.FirebaseError as fb_error:
        if firebase_uid:
            try:
                # Delete Firebase user if MySQL insert fails
                auth.delete_user(firebase_uid)
            except Exception as delete_error:
                raise HTTPException(status_code=500, detail=f"Firebase Error: Could not delete user after DB error: {delete_error}")
        raise HTTPException(status_code=500, detail=f"Firebase Error: {fb_error}")

    except SQLAlchemyError as db_error:
        db.rollback()
        if firebase_uid:
            try:
                # Delete Firebase user if MySQL insert fails
                auth.delete_user(firebase_uid)
            except Exception as delete_error:
                raise HTTPException(status_code=500, detail=f"Firebase Error: Could not delete user after DB error: {delete_error}")
        raise HTTPException(status_code=500, detail=f"Database Error: {db_error}")

    except Exception as e:
        db.rollback()
        if firebase_uid:
            try:
                # Delete Firebase user if any unexpected error occurs
                auth.delete_user(firebase_uid)
            except Exception as delete_error:
                raise HTTPException(status_code=500, detail=f"Error deleting Firebase user: {delete_error}")
        raise HTTPException(status_code=400, detail=f"Error: {e}")

@app.patch("/update-admin/{admin_id}")
def update_admin(
    admin_id: str,
    email: Optional[str] = None,
    admin_name: Optional[str] = None,
    ph_no: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Updates the admin's details in MySQL and Firebase."""

    try:
        admin_in_db = db.query(Admin).filter(Admin.admin_id == admin_id).first()
        if not admin_in_db:
            raise HTTPException(status_code=404, detail="Admin not found in database")

        # Step 1: Update user in Firebase (only email can be updated)
        if email:
            auth.update_user(admin_in_db.users_id, email=email)

        # Step 2: Update user in MySQL database
        user_in_db = db.query(User).filter(User.users_id == admin_in_db.users_id,).first()
        if user_in_db:
            if email:
                user_in_db.email = email

            db.commit()
        else:
            raise HTTPException(status_code=404, detail="Admin not found in database")
        # Step 4: Update admin details in the Admin table
        if admin_name:
            admin_in_db.admin_name = admin_name
        if ph_no:
            admin_in_db.ph_no = ph_no
        if email:
            admin_in_db.email = email

        db.commit()



        return {"message": "Admin details updated successfully"}

    except firebase_admin.exceptions.FirebaseError as fb_error:
        raise HTTPException(status_code=500, detail=f"Firebase Error: {fb_error}")

    except SQLAlchemyError as db_error:
        db.rollback()  # Rollback in case of any MySQL error
        raise HTTPException(status_code=500, detail=f"Database Error: {db_error}")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {e}")

@app.delete("/delete-admin/{admin_id}")
def delete_admin(
    admin_id: str,  # Firebase UID to identify the admin
    db: Session = Depends(get_db)
):
    """Deletes an admin from Firebase and MySQL."""

    try:
        # Step 1: Fetch the admin record from the Admin table
        admin_in_db = db.query(Admin).filter(Admin.admin_id == admin_id).first()
        if not admin_in_db:
            raise HTTPException(status_code=404, detail="Admin not found in database")

         # Step 2: Delete user from Firebase
        auth.delete_user(admin_in_db.users_id)

        # Step 3: Delete the admin record from the Admin table
        db.delete(admin_in_db)

        # Step 2: Delete user from MySQL database
        user_in_db = db.query(User).filter(User.users_id == admin_in_db.users_id).first()
        if user_in_db:
            db.delete(user_in_db)
        else:
            raise HTTPException(status_code=404, detail="User not found in database")

        db.commit()

        return {"message": "Admin and user deleted successfully"}

    except firebase_admin.exceptions.FirebaseError as fb_error:
        raise HTTPException(status_code=500, detail=f"Firebase Error: {fb_error}")

    except SQLAlchemyError as db_error:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {db_error}")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {e}")



# Endpoint to fetch dashboard data
@app.get("/admin_dashboard/{users_id}")
def get_dashboard_data(
    users_id: str = Path(..., description="The ID of the user to fetch dashboard data for"),  # User ID as path parameter
    db: Session = Depends(get_db),
):
    try:
        # Step 1: Query the User table to check the user's role
        user = db.query(User).filter(User.users_id == users_id).first()

        # Step 2: If the user does not exist, return a 404 error
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Step 3: Check if the user is an admin
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="You are not authorized to access this data")
         # Fetch admin details based on users_id

        admin = db.query(Admin).filter(Admin.users_id == users_id).first()
         # If admin not found, raise an exception

        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")

        # 1. Number of schools
        num_schools = db.query(School).count()

        # 2. Number of teachers
        num_teachers = db.query(Teacher).count()

        # 3. Number of student projects
        num_student_projects = db.query(StudentProjects).count()

        # 4. Number of teacher projects
        num_teacher_projects = db.query(TeachersProjects).count()

        # 5. Number of evaluated projects (completed status)
        num_evaluated_projects = (
            db.query(StudentProjects)
            .filter(StudentProjects.status == 'completed')
            .count() +
            db.query(TeachersProjects)
            .filter(TeachersProjects.status == 'completed')
            .count()
        )

        # 6. Number of projects to be evaluated (pending status)
        num_projects_to_be_evaluated = (
            db.query(StudentProjects)
            .filter(StudentProjects.status == 'pending')
            .count() +
            db.query(TeachersProjects)
            .filter(TeachersProjects.status == 'pending')
            .count()
        )

        # 7. Get teacher details along with cumulative score and weekly score
        teacher_details = db.query(Teacher).all()

        # Prepare the result
        teacher_data = []
        for teacher in teacher_details:
            # Cumulative score: Sum of teacher's and student's project scores
            cumulative_score = (
                db.query(func.coalesce(func.sum(TeachersScore.total), 0))
                .join(TeachersProjects, TeachersScore.tea_pro_id == TeachersProjects.tea_pro_id)
                .filter(TeachersProjects.teacher_id == teacher.teacher_id)
                .scalar() +
                db.query(func.coalesce(func.sum(StudentsScore.total), 0))
                .join(StudentProjects, StudentsScore.stu_pro_id == StudentProjects.stu_pro_id)
                .filter(StudentProjects.teacher_id == teacher.teacher_id)
                .scalar()
            )

            # Weekly score: Sum of teacher's and student's project scores for the current week
            start_of_week = datetime.now() - timedelta(days=datetime.now().weekday())  # Get start of the week (Monday)
            end_of_week = start_of_week + timedelta(days=7)  # Get end of the week (Sunday)

            weekly_score = (
                db.query(func.coalesce(func.sum(TeachersScore.total), 0))
                .join(TeachersProjects, TeachersScore.tea_pro_id == TeachersProjects.tea_pro_id)
                .filter(TeachersProjects.teacher_id == teacher.teacher_id)
                .filter(TeachersScore.created_at >= start_of_week)
                .filter(TeachersScore.created_at < end_of_week)
                .scalar() +
                db.query(func.coalesce(func.sum(StudentsScore.total), 0))
                .join(StudentProjects, StudentsScore.stu_pro_id == StudentProjects.stu_pro_id)
                .filter(StudentProjects.teacher_id == teacher.teacher_id)
                .filter(StudentsScore.created_at >= start_of_week)
                .filter(StudentsScore.created_at < end_of_week)
                .scalar()
            )

            # Append teacher details with scores
            teacher_data.append({
                "teacher_id": teacher.teacher_id,
                "teacher_name": teacher.teacher_name,
                "number_of_students": teacher.number_of_students,
                "classes_managed": teacher.classes,
                "cumulative_score": cumulative_score,
                "weekly_score": weekly_score
            })

        # Return the gathered data
        return {
            "admin_details": {
                "admin_id": admin.admin_id,
                "admin_name": admin.admin_name,
                "email": admin.email,
                "ph_no": admin.ph_no,
                "created_by": admin.created_by,
                "created_at": admin.created_at
            },
            "number_of_schools": num_schools,
            "number_of_teachers": num_teachers,
            "number_of_student_projects": num_student_projects,
            "number_of_teacher_projects": num_teacher_projects,
            "number_of_evaluated_projects": num_evaluated_projects,
            "number_of_projects_to_be_evaluated": num_projects_to_be_evaluated,
            "teacher_details": teacher_data
        }

    except Exception as e:
        # Log the error and raise an HTTPException
        print(f"Error while querying the database: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving dashboard data: {e}")

@app.get("/organizations")
def get_all_organizations(db: Session = Depends(get_db)):
    """Fetches all organizations."""
    try:
        organizations = db.query(Organization).all()
        return {"organizations": organizations}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching organizations: {e}")

@app.get("/organization/{organization_id}")
def get_organization_by_id(organization_id: str, db: Session = Depends(get_db)):
    """Fetches a specific organization by its organization_id."""
    try:
        # Query to get the organization by organization_id
        organization = db.query(Organization).filter(Organization.organization_id == organization_id).first()

        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        return {"organization": organization}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching organization: {e}")


@app.post("/organizations/{users_id}")
def create_organization(
    users_id: str,
    organization_name: str,
    contact_person: str | None = None,
    email: str | None = None,
    ph_no: str | None = None,
    address: str | None = None,
    db: Session = Depends(get_db)
):
    """Creates a new organization."""
    try:
        # Check if the organization already exists
        existing_org = db.query(Organization).filter(Organization.organization_name == organization_name).first()
        if existing_org:
            raise HTTPException(status_code=400, detail="Organization with this name already exists.")

        organization_id = str(uuid4())

        # Create a new Organization object
        new_organization = Organization(
            organization_id=organization_id,
            organization_name=organization_name,
            contact_person=contact_person,
            email=email,
            ph_no=ph_no,
            address=address,
            created_by=users_id
        )

        # Add the organization to the session and commit
        db.add(new_organization)
        db.commit()

        # Return a success message
        return {"message": "Organization created successfully", "organization_id": new_organization.organization_id}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating organization: {e}")

@app.patch("/organizations/{users_id}/{organization_id}")
def update_organization(
    users_id: str,
    organization_id: str,
    organization_name: str | None = None,
    contact_person: str | None = None,
    email: str | None = None,
    ph_no: str | None = None,
    address: str | None = None,
    db: Session = Depends(get_db)
):
    """Updates an organization using its UUID (organization_id) and users_id."""
    try:
        # Check if the user exists (this can be done based on users_id)
        user = db.query(User).filter(User.users_id == users_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        # Fetch the organization by its ID
        organization = db.query(Organization).filter(Organization.organization_id == organization_id).first()

        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found.")

        # Update the fields that were provided in the request
        if organization_name:
            organization.organization_name = organization_name
        if contact_person:
            organization.contact_person = contact_person
        if email:
            organization.email = email
        if ph_no:
            organization.ph_no = ph_no
        if address:
            organization.address = address

        # Update the 'created_by' field with the new user (users_id)
        organization.created_by = users_id

        # Commit the changes
        db.commit()

        # Return a success message (No need to return the updated data)
        return {"message": "Organization updated successfully."}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating organization: {e}")

@app.delete("/organizations/{organization_id}")
def delete_organization(
    organization_id: str,
    db: Session = Depends(get_db)
):
    """Deletes an organization using its UUID (organization_id)."""
    try:
        # Fetch the organization by its ID
        organization = db.query(Organization).filter(Organization.organization_id == organization_id).first()

        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found.")

        # Delete the organization
        db.delete(organization)
        db.commit()

        return {"message": "Organization deleted successfully."}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting organization: {e}")



@app.get("/schools")
def get_all_schools(db: Session = Depends(get_db)):
    try:
        # Query the School table and perform an outerjoin with the Organization table
        schools = db.query(
            School.school_id,
            School.school_name,
            School.addr,
            School.email,
            School.ph_no,
            func.count(Teacher.teacher_id).label('teacher_count'),
            School.organization_id,
            Organization.organization_name
        ) \
        .outerjoin(Teacher, Teacher.school_id == School.school_id) \
        .outerjoin(Organization, Organization.organization_id == School.organization_id) \
        .group_by(School.school_id, Organization.organization_id, Organization.organization_name) \
        .all()  # Executes the query

        # Prepare the response data as a list of dictionaries
        school_data = [
            {
                "School_id": school.school_id,
                "school_name": school.school_name,
                "address": school.addr,
                "email": school.email,
                "contact_no": school.ph_no,
                "no_of_teachers": school.teacher_count,
                "organization_id": school.organization_id,
                "organization_name": school.organization_name if school.organization_name else "No Organization"  # Handle NULL organization name
            }
            for school in schools
        ]

        return {"schools": school_data}

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error retrieving schools data.")


@app.get("/school/{school_id}")
def get_school_by_id(school_id: str, db: Session = Depends(get_db)):
    """Fetches a specific school by its school_id."""
    try:
        # Query to get the school by school_id and also count the number of teachers for that school
        school = db.query(
            School.school_id,
            School.school_name,
            School.addr,
            School.email,
            School.ph_no,
            func.count(Teacher.teacher_id).label('teacher_count'),
            Organization.organization_id,
            Organization.organization_name
        ) \
        .outerjoin(Teacher, Teacher.school_id == School.school_id) \
        .join(Organization, Organization.organization_id == School.organization_id) .filter(School.school_id == school_id) \
        .group_by(School.school_id, Organization.organization_id, Organization.organization_name) .first()

        # If no school found, return a 404 error
        if not school:
            raise HTTPException(status_code=404, detail="School not found")

        # Prepare the response data
        school_data = {
            "School_id": school.school_id,
            "school_name": school.school_name,
            "address": school.addr,
            "email": school.email,
            "contact_no": school.ph_no,
            "no_of_teachers": school.teacher_count,
            "organization_id": school.organization_id,
            "organization_name": school.organization_name
        }

        return {"school": school_data}

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error retrieving school data.")

#
# Profile Login Endpoints
#

@app.get("/profileget/{users_id}")
async def get_user_profile(users_id: str, db: Session = Depends(get_db)):
    logger.info(f"Fetching profile for users_id: {users_id}")

    try:
        # Check if user exists in the Users table
        user = db.query(User).filter(User.users_id == users_id).first()
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
        user = db.query(User).filter(User.users_id == user_id).first()
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

#
# Teacher API Endpoints
#

@app.get("/dashboard/{user_id}", response_model=DashboardResponse)
async def get_teacher_dashboard(user_id: str, db: Session = Depends(get_db)):
    # Step 1: Fetch teacher_id based on user_id
    teacher = db.query(Teacher).filter(Teacher.users_id == user_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found for the given user")

    teacher_id = teacher.teacher_id
    teacher_name = teacher.teacher_name
    school_id = teacher.school_id
    classes = teacher.classes


    bread_crumb = f"Dashboard > {teacher_name} > Projects"

     # Step 2: Fetch the school name
    school = db.query(School).filter(School.school_id == school_id).first()
    school_name = school.school_name if school else "Unknown School"

    # Step 2: Fetch number of teacher projects
    num_teacher_projects = db.query(func.count(TeachersProjects.tea_pro_id))\
                             .filter(TeachersProjects.teacher_id == teacher_id).scalar()

    # Step 3: Fetch number of student projects
    num_student_projects = db.query(func.count(StudentProjects.stu_pro_id))\
                             .filter(StudentProjects.teacher_id == teacher_id).scalar()



  # Step 5: Fetch total number of students for the teacher
    total_students = db.query(Teacher.number_of_students)\
                   .filter(Teacher.teacher_id == teacher_id).scalar()

    # Fetching teacher project links and their respective project IDs
    teacher_project_links = db.query(TeachersProjects.tea_pro_id, TeachersProjects.project_link, TeachersProjects.created_at, TeachersProjects.status) \
    .filter(TeachersProjects.teacher_id == teacher_id).all()

    # Ensure data is in the correct format: List of ProjectLink objects
    teacher_project_links = [
        ProjectLink(project_id=link.tea_pro_id, project_link=link.project_link, uploaded_time=link.created_at, status=link.status)
        for link in teacher_project_links
    ]

    # Fetching student project links and their respective project IDs
    student_project_links = db.query(StudentProjects.stu_pro_id, StudentProjects.project_link, StudentProjects.created_at, StudentProjects.status) \
    .filter(StudentProjects.teacher_id == teacher_id).all()

    # Ensure data is in the correct format: List of ProjectLink objects
    student_project_links = [
        ProjectLink(project_id=link.stu_pro_id, project_link=link.project_link, uploaded_time=link.created_at, status=link.status)
        for link in student_project_links
]
      # Parse the 'classes' field if it's a comma-separated string and convert to a list of integers
    if isinstance(classes, str):
        classes = [int(c.strip()) for c in classes.split(',')]

    # Return the dashboard data
    return DashboardResponse(
        teacher_id=teacher_id,
        teacher_name=teacher_name,
        school_name=school_name,
        bread_crumb=bread_crumb,
        num_teacher_projects=num_teacher_projects,
        num_student_projects=num_student_projects,
        distinct_grades=classes,
        total_students=total_students,
        teacher_project_links=teacher_project_links,
        student_project_links=student_project_links
    )


@app.delete("/delete_teacher_project/{project_id}")
async def delete_teacher_project(
    project_id: str, db: Session = Depends(get_db), response: Response = None
):
    # Check if the project exists in teachers_projects
    project = db.query(TeachersProjects).filter(TeachersProjects.tea_pro_id == project_id).first()

    if project:

        if project.status == 'completed':
            raise HTTPException(status_code=400, detail="Project status is 'completed'. Deletion not allowed.")

        # Delete the teacher project record (related records will be deleted due to ON DELETE CASCADE)
        db.delete(project)
        db.commit()

        # Set a custom header and return a success message
        if response is None:
            response = Response()
        response.headers["X-Message"] = "Teacher project deleted successfully along with related evaluations"
        response.status_code = 200
        response.body = b'{"message": "Teacher project deleted successfully."}'
        response.media_type = "application/json"
        return response

    # If project not found in teachers_projects
    raise HTTPException(status_code=404, detail="Teacher project not found")

@app.delete("/delete_student_project/{project_id}")
async def delete_student_project(
    project_id: str, db: Session = Depends(get_db), response: Response = None
):
    # Check if the project exists in Student_projects
    project = db.query(StudentProjects).filter(StudentProjects.stu_pro_id == project_id).first()

    if project:

        if project.status == 'completed':
            raise HTTPException(status_code=400, detail="Project status is 'completed'. Deletion not allowed.")


        # Delete the Student project record (related records will be deleted due to ON DELETE CASCADE)
        db.delete(project)
        db.commit()

        # Set a custom header and return a success message
        if response is None:
            response = Response()
        response.headers["X-Message"] = "Student project deleted successfully along with related evaluations"
        response.status_code = 200
        response.body = b'{"message": "Student project deleted successfully."}'
        response.media_type = "application/json"
        return response

@app.post("/upload_teacher_projects/{teacher_id}")
async def upload_teacher_projects(
    teacher_id: str,
    project_batch: List[TeacherProjectUpload],
    db: Session = Depends(get_db)
):
    # Step 1: Verify if the teacher exists based on teacher_id
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # Step 2: List to store generated teacher project IDs
    response_messages = []
    teacher_project_ids = []

    # Step 3: Iterate over the teacher projects and upload them
    for project in project_batch:

        project_link = project.project_link

        # Step 3.1: Check if the project link already exists in the student_projects table
        existing_student_project = db.query(StudentProjects).filter(StudentProjects.project_link == project_link).first()
        if existing_student_project:
            response_messages.append(f"Project link '{project_link}' already exists in student projects.")
            continue


        # Step 3.1: Generate a new UUID for each project link
        teacher_project_id = str(uuid.uuid4())

        # Step 3.2: Create new teacher project entry
        new_teacher_project = TeachersProjects(
            tea_pro_id=teacher_project_id,
            teacher_id=teacher_id,
            project_link=project_link,
            feedback=project.feedback,
            status="pending",
        )
        db.add(new_teacher_project)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            # Check for duplicate project link error and handle it
            if 'Duplicate entry' in str(e.orig):
                response_messages.append(f"Error: The project link '{project_link}' already exists in the teacher projects table.")
            else:
                # For other IntegrityErrors, you can log or return a generic message
                response_messages.append(f"Error: IntegrityError occurred while inserting project '{project_link}': {str(e)}")
            continue  # Skip the current project if error occurs


        # Step 3.3: Add the generated teacher project ID to the list
        teacher_project_ids.append(teacher_project_id)
        response_messages.append(f"Project '{project_link}' uploaded successfully.")

        # Step 4: Return success response with teacher project IDs and messages
    return {"message": response_messages, "teacher_project_ids": teacher_project_ids}


@app.post("/upload_student_projects/{teacher_id}")
async def upload_student_projects(
    teacher_id: str,
    project_batch: StudentProjectBatchUpload,
    db: Session = Depends(get_db)
):
    # Step 1: Verify if the teacher exists based on teacher_id
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # Step 2: Store session student details first (only once)
    session_data = project_batch.session_data
    session_id = str(uuid.uuid4())

    # Step 3: Create new session data entry
    new_session_data = SessionStudentsDetails(
        se_st_det_id=session_id,
        no_of_students=session_data.no_of_students,
        grade=session_data.grade,
        section=session_data.section,
        feedback=session_data.feedback
    )
    db.add(new_session_data)
    db.commit()

    # Step 5: List to store generated student project IDs
    response_messages = []
    student_project_ids = []


    # Step 4: Iterate over the student projects and upload them
    for project in project_batch.projects:

    # # Step 5: Extract the project ID from the original link (if the link is valid)
    #     project_id_match = re.search(r'projects/(\d+)', project.project_link)
    #     if not project_id_match:
    #         raise HTTPException(status_code=400, detail="Invalid project link format")

        project_link = project.project_link

        # Step 5.1: Check if the project link already exists in the teachers_projects table
        existing_teacher_project = db.query(TeachersProjects).filter(TeachersProjects.project_link == project_link).first()
        if existing_teacher_project:
            response_messages.append(f"Project link '{project_link}' already exists in teacher projects.")
            continue


        # Step 7: Generate a new UUID for each student project
        student_project_id = str(uuid.uuid4())

        # Step 8: Create new student project entry
        new_student_project = StudentProjects(
            stu_pro_id=student_project_id,
            teacher_id=teacher_id,
            project_link=project_link,
            se_st_det_id=session_id
        )
        db.add(new_student_project)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            # Check for duplicate project link error and handle it
            if 'Duplicate entry' in str(e.orig):
                response_messages.append(f"Error: The project link '{project_link}' already exists in the student projects table.")
            else:
                # For other IntegrityErrors, you can log or return a generic message
                response_messages.append(f"Error: IntegrityError occurred while inserting project '{project_link}': {str(e)}")
            continue  # Skip the current project if error occurs

        # Step 9: Add the generated student project ID to the list
        student_project_ids.append(student_project_id)
        response_messages.append(f"Project '{project_link}' uploaded successfully.")

       # Step 9: Return success response with student project IDs and messages
    return {"message": response_messages, "student_project_ids": student_project_ids}

@app.get("/teacher_project_scores/{project_id}")
async def get_teacher_project_scores(project_id: str, db: Session = Depends(get_db)):
    # Fetch project details for the given teacher project ID
    teacher_project = db.query(TeachersProjects).filter(TeachersProjects.tea_pro_id == project_id).first()

    if not teacher_project:
        raise HTTPException(status_code=404, detail="Teacher project not found")

    # Fetch scores for the teacher project
    teacher_score = db.query(TeachersScore).filter(TeachersScore.tea_pro_id == project_id).first()

    # If scores not found, use '/null' for the score values
    if not teacher_score:
        teacher_score = {
            "creativity": 0,
            "code_complexity": 0,
            "originality_of_code": 0,
            "usage_of_spr_bd": 0,
            "animations_sounds": 0,
            "total": 0,
            "feedback": ""
        }
    else:
        teacher_score = {
            "creativity": teacher_score.creativity or 0,
            "code_complexity": teacher_score.code_complexity or 0,
            "originality_of_code": teacher_score.originality_of_code or 0,
            "usage_of_spr_bd": teacher_score.usage_of_spr_bd or 0,
            "animations_sounds": teacher_score.animations_sounds or 0,
            "total": teacher_score.total or 0,
            "feedback": teacher_score.feedback if teacher_score.feedback else ""
        }

    # Get the teacher's school and organization information
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_project.teacher_id).first()

    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # Fetch the school details related to the teacher
    school = db.query(School).filter(School.school_id == teacher.school_id).first()

    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # Fetch the organization details related to the school
    organization = db.query(Organization).filter(Organization.organization_id == school.organization_id).first()

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Get the status from the teacher_project
    project_status = teacher_project.status

    # Return the project link, scores, status, and teacher, school, organization details
    return {
        "project_link": teacher_project.project_link,
        "scores": teacher_score,
        "status": project_status,
        "project_id": teacher_project.tea_pro_id,
        "teacher_name": teacher.teacher_name,
        "school_name": school.school_name,
        "organization_name": organization.organization_name,
    }



@app.get("/student_project_scores/{project_id}")
async def get_student_project_scores(project_id: str, db: Session = Depends(get_db)):
    # Fetch project details for the given student project ID
    student_project = db.query(StudentProjects).filter(StudentProjects.stu_pro_id == project_id).first()

    if not student_project:
        raise HTTPException(status_code=404, detail="Student project not found")

    # Fetch scores for the student project
    student_score = db.query(StudentsScore).filter(StudentsScore.stu_pro_id == project_id).first()

    # If no scores are found, use default values (e.g., zeros or nulls)
    if not student_score:
        student_score = {
            "creativity": 0,
            "code_complexity": 0,
            "originality_of_code": 0,
            "usage_of_spr_bd": 0,
            "animations_sounds": 0,
            "total": 0,
            "feedback": ""
        }
    else:
        student_score = {
            "creativity": student_score.creativity or 0,
            "code_complexity": student_score.code_complexity or 0,
            "originality_of_code": student_score.originality_of_code or 0,
            "usage_of_spr_bd": student_score.usage_of_spr_bd or 0,
            "animations_sounds": student_score.animations_sounds or 0,
            "total": student_score.total or 0,
            "feedback": student_score.feedback if student_score.feedback else ""
        }

    # Get the teacher_id for the project
    teacher = db.query(Teacher).filter(Teacher.teacher_id == student_project.teacher_id).first()

    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # Fetch the school details related to the teacher
    school = db.query(School).filter(School.school_id == teacher.school_id).first()

    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # Fetch the organization details related to the school
    organization = db.query(Organization).filter(Organization.organization_id == school.organization_id).first()

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Get the status of the student project
    project_status = student_project.status

    # Return the project link, scores, status, and related details
    return {
        "project_link": student_project.project_link,
        "project_id": student_project.stu_pro_id,
        "scores": student_score,
        "status": project_status,
        "teacher_name": teacher.teacher_name,
        "school_name": school.school_name,
        "organization_name": organization.organization_name,
    }
@app.get("/teachers")
def get_all_teachers(db: Session = Depends(get_db)):
    try:
        # Query the Teacher table and get the required fields
        teachers = db.query(
            Teacher.teacher_id,
            Teacher.teacher_name,
            Teacher.email,
            Teacher.ph_no,
            Teacher.classes,
            Teacher.number_of_students,
            Teacher.gender,
            Teacher.dob,
            Teacher.age,
            Teacher.created_at,
            School.school_name
        ) \
        .join(School, Teacher.school_id == School.school_id) \
        .all()

        # Prepare the response data as a list of dictionaries
        teacher_data = [
            {
                "teacher_id": teacher.teacher_id,
                "teacher_name": teacher.teacher_name,
                "email": teacher.email,
                "contact_no": teacher.ph_no,
                "classes": teacher.classes,
                "no_of_students": teacher.number_of_students,
                "gender": teacher.gender,
                "dob": teacher.dob.strftime('%Y-%m-%d') if teacher.dob else None,
                "age": teacher.age,
                "created_at": teacher.created_at.strftime('%Y-%m-%d %H:%M:%S') if teacher.created_at else None,
                "school_name": teacher.school_name
            }
            for teacher in teachers
        ]

        return {"teachers": teacher_data}

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error retrieving teachers data.")

@app.get("/teacher/{teacher_id}")
def get_teacher_by_id(teacher_id: str, db: Session = Depends(get_db)):
    """Fetches a specific teacher by their teacher_id."""
    try:
        # Query to get the teacher by teacher_id along with the school name
        teacher = db.query(
            Teacher.teacher_id,
            Teacher.teacher_name,
            Teacher.email,
            Teacher.ph_no,
            Teacher.classes,
            Teacher.number_of_students,
            Teacher.gender,
            Teacher.dob,
            Teacher.age,
            Teacher.created_at,
            School.school_name
        ) \
        .join(School, Teacher.school_id == School.school_id) \
        .filter(Teacher.teacher_id == teacher_id) \
        .first()

        # If no teacher found, return a 404 error
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")

        # Prepare the response data
        teacher_data = {
            "teacher_id": teacher.teacher_id,
            "teacher_name": teacher.teacher_name,
            "email": teacher.email,
            "contact_no": teacher.ph_no,
            "classes": teacher.classes,
            "no_of_students": teacher.number_of_students,
            "gender": teacher.gender,
            "dob": teacher.dob.strftime('%Y-%m-%d') if teacher.dob else None,
            "age": teacher.age,
            "created_at": teacher.created_at.strftime('%Y-%m-%d %H:%M:%S') if teacher.created_at else None,
            "school_name": teacher.school_name
        }

        return {"teacher": teacher_data}

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error retrieving teacher data.")

@app.get("/teachers/{school_id}")
def get_teachers_by_school(
    school_id: str,
    db: Session = Depends(get_db)
):
    try:
        # Query the Teacher table based on the school_id and join with the School table
        teachers = db.query(
            Teacher.teacher_id,
            Teacher.teacher_name,
            Teacher.email,
            Teacher.ph_no,
            Teacher.number_of_students,
            School.addr.label('school_address'),
            School.ph_no.label('school_contact_no'),
            School.school_name
        ) \
        .join(School, School.school_id == Teacher.school_id) \
        .filter(Teacher.school_id == school_id).all()

        # Prepare the response data
        teacher_data = [
            {
                "teacher_id": teacher.teacher_id,
                "teacher_name": teacher.teacher_name,
                "email": teacher.email,
                "contact_no": teacher.ph_no,
                "school_name": teacher.school_name,
                "school_address": teacher.school_address,
                "school_contact_no": teacher.school_contact_no,
                "number_of_students": teacher.number_of_students
            }
            for teacher in teachers
        ]

        return {"teachers": teacher_data}

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error retrieving teacher data.")
@app.post("/add-teacher/{users_id}")
def add_teacher(
                users_id: str,
                name: str,
                email: str,
                school_id: str,
                phone_number:str,
                number_of_students:str,
                classes:Optional[str] = None,
                date_of_birth:Optional[str] = None,
                gender: Optional[str] = None,
                age:Optional[str] = None,
                db: Session = Depends(get_db)):
    """Creates a teacher user in Firebase and inserts teacher details into MySQL using SQLAlchemy ORM."""
    firebase_uid = None
    try:
         # Step 1: Generate a random password (e.g., 12 characters long)
        generated_password = generate_random_password()
        # Step 1: Create a user in Firebase Authentication
        user = auth.create_user(email=email, password=generated_password)
        firebase_uid = user.uid

        # Step 2: Create User record in MySQL using SQLAlchemy (adding role as 'teacher')
        new_user = User(users_id=firebase_uid, email=email, role="teacher")
        db.add(new_user)

        # Step 3: Insert into Teacher table with the additional school_id
        teacher_id = str(uuid.uuid4())
        new_teacher = Teacher(
            teacher_id=teacher_id,
            users_id=firebase_uid,
            teacher_name=name,
            email=email,
            school_id=school_id,
            classes=classes,
            number_of_students=number_of_students,
            ph_no=phone_number,
            gender=gender,
            dob=date_of_birth,
            age=age,
            created_by=users_id
        )
        db.add(new_teacher)

        # Commit the transaction after all operations are successful
        db.commit()

        # Return success response
        return {"message": "Teacher added successfully", "firebase_uid": firebase_uid, "teacher_id": teacher_id}

    except firebase_admin.exceptions.FirebaseError as fb_error:
        # Rollback changes in the database if Firebase fails
        if firebase_uid:
            try:
                # Delete Firebase user if MySQL insert fails
                auth.delete_user(firebase_uid)
            except Exception as delete_error:
                raise HTTPException(status_code=500, detail=f"Firebase Error: Could not delete user after DB error: {delete_error}")
        raise HTTPException(status_code=500, detail=f"Firebase Error: {fb_error}")

    except SQLAlchemyError as db_error:
        # Rollback the transaction in case of MySQL error
        db.rollback()
        if firebase_uid:
            try:
                # Delete Firebase user if MySQL insert fails
                auth.delete_user(firebase_uid)
            except Exception as delete_error:
                raise HTTPException(status_code=500, detail=f"Firebase Error: Could not delete user after DB error: {delete_error}")
        raise HTTPException(status_code=500, detail=f"Database Error: {db_error}")

    except Exception as e:
        # Rollback in case of any unexpected error
        db.rollback()
        if firebase_uid:
            try:
                # Delete Firebase user if any unexpected error occurs
                auth.delete_user(firebase_uid)
            except Exception as delete_error:
                raise HTTPException(status_code=500, detail=f"Error deleting Firebase user: {delete_error}")
        raise HTTPException(status_code=400, detail=f"Error: {e}")

@app.patch("/update-teacher/{teacher_id}")
def update_teacher(
    teacher_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone_number: Optional[str] = None,
    school_id: Optional[str] = None,
    number_of_students: Optional[int] = None,
    classes: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    gender: Optional[str] = None,
    age: Optional[int] = None,
    db: Session = Depends(get_db)
):
    try:
        # Fetch the teacher record from DB
        teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()

        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found.")

        # Fetch the user linked with this teacher
        user = db.query(User).filter(User.users_id == teacher.users_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        # Update fields in the teacher record if provided
        if name:
            teacher.teacher_name = name
        if email:
            # Update the email in Firebase and Database if provided
            auth.update_user(teacher.users_id, email=email)

            # Update the email in the users table
            user.email = email

            teacher.email = email

        if phone_number:
            teacher.ph_no = phone_number
        if school_id:
            teacher.school_id = school_id
        if number_of_students is not None:
            teacher.number_of_students = number_of_students
        if classes is not None:
            teacher.classes = classes
        if date_of_birth:
            teacher.dob = date_of_birth
        if gender:
            teacher.gender = gender
        if age is not None:
            teacher.age = age

        # Commit the transaction after all updates are done
        db.commit()

        return {"message": "Teacher details updated successfully", "teacher_id": teacher_id}

    except firebase_admin.exceptions.FirebaseError as fb_error:
        raise HTTPException(status_code=500, detail=f"Firebase Error: {fb_error}")

    except Exception as e:
        db.rollback()  # Rollback in case of any error
        raise HTTPException(status_code=500, detail=f"Error updating Teacher details: {e}")

@app.delete("/delete-teacher/{teacher_id}")
def delete_teacher(teacher_id: str, db: Session = Depends(get_db)):
    try:
        # Fetch the teacher record from DB
        teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()

        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found.")

        # Delete the user from Firebase (remove all associated Firebase data)
        auth.delete_user(teacher.users_id)

        # Delete the user record from the users table
        db.query(User).filter(User.users_id == teacher.users_id).delete()

        # Delete the teacher record from the database
        db.delete(teacher)

        # Commit the transaction after all deletions
        db.commit()

        return {"message": "Teacher and associated records deleted successfully from both Firebase and Database", "teacher_id": teacher_id}

    except firebase_admin.exceptions.FirebaseError as fb_error:
        raise HTTPException(status_code=500, detail=f"Firebase Error: {fb_error}")

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting Teacher: {e}")

@app.get("/teacher_report/{teacher_id}")
def get_teacher_report(
    teacher_id: str = Path(..., description="Teacher ID"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    try:
        # Step 1: Fetch teacher with school name
        teacher = db.query(
            Teacher.teacher_id,
            Teacher.teacher_name,
            Teacher.classes,
            Teacher.number_of_students,
            School.school_name
        ).join(School, Teacher.school_id == School.school_id) \
         .filter(Teacher.teacher_id == teacher_id).first()

        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")

        # Step 2: Get cumulative project counts
        total_teacher_projects = db.query(TeachersProjects).filter(TeachersProjects.teacher_id == teacher_id).count()
        total_student_projects = db.query(StudentProjects).filter(StudentProjects.teacher_id == teacher_id).count()

        # Step 3: Get cumulative score
        cumulative_score = (
            db.query(func.coalesce(func.sum(TeachersScore.total), 0))
            .join(TeachersProjects, TeachersScore.tea_pro_id == TeachersProjects.tea_pro_id)
            .filter(TeachersProjects.teacher_id == teacher_id)
            .scalar()
            +
            db.query(func.coalesce(func.sum(StudentsScore.total), 0))
            .join(StudentProjects, StudentsScore.stu_pro_id == StudentProjects.stu_pro_id)
            .filter(StudentProjects.teacher_id == teacher_id)
            .scalar()
        )

        # Step 4: Date filtering logic
        filtered_start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        filtered_end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) if end_date else None

        def apply_date_filter(queryset, score_field):
            if filtered_start and filtered_end:
                queryset = queryset.filter(score_field >= filtered_start, score_field < filtered_end)
            return queryset

        # Step 5: Filtered scores and counts
        teacher_scores_filtered = apply_date_filter(
            db.query(TeachersScore)
            .join(TeachersProjects, TeachersScore.tea_pro_id == TeachersProjects.tea_pro_id)
            .filter(TeachersProjects.teacher_id == teacher_id),
            TeachersScore.created_at
        ).all()

        student_scores_filtered = apply_date_filter(
            db.query(StudentsScore)
            .join(StudentProjects, StudentsScore.stu_pro_id == StudentProjects.stu_pro_id)
            .filter(StudentProjects.teacher_id == teacher_id),
            StudentsScore.created_at
        ).all()

        teacher_proj_count_filtered = apply_date_filter(
            db.query(TeachersProjects).filter(TeachersProjects.teacher_id == teacher_id),
            TeachersProjects.created_at
        ).count()

        student_proj_count_filtered = apply_date_filter(
            db.query(StudentProjects).filter(StudentProjects.teacher_id == teacher_id),
            StudentProjects.created_at
        ).count()

        total_filtered_score = sum(score.total for score in teacher_scores_filtered + student_scores_filtered)
        total_evaluated_projects = len(teacher_scores_filtered) + len(student_scores_filtered)

        def average(attr):
            values = [
                getattr(score, attr) or 0
                for score in teacher_scores_filtered + student_scores_filtered
                if getattr(score, attr) is not None
            ]
            return round(sum(values) / len(values), 2) if values else 0

        return {
            "teacher_id": teacher.teacher_id,
            "teacher_name": teacher.teacher_name,
            "school_name": teacher.school_name,
            "grade": teacher.classes,
            "number_of_students": teacher.number_of_students,
            "total_teacher_projects": total_teacher_projects,
            "total_student_projects": total_student_projects,
            "cumulative_score": cumulative_score,
            "filtered_report": {
                "start_date": start_date,
                "end_date": end_date,
                "teacher_projects_uploaded": teacher_proj_count_filtered,
                "student_projects_uploaded": student_proj_count_filtered,
                "total_score": total_filtered_score,
                "total_evaluated_projects": total_evaluated_projects,
                "live_average_score": (
                    round(total_filtered_score / total_evaluated_projects, 2)
                    if total_evaluated_projects > 0 else 0
                ),
                "average_criteria_scores": {
                    "creativity": average("creativity"),
                    "code_complexity": average("code_complexity"),
                    "originality_of_code": average("originality_of_code"),
                    "usage_of_spr_bd": average("usage_of_spr_bd"),
                    "animations_sounds": average("animations_sounds")
                }
            }
        }

    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error occurred")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/teacher-projects/{teacher_id}")
def get_teacher_projects_by_teacher_id(
    teacher_id: str,
    db: Session = Depends(get_db)
):
    try:
        # Query the TeachersProjects table to fetch project links for the given teacher_id
        teacher_projects = db.query(TeachersProjects.tea_pro_id, TeachersProjects.project_link) \
                             .filter(TeachersProjects.teacher_id == teacher_id).all()

        if not teacher_projects:
            raise HTTPException(status_code=404, detail="No projects found for the teacher.")

        # Prepare the response data
        project_data = [
            {
                "project_id": project.tea_pro_id,
                "project_link": project.project_link
            }
            for project in teacher_projects
        ]

        return {"teacher_projects": project_data}

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error retrieving teacher project data.")

@app.get("/student-projects/{teacher_id}")
def get_student_projects_by_teacher_id(
    teacher_id: str,
    db: Session = Depends(get_db)
):
    try:
        # Query the StudentProjects table to fetch project links for the given teacher_id
        student_projects = db.query(StudentProjects.stu_pro_id, StudentProjects.project_link) \
                             .filter(StudentProjects.teacher_id == teacher_id).all()

        if not student_projects:
            raise HTTPException(status_code=404, detail="No student projects found for the teacher.")

        # Prepare the response data
        student_project_data = [
            {
                "student_project_id": project.stu_pro_id,
                "project_link": project.project_link
            }
            for project in student_projects
        ]

        return {"student_projects": student_project_data}

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error retrieving student project data.")

#
# TSC API Endpoints
#

@app.get("/tsc-summary/{user_id}", response_model=dict)
def get_tsc_summary(user_id: str, db: Session = Depends(get_db)):
    try:
        # Fetch TSC details for the user
        tsc = db.query(Tsc).filter(Tsc.users_id == user_id).first()
        if not tsc:
            raise HTTPException(status_code=404, detail="TSC details not found.")

        # Count number of teachers associated with the TSC via school_tsc_mapping
        num_teachers = (
            db.query(func.count(Teacher.teacher_id.distinct()))
            .join(SchoolTscMapping, SchoolTscMapping.school_id == Teacher.school_id)
            .filter(SchoolTscMapping.tsc_id == tsc.tsc_id)
            .scalar()
        )

        # Count total number of students associated with the TSC
        total_students = (
            db.query(func.sum(Teacher.number_of_students))
            .join(SchoolTscMapping, SchoolTscMapping.school_id == Teacher.school_id)
            .filter(SchoolTscMapping.tsc_id == tsc.tsc_id)
            .scalar()
        ) or 0

        # Count total evaluated projects (teachers + students)
        total_evaluated = (
            db.query(func.count(TeachersProjects.tea_pro_id))
            .join(Teacher, TeachersProjects.teacher_id == Teacher.teacher_id)
            .join(SchoolTscMapping, SchoolTscMapping.school_id == Teacher.school_id)
            .filter(SchoolTscMapping.tsc_id == tsc.tsc_id, TeachersProjects.status != "pending")
            .scalar()
            +
            db.query(func.count(StudentProjects.stu_pro_id))
            .join(Teacher, StudentProjects.teacher_id == Teacher.teacher_id)
            .join(SchoolTscMapping, SchoolTscMapping.school_id == Teacher.school_id)
            .filter(SchoolTscMapping.tsc_id == tsc.tsc_id, StudentProjects.status != "pending")
            .scalar()
        )

        # Count total pending projects (teachers + students)
        total_pending = (
            db.query(func.count(TeachersProjects.tea_pro_id))
            .join(Teacher, TeachersProjects.teacher_id == Teacher.teacher_id)
            .join(SchoolTscMapping, SchoolTscMapping.school_id == Teacher.school_id)
            .filter(SchoolTscMapping.tsc_id == tsc.tsc_id, TeachersProjects.status == "pending")
            .scalar()
            +
            db.query(func.count(StudentProjects.stu_pro_id))
            .join(Teacher, StudentProjects.teacher_id == Teacher.teacher_id)
            .join(SchoolTscMapping, SchoolTscMapping.school_id == Teacher.school_id)
            .filter(SchoolTscMapping.tsc_id == tsc.tsc_id, StudentProjects.status == "pending")
            .scalar()
        )

        # Get the details of the teachers associated with this TSC
        teachers_assigned = db.query(Teacher).join(SchoolTscMapping, SchoolTscMapping.school_id == Teacher.school_id).filter(SchoolTscMapping.tsc_id == tsc.tsc_id).all()

        teacher_details = []
        for teacher in teachers_assigned:
            # Fetch the most recent project upload time for the teacher from both TeachersProjects and StudentProjects
            latest_teacher_project = db.query(func.max(TeachersProjects.created_at)).filter(TeachersProjects.teacher_id == teacher.teacher_id).scalar()
            latest_student_project = db.query(func.max(StudentProjects.created_at)).filter(StudentProjects.teacher_id == teacher.teacher_id).scalar()

            # Get the maximum of the two (latest project upload time)
            last_updated = max(latest_teacher_project or datetime.min, latest_student_project or datetime.min)

            # Fallback to teacher's created_at if no projects exist
            last_updated = last_updated if last_updated != datetime.min else teacher.created_at

            # Append teacher details inside the loop
            teacher_details.append({
                "teacher_id": teacher.teacher_id,
                "teacher_name": teacher.teacher_name,
                "contact_number": teacher.ph_no,
                "email_id": teacher.email,
                "last_updated": last_updated.strftime('%Y-%m-%d %H:%M:%S')
            })

        # Construct response
        response = {
            "tsc_id": tsc.tsc_id,
            "tsc_name": tsc.tsc_name,
            "ph_no": tsc.ph_no,
            "email": tsc.email,
            "created_at": tsc.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "num_teachers": num_teachers,
            "total_students": total_students,
            "total_evaluated": total_evaluated,
            "total_pending": total_pending,
            "teachers": teacher_details,
        }

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.get("/tsc-schools/{tsc_id}", response_model=dict)
def get_schools_assigned_to_tsc(tsc_id: str, db: Session = Depends(get_db)):
    try:
        # Fetch the TSC details based on the tsc_id
        tsc = db.query(Tsc).filter(Tsc.tsc_id == tsc_id).first()
        if not tsc:
            raise HTTPException(status_code=404, detail="TSC not found.")

        # Fetch the schools associated with this TSC
        schools = db.query(School).join(SchoolTscMapping, SchoolTscMapping.school_id == School.school_id) \
            .filter(SchoolTscMapping.tsc_id == tsc_id).all()

        # Prepare the list of school details to return
        school_details = [{
            "schoo_id":school.school_id,
            "school_name": school.school_name,
            "contact": school.ph_no,
            "address": school.addr,
            "tsc_name": tsc.tsc_name,
            "email_id": school.email
        } for school in schools]

        # Construct response
        response = {
            "tsc_id": tsc.tsc_id,
            "tsc_name": tsc.tsc_name,
            "schools": school_details
        }

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.get("/school-teachers-tsc/{school_id}")
def get_teachers_by_school(
    school_id: str,
    db: Session = Depends(get_db)
):
    try:
        # Query the Teacher table based on the school_id and join with the School table
        teachers = db.query(
            Teacher.teacher_id,
            Teacher.teacher_name,
            Teacher.email,
            Teacher.ph_no,
            Teacher.number_of_students,
            Teacher.gender,
            School.addr.label('school_address'),
            School.ph_no.label('school_contact_no'),
            School.school_name
        ) \
        .join(School, School.school_id == Teacher.school_id) \
        .filter(Teacher.school_id == school_id).all()

        # Prepare the response data
        teacher_data = [
            {
                "teacher_id": teacher.teacher_id,
                "teacher_name": teacher.teacher_name,
                "email": teacher.email,
                "contact_no": teacher.ph_no,
                "school_address": teacher.school_address,
                "school_name": teacher.school_name,
                "school_contact_no": teacher.school_contact_no,
                "gender": teacher.gender,
                "number_of_students": teacher.number_of_students
            }
            for teacher in teachers
        ]

        return {"teachers": teacher_data}

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error retrieving teacher data.")

@app.post("/teacher-project/{teacher_project_id}/score/{user_id}")
def post_teacher_project_score(
    teacher_project_id: str,
    user_id: str,
    score: TeachersScoreCreate,
    db: Session = Depends(get_db)
):
    # Fetch the teacher project by teacher_project_id
    teacher_project = db.query(TeachersProjects).filter(TeachersProjects.tea_pro_id == teacher_project_id).first()
    if not teacher_project:
        raise HTTPException(status_code=404, detail="Teacher project not found")

    # Fetch the teacher details from the teacher table using the teacher_id from teacher_project
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_project.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # Fetch the TSC (evaluating user) from the tsc table using user_id
    tsc = db.query(Tsc).filter(Tsc.users_id == user_id).first()
    if not tsc:
        raise HTTPException(status_code=404, detail="TSC user not found")

    # Update the status of the teacher project to "completed" first
    teacher_project.status = "completed"
    db.commit()

    # Check if a score already exists for this teacher project
    existing_score = db.query(TeachersScore).filter(TeachersScore.tea_pro_id == teacher_project_id).first()
    if existing_score:
        raise HTTPException(status_code=400, detail="Score already exists for this teacher project")

    # Generate a new score ID
    tea_sc_id = str(uuid4())

    # Create a new TeachersScore entry
    new_score = TeachersScore(
        tea_sc_id=tea_sc_id,
        tea_pro_id=teacher_project.tea_pro_id,
        creativity=score.creativity,
        code_complexity=score.code_complexity,
        originality_of_code=score.originality_of_code,
        usage_of_spr_bd=score.usage_of_spr_bd,
        animations_sounds=score.animations_sounds,
        total=score.total,
        feedback=score.feedback,
        evaluated_by=user_id,
        tsc_id=tsc.tsc_id,
    )

    try:
        # Add the score to the database and commit
        db.add(new_score)
        db.commit()
        db.refresh(new_score)
    except Exception as e:
        # Handle any exception (e.g., validation error) by rolling back changes
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    # Return the created score record as response
    return {"message": "Score successfully created and teacher project marked as completed", "status": "success"}

@app.post("/student-project/{student_project_id}/score/{user_id}")
def post_student_project_score(
    student_project_id: str,
    user_id: str,
    score: StudentsScoreCreate,
    db: Session = Depends(get_db)
):
    # Fetch the student project by student_project_id
    student_project = db.query(StudentProjects).filter(StudentProjects.stu_pro_id == student_project_id).first()
    if not student_project:
        raise HTTPException(status_code=404, detail="Student project not found")

    # Fetch the teacher details from the teacher table using the teacher_id from student_project
    teacher = db.query(Teacher).filter(Teacher.teacher_id == student_project.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # Fetch the TSC (evaluating user) from the tsc table using user_id
    tsc = db.query(Tsc).filter(Tsc.users_id == user_id).first()
    if not tsc:
        raise HTTPException(status_code=404, detail="TSC user not found")

    # Check if a score already exists for this student project
    existing_score = db.query(StudentsScore).filter(StudentsScore.stu_pro_id == student_project_id).first()
    if existing_score:
        raise HTTPException(status_code=400, detail="Score already exists for this student project")

    # Generate a new score ID
    st_sc_id = str(uuid4())

    # Create a new StudentsScore entry
    new_score = StudentsScore(
        st_sc_id=st_sc_id,
        stu_pro_id=student_project.stu_pro_id,
        creativity=score.creativity,
        code_complexity=score.code_complexity,
        originality_of_code=score.originality_of_code,
        usage_of_spr_bd=score.usage_of_spr_bd,
        animations_sounds=score.animations_sounds,
        total=score.total,
        feedback=score.feedback,
        evaluated_by=user_id,
        tsc_id=tsc.tsc_id,
    )

    student_project.status = "completed"

    try:

        db.add(new_score)

        db.commit()

        db.refresh(new_score)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create score: {str(e)}")

    # Return the created score record as response
    return {"message": "Score successfully created", "status": "success"}



@app.patch("/teacher-project/{teacher_project_id}/score/{user_id}")
def patch_teacher_project_score(
    teacher_project_id: str,
    user_id: str,
    score: TeachersScoreCreate,
    db: Session = Depends(get_db)
):
    # Fetch the teacher project by teacher_project_id
    teacher_project = db.query(TeachersProjects).filter(TeachersProjects.tea_pro_id == teacher_project_id).first()
    if not teacher_project:
        raise HTTPException(status_code=404, detail="Teacher project not found")

    # Fetch the teacher details from the teacher table using the teacher_id from teacher_project
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_project.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # Fetch the TSC (evaluating user) from the tsc table using user_id
    tsc = db.query(Tsc).filter(Tsc.users_id == user_id).first()
    if not tsc:
        raise HTTPException(status_code=404, detail="TSC user not found")

    # Fetch the existing score for this teacher project
    existing_score = db.query(TeachersScore).filter(TeachersScore.tea_pro_id == teacher_project_id).first()
    if not existing_score:
        raise HTTPException(status_code=404, detail="Score not found for this teacher project")

    # Update only the fields that are provided in the request
    if score.creativity is not None:
        existing_score.creativity = score.creativity
    if score.code_complexity is not None:
        existing_score.code_complexity = score.code_complexity
    if score.originality_of_code is not None:
        existing_score.originality_of_code = score.originality_of_code
    if score.usage_of_spr_bd is not None:
        existing_score.usage_of_spr_bd = score.usage_of_spr_bd
    if score.animations_sounds is not None:
        existing_score.animations_sounds = score.animations_sounds
    if score.total is not None:
        existing_score.total = score.total
    if score.feedback is not None:
        existing_score.feedback = score.feedback
    if score.evaluated_by is not None:
        existing_score.evaluated_by = score.evaluated_by

    db.commit()
    db.refresh(existing_score)

    # Return the updated score record
    return {"message": "Score successfully updated", "status": "success"}

@app.patch("/student-project/{student_project_id}/score/{user_id}")
def patch_student_project_score(
    student_project_id: str,
    user_id: str,
    score: StudentsScoreCreate,
    db: Session = Depends(get_db)
):
    # Fetch the student project by student_project_id
    student_project = db.query(StudentProjects).filter(StudentProjects.stu_pro_id == student_project_id).first()
    if not student_project:
        raise HTTPException(status_code=404, detail="Student project not found")

    # Fetch the teacher details from the teacher table using the teacher_id from student_project
    teacher = db.query(Teacher).filter(Teacher.teacher_id == student_project.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # Fetch the TSC (evaluating user) from the tsc table using user_id
    tsc = db.query(Tsc).filter(Tsc.users_id == user_id).first()
    if not tsc:
        raise HTTPException(status_code=404, detail="TSC user not found")

    # Fetch the existing score for this student project
    existing_score = db.query(StudentsScore).filter(StudentsScore.stu_pro_id == student_project_id).first()
    if not existing_score:
        raise HTTPException(status_code=404, detail="Score not found for this student project")

    # Update only the fields that are provided in the request body
    if score.creativity is not None:
        existing_score.creativity = score.creativity
    if score.code_complexity is not None:
        existing_score.code_complexity = score.code_complexity
    if score.originality_of_code is not None:
        existing_score.originality_of_code = score.originality_of_code
    if score.usage_of_spr_bd is not None:
        existing_score.usage_of_spr_bd = score.usage_of_spr_bd
    if score.animations_sounds is not None:
        existing_score.animations_sounds = score.animations_sounds
    if score.total is not None:
        existing_score.total = score.total
    if score.feedback is not None:
        existing_score.feedback = score.feedback
    if score.evaluated_by is not None:
        existing_score.evaluated_by = score.evaluated_by
    # Commit the changes to the database
    db.commit()
    db.refresh(existing_score)
    # Return the updated score record
    return {"message": "Score successfully updated", "status": "success"}

@app.get("/organization-by-tsc/{tsc_id}")
def get_organization_by_tsc(tsc_id: str, db: Session = Depends(get_db)):
    """Fetches the organization by TSC ID."""
    try:
        # Query the organization by tsc_id by finding the related school and then the organization
        school = db.query(School).join(School.school_tsc_mappings).filter(SchoolTscMapping.tsc_id == tsc_id).first()

        if not school:
            raise HTTPException(status_code=404, detail=f"No school found for TSC ID {tsc_id}.")

        organization = school.organization

        if not organization:
            raise HTTPException(status_code=404, detail=f"No organization found for TSC ID {tsc_id}.")

        # Convert the organization data to a dictionary
        organization_data = {
            "organization_id": organization.organization_id,
            "organization_name": organization.organization_name,
            "contact_person": organization.contact_person,
            "email": organization.email,
            "ph_no": organization.ph_no,
            "address": organization.address,
            "created_at": organization.created_at,
            "created_by": organization.created_by
        }

        # Return the organization data
        return {"organization": organization_data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching organization: {e}")

@app.get("/tscs")
def get_all_tscs(db: Session = Depends(get_db)):
    """Fetches all TSCs, including the schools each handles."""
    try:
        # Query the TSC table and fetch all records
        tscs = db.query(Tsc).all()

        # Prepare the response data
        tsc_data = []
        for tsc in tscs:
            # Get the schools handled by this TSC
            school_mappings = db.query(SchoolTscMapping).filter(SchoolTscMapping.tsc_id == tsc.tsc_id).all()

            # Extract school names from the mappings, check if the school exists before accessing school_name
            school_names = []
            for mapping in school_mappings:
                school = db.query(School).filter(School.school_id == mapping.school_id).first()
                if school:  # Ensure the school exists before accessing the school_name attribute
                    school_names.append(school.school_name)
                else:
                    # Optionally, log or handle the case where no school is found
                    school_names.append("Unknown School")

            tsc_data.append({
                "tsc_id": tsc.tsc_id,
                "tsc_name": tsc.tsc_name,
                "email": tsc.email,
                "phone_number": tsc.ph_no,
                "gender": tsc.gender,
                "created_by": tsc.created_by,
                "created_at": tsc.created_at.strftime('%Y-%m-%d %H:%M:%S') if tsc.created_at else None,
                "schools_handled": school_names
            })

        return {"tscs": tsc_data}

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error retrieving TSC data.")
@app.get("/tsc/{tsc_id}")
def get_tsc_by_id(tsc_id: str, db: Session = Depends(get_db)):
    """Fetches a specific TSC by tsc_id, along with schools it handles."""
    try:
        # Query the TSC table and filter by tsc_id
        tsc = db.query(Tsc).filter(Tsc.tsc_id == tsc_id).first()

        # If no TSC is found, return a 404 error
        if not tsc:
            raise HTTPException(status_code=404, detail="TSC not found")

        # Get the schools handled by this TSC through the SchoolTscMapping
        school_mappings = db.query(SchoolTscMapping).filter(SchoolTscMapping.tsc_id == tsc_id).all()

        # Extract the school names from the mappings
        school_names = [db.query(School).filter(School.school_id == mapping.school_id).first().school_name
                        for mapping in school_mappings]

        # Prepare the response data
        tsc_data = {
            "tsc_id": tsc.tsc_id,
            "tsc_name": tsc.tsc_name,
            "email": tsc.email,
            "phone_number": tsc.ph_no,
            "gender": tsc.gender,
            "created_by": tsc.created_by,
            "created_at": tsc.created_at.strftime('%Y-%m-%d %H:%M:%S') if tsc.created_at else None,
            "schools_handled": school_names
        }

        return {"tsc": tsc_data}

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error retrieving TSC data.")
@app.post("/add-tsc/{users_id}")
def add_tsc(
    users_id: str,
    name: str,
    email: str,
    phone_number: str,
    school_id: str,
    gender: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Creates a TSC user in Firebase, inserts user details into MySQL,
       and links the TSC to a school in the school_tsc_mapping table."""

    firebase_uid = None
    generated_password = None
    try:
        # Step 1: Generate a random password (e.g., 12 characters long)
        generated_password = generate_random_password()
        # Step 2: Create a user in Firebase Authentication
        user = auth.create_user(email=email, password=generated_password)
        firebase_uid = user.uid

        # Step 3: Create User record in MySQL using SQLAlchemy
        new_user = User(users_id=firebase_uid, email=email, role="tsc")
        db.add(new_user)
        db.commit()

        # Step 4: Insert into TSC table
        tsc_id = str(uuid.uuid4())  # Generate UUID for tsc_id
        new_tsc = Tsc(tsc_id=tsc_id, users_id=firebase_uid, tsc_name=name, email=email, ph_no=phone_number, gender=gender, created_by=users_id)
        db.add(new_tsc)
        db.commit()

        # The mapping_id will be auto-generated (UUID)
        mapping_id = str(uuid.uuid4())
        new_mapping = SchoolTscMapping(
            mapping_id=mapping_id,
            school_id=school_id,
            tsc_id=tsc_id
        )

        db.add(new_mapping)
        db.commit()

        # Return success response
        return {"message": "TSC added successfully", "firebase_uid": firebase_uid, "tsc_id": tsc_id}

    except firebase_admin.exceptions.FirebaseError as fb_error:
        if firebase_uid:
            try:
                # Delete Firebase user if MySQL insert fails
                auth.delete_user(firebase_uid)
            except Exception as delete_error:
                raise HTTPException(status_code=500, detail=f"Firebase Error: Could not delete user after DB error: {delete_error}")
        raise HTTPException(status_code=500, detail=f"Firebase Error: {fb_error}")

    except SQLAlchemyError as db_error:
        db.rollback()
        if firebase_uid:
            try:
                # Delete Firebase user if MySQL insert fails
                auth.delete_user(firebase_uid)
            except Exception as delete_error:
                raise HTTPException(status_code=500, detail=f"Firebase Error: Could not delete user after DB error: {delete_error}")
        raise HTTPException(status_code=500, detail=f"Database Error: {db_error}")

    except Exception as e:
        db.rollback()
        if firebase_uid:
            try:
                # Delete Firebase user if any unexpected error occurs
                auth.delete_user(firebase_uid)
            except Exception as delete_error:
                raise HTTPException(status_code=500, detail=f"Error deleting Firebase user: {delete_error}")
        raise HTTPException(status_code=400, detail=f"Error: {e}")
@app.patch("/update-tsc/{tsc_id}")
def update_tsc(
    tsc_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone_number: Optional[str] = None,
    gender: Optional[str] = None,
    school_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        # Fetch the TSC record from DB
        tsc = db.query(Tsc).filter(Tsc.tsc_id == tsc_id).first()

        if not tsc:
            raise HTTPException(status_code=404, detail="TSC not found.")

        # Fetch the associated User record
        user = db.query(User).filter(User.users_id == tsc.users_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        # Update fields in the database if provided
        if name:
            tsc.tsc_name = name
        if email:
            # Update the email in Firebase and Database if provided
            auth.update_user(tsc.users_id, email=email)
            tsc.email = email
            user.email = email

        if phone_number:
            tsc.ph_no = phone_number
        if gender:
            tsc.gender = gender

        if school_id:
            # If school_id is provided, update the mapping in the school_tsc_mapping table
            existing_mapping = db.query(SchoolTscMapping).filter(SchoolTscMapping.tsc_id == tsc_id).first()
            if existing_mapping:
                existing_mapping.school_id = school_id
            else:
                # Create a new mapping if not exists
                new_mapping = SchoolTscMapping(
                    mapping_id=str(uuid.uuid4()),
                    school_id=school_id,
                    tsc_id=tsc_id
                )
                db.add(new_mapping)

        # Commit the transaction after all updates are done
        db.commit()

        return {"message": "TSC details and associated User email updated successfully", "tsc_id": tsc_id}

    except firebase_admin.exceptions.FirebaseError as fb_error:
        raise HTTPException(status_code=500, detail=f"Firebase Error: {fb_error}")

    except Exception as e:
        db.rollback()  # Rollback in case of any error
        raise HTTPException(status_code=500, detail=f"Error updating TSC details: {e}")
@app.delete("/delete-tsc-by-user/{tsc_id}")
def delete_tsc_by_tsc_id(tsc_id: str, db: Session = Depends(get_db)):
    try:
        # Fetch the TSC record by tsc_id
        tsc = db.query(Tsc).filter(Tsc.tsc_id == tsc_id).first()

        if not tsc:
            raise HTTPException(status_code=404, detail="TSC not found.")

        # Fetch the associated User record
        user = db.query(User).filter(User.users_id == tsc.users_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        # Delete the associated school_tsc_mapping records based on tsc_id
        mappings = db.query(SchoolTscMapping).filter(SchoolTscMapping.tsc_id == tsc.tsc_id).all()

        for mapping in mappings:
            db.delete(mapping)

        # Delete the user from Firebase
        auth.delete_user(user.users_id)

        # Delete the TSC record from the database
        db.delete(tsc)

        # Delete the associated User record from the database
        db.delete(user)

        # Commit the transaction after all deletions
        db.commit()

        return {"message": "TSC and associated User deleted successfully from both Firebase and Database", "tsc_id": tsc.tsc_id}

    except firebase_admin.exceptions.FirebaseError as fb_error:
        db.rollback()  # Rollback transaction if Firebase error occurs
        raise HTTPException(status_code=500, detail=f"Firebase Error: {fb_error}")

    except Exception as e:
        db.rollback()  # Rollback transaction in case of any other error
        raise HTTPException(status_code=500, detail=f"Error deleting TSC: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
