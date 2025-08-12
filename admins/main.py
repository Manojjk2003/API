from models import *

# Ensure the correct path is retrieved from the environment variable
cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')  
print(f"Credentials Path: {cred_path}")  

# Check if the credentials file exists at the specified path
if not cred_path or not os.path.isfile(cred_path):
    raise ValueError("Firebase credentials file not found at the specified path.")

# Initialize Firebase app if it's not already initialized
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

# Now you can access Firestore after initializing Firebase app
db_firestore = firestore.client()

# Define the TeachersScoreCreate schema with optional fields
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

# Define the StudentsScoreCreate schema with optional fields
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

@app.get("/dashboard/{teacher_id}", response_model=DashboardResponse)
async def get_teacher_dashboard(teacher_id: str, db: Session = Depends(get_db)):
    # Step 1: Fetch teacher details based on teacher_id
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found for the given teacher_id")

    teacher_name = teacher.teacher_name
    user_id = teacher.users_id
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
        user_id=user_id,
        num_teacher_projects=num_teacher_projects,
        num_student_projects=num_student_projects,
        distinct_grades=classes,
        total_students=total_students,  
        teacher_project_links=teacher_project_links,
        student_project_links=student_project_links
    )


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




# POST: Create Teacher Project Score
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
    
  # Fetch the evaluator (user_id) from the User table
    user = db.query(User).filter(User.users_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
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
    return {
        "message": "Score successfully created and teacher project marked as completed",
        "status": "success",
        "teacher_project_id": teacher_project_id,
        "score_id": tea_sc_id
    }

# POST: Create Student Project Score
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
    
    # Fetch the evaluator (user_id) from the User table
    user = db.query(User).filter(User.users_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
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
         
    )

    student_project.status = "completed" 
    
    try:
        
        db.add(new_score)
      
        db.commit()
        
        db.refresh(new_score)
    except Exception as e:        
        db.rollback()        
        raise HTTPException(status_code=500, detail=f"Failed to create score: {str(e)}")

    
    return {
        "message": "Score successfully created",
        "status": "success",
        "student_project_id": student_project_id,
        "score_id": st_sc_id
    }



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
    
   # Fetch the evaluator (user_id) from the User table
    user = db.query(User).filter(User.users_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
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

    # Commit the changes to the database
    db.commit()
    db.refresh(existing_score)

    # Return the updated score record
    return {"message": "Score successfully updated", "status": "success"}

# Define the student project PATCH endpoint
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
    
  # Fetch the evaluator (user_id) from the User table
    user = db.query(User).filter(User.users_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
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
    
    db.commit()
    db.refresh(existing_score)
    # Return the updated score record
    return {"message": "Score successfully updated", "status": "success"}


@app.get("/organizations")
def get_all_organizations(db: Session = Depends(get_db)):
    """Fetches all organizations with their id and name."""
    try:
        # Query all organizations from the database
        organizations = db.query(Organization.organization_id, Organization.organization_name).all()
        
        if not organizations:
            raise HTTPException(status_code=404, detail="No organizations found.")
        
        # Convert the result to a list of dictionaries
        organizations_list = [{"organization_id": org_id, "organization_name": org_name} for org_id, org_name in organizations]
        
        # Return the list of organizations
        return {"organizations": organizations_list}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching organizations: {e}")

@app.get("/schools/{organization_id}")
def get_schools_by_organization(organization_id: str, db: Session = Depends(get_db)):
    """Fetches all school data by organization ID."""
    try:
        # Query all school data by organization_id from the database
        schools = db.query(School).filter(School.organization_id == organization_id).all()
        
        if not schools:
            raise HTTPException(status_code=404, detail=f"No schools found for organization with ID {organization_id}.")
        
        # Convert the result to a list of dictionaries with all school data
        schools_list = [
            {
                "school_id": school.school_id,
                "school_name": school.school_name,
                "email": school.email,
                "ph_no": school.ph_no,
                "addr": school.addr,
                "created_at": school.created_at,
                "organization_id": school.organization_id,
                "created_by": school.created_by
            }
            for school in schools
        ]
        
        # Return the list of schools
        return {"schools": schools_list}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching schools: {e}")


@app.post("/add-school/{users_id}")
def add_school(
    users_id: str,
    school_name: str, 
    email: str, 
    ph_no: str, 
    addr: str, 
    organization_id: str, 
    db: Session = Depends(get_db)
):
    try:
        # Check if the organization_id exists in the 'organization' table
        organization = db.query(Organization).filter(Organization.organization_id == organization_id).first()

        if not organization:
            raise HTTPException(status_code=400, detail="Organization not found.")

        # Check if the email already exists in the 'school' table
        existing_school = db.query(School).filter(School.email == email).first()
        if existing_school:
            raise HTTPException(status_code=400, detail="School with this email already exists.")
        
        school_id = str(uuid.uuid4())
        
        # Create a new School instance
        new_school = School(
            school_id=school_id,
            school_name=school_name,
            email=email,
            ph_no=ph_no,
            addr=addr,
            organization_id=organization_id,
            created_by=users_id
        )
        
        # Add the new school to the database
        db.add(new_school)
        db.commit()
        db.refresh(new_school)
        
        return {"message": "School added successfully.", "school_id": new_school.school_id}

    except Exception as e:
        db.rollback()  # Rollback in case of any error
        raise HTTPException(status_code=500, detail=f"Error adding school: {e}")
    
@app.patch("/update-school/{school_id}")
def update_school(
    school_id: str, 
    school_name: Optional[str] = None, 
    email: Optional[str] = None, 
    ph_no: Optional[str] = None, 
    addr: Optional[str] = None,
    organization_id: Optional[str] = None,  
    db: Session = Depends(get_db)
):
    try:
        # Fetch the school record from DB
        school = db.query(School).filter(School.school_id == school_id).first()

        if not school:
            raise HTTPException(status_code=404, detail="School not found.")
        
        # If organization_id is provided, validate it exists
        if organization_id:
            organization = db.query(Organization).filter(Organization.organization_id == organization_id).first()
            if not organization:
                raise HTTPException(status_code=400, detail="Organization with this ID does not exist.")
            school.organization_id = organization_id

        # Update fields in the database if provided
        if school_name:
            school.school_name = school_name
        if email:
            # Ensure no other school has the same email
            existing_school = db.query(School).filter(School.email == email).first()
            if existing_school:
                raise HTTPException(status_code=400, detail="School with this email already exists.")
            school.email = email
        if ph_no:
            school.ph_no = ph_no
        if addr:
            school.addr = addr
        
        # Commit the transaction after all updates are done
        db.commit()

        return {"message": "School details updated successfully", "school_id": school_id}
    
    except Exception as e:
        db.rollback()  
        raise HTTPException(status_code=500, detail=f"Error updating school details: {e}")


@app.delete("/delete-school/{school_id}")
def delete_school(school_id: str, db: Session = Depends(get_db)):
    try:
        # Fetch the school record from DB
        school = db.query(School).filter(School.school_id == school_id).first()

        if not school:
            raise HTTPException(status_code=404, detail="School not found.")
        
        # Delete the school
        db.delete(school)
        db.commit()

        return {"message": f"School {school_id} deleted successfully"}
    
    except Exception as e:
        db.rollback()  
        raise HTTPException(status_code=500, detail=f"Error deleting school: {e}")
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
    
 
# @app.get("/available_sections/{teacher_id}")
# def get_available_sections(teacher_id: str, db: Session = Depends(get_db)):
#     results = (
#         db.query(SessionStudentsDetails.grade, SessionStudentsDetails.section)
#         .join(StudentProjects, StudentProjects.se_st_det_id == SessionStudentsDetails.se_st_det_id)
#         .filter(StudentProjects.teacher_id == teacher_id)
#         .distinct()
#         .all()
#     )
    
#     formatted_sections = [f"{grade} {sec}" for grade, sec in results]
#     return {"sections": formatted_sections}


# @app.get("/report_by_grade_section/{teacher_id}")
# def get_report_by_grade_section(
#     teacher_id: str,
#     grade: str = Query(..., description="Grade"),
#     section: str = Query(..., description="Section"),
#     db: Session = Depends(get_db)
# ):
#     try:
#         # Join Teacher and School to fetch all info
#         teacher = (
#             db.query(
#                 Teacher.teacher_id,
#                 Teacher.teacher_name,
#                 Teacher.classes,
#                 Teacher.number_of_students,
#                 School.school_name
#             )
#             .join(School, Teacher.school_id == School.school_id)
#             .filter(Teacher.teacher_id == teacher_id)
#             .first()
#         )

#         if not teacher:
#             raise HTTPException(status_code=404, detail="Teacher not found")

#         # Filter student projects by teacher, grade and section
#         student_projects = (
#             db.query(StudentProjects)
#             .join(SessionStudentsDetails, StudentProjects.se_st_det_id == SessionStudentsDetails.se_st_det_id)
#             .filter(
#                 StudentProjects.teacher_id == teacher_id,
#                 SessionStudentsDetails.grade == grade,
#                 SessionStudentsDetails.section == section
#             )
#             .all()
#         )

#         total_score = sum([proj.total for proj in student_projects if proj.total is not None])
#         total_evaluated = len([proj for proj in student_projects if proj.total is not None])

#         def average(criteria: str):
#             values = [getattr(proj, criteria) for proj in student_projects if getattr(proj, criteria) is not None]
#             return round(sum(values) / len(values), 2) if values else 0

#         return {
#             "teacher_id": teacher.teacher_id,
#             "teacher_name": teacher.teacher_name,
#             "school_name": teacher.school_name,
#             "grade": grade,
#             "section": section,
#             "number_of_students": teacher.number_of_students,
#             "total_student_projects": len(student_projects),
#             "total_score": total_score,
#             "evaluated_projects": total_evaluated,
#             "live_average_score": round(total_score / total_evaluated, 2) if total_evaluated else 0,
#             "average_criteria_scores": {
#                 "creativity": average("creativity"),
#                 "code_complexity": average("code_complexity"),
#                 "originality_of_code": average("originality_of_code"),
#                 "usage_of_spr_bd": average("usage_of_spr_bd"),
#                 "animations_sounds": average("animations_sounds")
#             }
#         }

#     except SQLAlchemyError:
#         raise HTTPException(status_code=500, detail="Database error occurred")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @app.get("/school-report/{school_id}")
# def get_school_report(school_id: str, db: Session = Depends(get_db)):
#     """
#     Generates a detailed report of a school including:
#     - School info
#     - Organization info
#     - Number of teachers
#     - Number of students
#     - Teacher names
#     """
#     try:
#         # Step 1: Get school, org info, and teacher count
#         school = db.query(
#             School.school_id,
#             School.school_name,
#             School.addr,
#             School.email,
#             School.ph_no,
#             Organization.organization_id,
#             Organization.organization_name,
#             func.count(Teacher.teacher_id).label("teacher_count"),
#             func.coalesce(func.sum(Teacher.number_of_students), 0).label("total_students")
#         ) \
#         .outerjoin(Teacher, Teacher.school_id == School.school_id) \
#         .join(Organization, Organization.organization_id == School.organization_id) \
#         .filter(School.school_id == school_id) \
#         .group_by(School.school_id, Organization.organization_id, Organization.organization_name) \
#         .first()

#         if not school:
#             raise HTTPException(status_code=404, detail="School not found")

#         # Step 2: Get list of teacher names
#         teacher_names = db.query(Teacher.teacher_name) \
#             .filter(Teacher.school_id == school_id).all()

#         teacher_name_list = [t.teacher_name for t in teacher_names]

#         # Final report structure
#         report = {
#             "school_id": school.school_id,
#             "school_name": school.school_name,
#             "organization_id": school.organization_id,
#             "organization_name": school.organization_name,
#             "address": school.addr,
#             "email": school.email,
#             "phone_no": school.ph_no,
#             "no_of_teachers": school.teacher_count,
#             "no_of_students": school.total_students,
#             "teacher_names": teacher_name_list
#         }

#         return {"school_report": report}

#     except SQLAlchemyError as e:
#         raise HTTPException(status_code=500, detail="Error generating school report")

# @app.get("/school_report/{school_id}")
# def generate_school_report(school_id: str, db: Session = Depends(get_db)):
#     try:
#         # 1. Fetch basic school info with organization and teacher count
#         school_info = db.query(
#             School.school_id,
#             School.school_name,
#             School.addr,
#             School.email,
#             School.ph_no,
#             Organization.organization_id,
#             Organization.organization_name,
#             func.count(Teacher.teacher_id).label('no_of_teachers')
#         ).outerjoin(Teacher, Teacher.school_id == School.school_id) \
#          .join(Organization, Organization.organization_id == School.organization_id) \
#          .filter(School.school_id == school_id) \
#          .group_by(School.school_id, Organization.organization_id, Organization.organization_name) \
#          .first()

#         if not school_info:
#             raise HTTPException(status_code=404, detail="School not found")

#         # 2. Get total number of students in the school
#         total_students = db.query(func.coalesce(func.sum(Teacher.number_of_students), 0)) \
#                            .filter(Teacher.school_id == school_id).scalar()

#         # 3. Fetch teachers and their cumulative scores and grades
#         teachers = db.query(Teacher).filter(Teacher.school_id == school_id).all()

#         teacher_details = []
#         grades_set = set()

#         for teacher in teachers:
#             # Collect grades
#             if teacher.classes:
#                 grades_set.update(grade.strip() for grade in teacher.classes.split(","))

#             # Calculate cumulative score
#             teacher_project_score = db.query(func.coalesce(func.sum(TeachersScore.total), 0)) \
#                 .join(TeachersProjects, TeachersScore.tea_pro_id == TeachersProjects.tea_pro_id) \
#                 .filter(TeachersProjects.teacher_id == teacher.teacher_id).scalar()

#             student_project_score = db.query(func.coalesce(func.sum(StudentsScore.total), 0)) \
#                 .join(StudentProjects, StudentsScore.stu_pro_id == StudentProjects.stu_pro_id) \
#                 .filter(StudentProjects.teacher_id == teacher.teacher_id).scalar()

#             cumulative_score = teacher_project_score + student_project_score

#             teacher_details.append({
#                 "teacher_id": teacher.teacher_id,
#                 "teacher_name": teacher.teacher_name,
#                 "email": teacher.email,
#                 "contact_no": teacher.ph_no,
#                 "number_of_students": teacher.number_of_students,
#                 "grades": teacher.classes,
#                 "cumulative_score": cumulative_score
#             })

#         # Final response
#         report = {
#             "school_id": school_info.school_id,
#             "school_name": school_info.school_name,
#             "organization_id": school_info.organization_id,
#             "organization_name": school_info.organization_name,
#             "address": school_info.addr,
#             "email": school_info.email,
#             "contact_no": school_info.ph_no,
#             "no_of_teachers": school_info.no_of_teachers,
#             "no_of_students": total_students,
#             "grades_offered": sorted(grades_set),
#             "teachers": teacher_details
#         }

#         return {"school_report": report}

#     except Exception as e:
#         print(f"Error generating school report: {str(e)}")
#         raise HTTPException(status_code=500, detail="Internal server error while generating school report.")

@app.get("/school_report/{school_id}")
def get_school_report(
    school_id: str = Path(..., description="School ID"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) if end_date else None

        # 1. School Info
        school_info = db.query(
            School.school_id,
            School.school_name,
            School.addr,
            School.email,
            School.ph_no,
            func.count(Teacher.teacher_id).label("no_of_teachers"),
            func.sum(Teacher.number_of_students).label("no_of_students"),
            Organization.organization_name
        ) \
        .outerjoin(Teacher, Teacher.school_id == School.school_id) \
        .join(Organization, Organization.organization_id == School.organization_id) \
        .filter(School.school_id == school_id) \
        .group_by(School.school_id, Organization.organization_name) \
        .first()

        if not school_info:
            raise HTTPException(status_code=404, detail="School not found")

        teachers = db.query(Teacher).filter(Teacher.school_id == school_id).all()

        teacher_list = []
        total_teacher_cumulative_score = 0
        total_teacher_projects = 0
        total_student_projects = 0

        for teacher in teachers:
            # --- TEACHER PROJECTS ---
            teacher_projects_query = db.query(TeachersProjects).filter(TeachersProjects.teacher_id == teacher.teacher_id)
            if start_dt:
                teacher_projects_query = teacher_projects_query.filter(TeachersProjects.created_at >= start_dt)
            if end_dt:
                teacher_projects_query = teacher_projects_query.filter(TeachersProjects.created_at < end_dt)
            teacher_projects = teacher_projects_query.all()

            evaluated_teacher_projects = db.query(TeachersScore) \
                .join(TeachersProjects, TeachersProjects.tea_pro_id == TeachersScore.tea_pro_id) \
                .filter(TeachersProjects.teacher_id == teacher.teacher_id)
            if start_dt:
                evaluated_teacher_projects = evaluated_teacher_projects.filter(TeachersProjects.created_at >= start_dt)
            if end_dt:
                evaluated_teacher_projects = evaluated_teacher_projects.filter(TeachersProjects.created_at < end_dt)
            evaluated_teacher_projects = evaluated_teacher_projects.all()

            teacher_score_total = sum(score.total for score in evaluated_teacher_projects)
            evaluated_teacher_count = len(evaluated_teacher_projects)
            avg_teacher_score = teacher_score_total / evaluated_teacher_count if evaluated_teacher_count > 0 else 0
            pending_teacher_projects = len(teacher_projects) - evaluated_teacher_count

            # --- STUDENT PROJECTS ---
            student_projects_query = db.query(StudentProjects).filter(StudentProjects.teacher_id == teacher.teacher_id)
            if start_dt:
                student_projects_query = student_projects_query.filter(StudentProjects.created_at >= start_dt)
            if end_dt:
                student_projects_query = student_projects_query.filter(StudentProjects.created_at < end_dt)
            student_projects = student_projects_query.all()

            evaluated_student_projects = db.query(StudentsScore) \
                .join(StudentProjects, StudentProjects.stu_pro_id == StudentsScore.stu_pro_id) \
                .filter(StudentProjects.teacher_id == teacher.teacher_id)
            if start_dt:
                evaluated_student_projects = evaluated_student_projects.filter(StudentProjects.created_at >= start_dt)
            if end_dt:
                evaluated_student_projects = evaluated_student_projects.filter(StudentProjects.created_at < end_dt)
            evaluated_student_projects = evaluated_student_projects.all()

            student_score_total = sum(score.total for score in evaluated_student_projects)
            evaluated_student_count = len(evaluated_student_projects)
            avg_student_score = student_score_total / evaluated_student_count if evaluated_student_count > 0 else 0
            pending_student_projects = len(student_projects) - evaluated_student_count

            cumulative_score = teacher_score_total + student_score_total
            total_teacher_cumulative_score += cumulative_score
            total_teacher_projects += len(teacher_projects)
            total_student_projects += len(student_projects)

            teacher_list.append({
                "teacher_id": teacher.teacher_id,
                "teacher_name": teacher.teacher_name,
                "classes": teacher.classes,
                "number_of_students": teacher.number_of_students,
                "avg_teacher_score": round(avg_teacher_score, 2),
                "avg_student_score": round(avg_student_score, 2),
                "cumulative_score": round(cumulative_score, 2),
                "teacher_project_count": len(teacher_projects),
                "teacher_evaluated_projects": evaluated_teacher_count,
                "teacher_pending_projects": pending_teacher_projects,
                "student_project_count": len(student_projects),
                "student_evaluated_projects": evaluated_student_count,
                "student_pending_projects": pending_student_projects
            })

        # --- STUDENT CUMULATIVE SCORE FOR SCHOOL ---
        student_cumulative_score_query = db.query(func.coalesce(func.sum(StudentsScore.total), 0)) \
            .join(StudentProjects, StudentsScore.stu_pro_id == StudentProjects.stu_pro_id) \
            .join(Teacher, Teacher.teacher_id == StudentProjects.teacher_id) \
            .filter(Teacher.school_id == school_id)
        if start_dt:
            student_cumulative_score_query = student_cumulative_score_query.filter(StudentProjects.created_at >= start_dt)
        if end_dt:
            student_cumulative_score_query = student_cumulative_score_query.filter(StudentProjects.created_at < end_dt)
        student_cumulative_score = student_cumulative_score_query.scalar()

        return {
            "school_id": school_info.school_id,
            "school_name": school_info.school_name,
            "organization_name": school_info.organization_name,
            "address": school_info.addr,
            "email": school_info.email,
            "contact_no": school_info.ph_no,
            "no_of_teachers": school_info.no_of_teachers,
            "no_of_students": school_info.no_of_students,
             "total_teacher_projects": total_teacher_projects,
            "total_student_projects": total_student_projects,
            "teacher_details": teacher_list,
             "filter_start_date": start_date,
            "filter_end_date": end_date,
            # "total_teacher_cumulative_score": round(total_teacher_cumulative_score, 2),
            # "student_cumulative_score": round(student_cumulative_score, 2)
        }

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail="Error generating school report")

@app.get("/best_teacher")
async def get_best_teacher(db: Session = Depends(get_db)):
    # Step 1: Join TeachersProjects and TeachersScore, group by teacher, sum total scores
    best_teacher_score = (
        db.query(
            TeachersProjects.teacher_id,
            func.sum(TeachersScore.total).label("cumulative_score")
        )
        .join(TeachersScore, TeachersProjects.tea_pro_id == TeachersScore.tea_pro_id)
        .group_by(TeachersProjects.teacher_id)
        .order_by(func.sum(TeachersScore.total).desc())
        .first()
    )

    if not best_teacher_score:
        raise HTTPException(status_code=404, detail="No teacher scores found")

    # Step 2: Get teacher details
    teacher = db.query(Teacher).filter(Teacher.teacher_id == best_teacher_score.teacher_id).first()

    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # Step 3: Get school and organization (optional enrichment)
    school = db.query(School).filter(School.school_id == teacher.school_id).first()
    organization = db.query(Organization).filter(Organization.organization_id == school.organization_id).first() if school else None

    return {
        "teacher_id": teacher.teacher_id,
        "teacher_name": teacher.teacher_name,
        "school_name": school.school_name if school else "Unknown School",
        "organization_name": organization.organization_name if organization else "Unknown Organization",
        "cumulative_score": float(best_teacher_score.cumulative_score)
    }


@app.get("/most_improved_teacher")
def get_most_improved_teacher(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        # Parse dates
        if start_date and end_date:
            current_start = datetime.strptime(start_date, "%Y-%m-%d")
            current_end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)  # inclusive end

            # Calculate previous period (same duration just before current_start)
            period_length = current_end - current_start
            previous_end = current_start
            previous_start = previous_end - period_length

            # 1. Get total scores per teacher in previous period
            previous_scores = (
                db.query(
                    TeachersProjects.teacher_id,
                    func.sum(TeachersScore.total).label("previous_score")
                )
                .join(TeachersScore, TeachersProjects.tea_pro_id == TeachersScore.tea_pro_id)
                .filter(TeachersScore.created_at >= previous_start,
                        TeachersScore.created_at < previous_end)
                .group_by(TeachersProjects.teacher_id)
                .subquery()
            )

            # 2. Get total scores per teacher in current period
            current_scores = (
                db.query(
                    TeachersProjects.teacher_id,
                    func.sum(TeachersScore.total).label("current_score")
                )
                .join(TeachersScore, TeachersProjects.tea_pro_id == TeachersScore.tea_pro_id)
                .filter(TeachersScore.created_at >= current_start,
                        TeachersScore.created_at < current_end)
                .group_by(TeachersProjects.teacher_id)
                .subquery()
            )

            # 3. Join and calculate improvement %
            improvement_q = (
                db.query(
                    current_scores.c.teacher_id,
                    previous_scores.c.previous_score,
                    current_scores.c.current_score,
                    ((current_scores.c.current_score - previous_scores.c.previous_score) / previous_scores.c.previous_score * 100).label("improvement_percentage")
                )
                .join(previous_scores, current_scores.c.teacher_id == previous_scores.c.teacher_id)
                .filter(previous_scores.c.previous_score > 0)  # avoid division by zero
                .filter(((current_scores.c.current_score - previous_scores.c.previous_score) / previous_scores.c.previous_score) >= 0.5)  # at least 50% improvement
                .order_by(((current_scores.c.current_score - previous_scores.c.previous_score) / previous_scores.c.previous_score).desc())
            )

            top_improved = improvement_q.first()

            if top_improved:
                teacher = db.query(Teacher).filter(Teacher.teacher_id == top_improved.teacher_id).first()
                most_improved_teacher_in_date_range = {
                    "teacher_id": top_improved.teacher_id,
                    "teacher_name": teacher.teacher_name if teacher else "Unknown",
                    "previous_score": float(top_improved.previous_score),
                    "current_score": float(top_improved.current_score),
                    "improvement_percentage": float(top_improved.improvement_percentage)
                }
            else:
                most_improved_teacher_in_date_range = None

        else:
            most_improved_teacher_in_date_range = None

        # 4. Present most improved teacher by total cumulative score overall (optional)
        present_teacher_score = (
            db.query(
                TeachersProjects.teacher_id,
                func.sum(TeachersScore.total).label("score")
            )
            .join(TeachersScore, TeachersProjects.tea_pro_id == TeachersScore.tea_pro_id)
            .group_by(TeachersProjects.teacher_id)
            .order_by(func.sum(TeachersScore.total).desc())
            .first()
        )

        present_most_improved_teacher = None
        if present_teacher_score:
            teacher_info = db.query(Teacher).filter(Teacher.teacher_id == present_teacher_score.teacher_id).first()
            present_most_improved_teacher = {
                "teacher_id": teacher_info.teacher_id,
                "teacher_name": teacher_info.teacher_name,
                "cumulative_score": present_teacher_score.score
            }

        return {
            "present_most_improved_teacher": present_most_improved_teacher,
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            },
            "most_improved_teacher_in_date_range": most_improved_teacher_in_date_range
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

