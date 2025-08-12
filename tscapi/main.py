from models import *
from sqlalchemy.exc import SQLAlchemyError

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

# Endpoint to get assigned schools based on user_id (instead of tsc_id)
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