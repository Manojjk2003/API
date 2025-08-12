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
        raise HTTPException(status_code=500, detail="Internal Server Error")# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Endpoint to fetch user details by uid
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
