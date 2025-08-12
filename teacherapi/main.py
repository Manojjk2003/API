from models import *

# Endpoint to get Teacher Dashboard data
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


# Endpoint to delete a teacher project and related scores 
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

# 1. Endpoint for uploading Teacher Projects
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


# 2. Endpoint for uploading Student Projects

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

    # Endpoint to fetch teacher project details and associated scores
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
    # Your routes and logic here...

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)