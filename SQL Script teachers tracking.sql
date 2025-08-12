create database teachers_tracking;
use teachers_tracking;

CREATE TABLE users (
    users_id VARCHAR(100) NOT NULL PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    role VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE admin (
    admin_id VARCHAR(100) NOT NULL PRIMARY KEY,
    users_id VARCHAR(100),
    admin_name VARCHAR(255),
    email VARCHAR(255),
    ph_no VARCHAR(20),
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    gender VARCHAR(10) NOT NULL,
    FOREIGN KEY (users_id) REFERENCES users(users_id),
    FOREIGN KEY (created_by) REFERENCES users(users_id)
);


CREATE TABLE organization (
    organization_id VARCHAR(100) NOT NULL PRIMARY KEY,
    organization_name TEXT NOT NULL,
    contact_person VARCHAR(255),
    email VARCHAR(255),
    ph_no VARCHAR(20),
    address TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(users_id)
);

CREATE TABLE school (
    school_id VARCHAR(100) NOT NULL PRIMARY KEY,
    school_name VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    ph_no VARCHAR(20),
    addr VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    organization_id VARCHAR(100),
    created_by VARCHAR(100),
    FOREIGN KEY (organization_id) REFERENCES organization(organization_id),
    FOREIGN KEY (created_by) REFERENCES users(users_id)
);

CREATE TABLE tsc (
    tsc_id VARCHAR(100) NOT NULL PRIMARY KEY,
    users_id VARCHAR(100),
    tsc_name VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    ph_no VARCHAR(20),
    gender VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    FOREIGN KEY (users_id) REFERENCES users(users_id),
    FOREIGN KEY (created_by) REFERENCES users(users_id)
);

CREATE TABLE teacher (
    teacher_id VARCHAR(100) NOT NULL PRIMARY KEY,
    users_id VARCHAR(100),
    teacher_name VARCHAR(255),
    school_id VARCHAR(100),
    classes VARCHAR(100),
    number_of_students INT,
    gender VARCHAR(10),
    email VARCHAR(255) UNIQUE,
    dob DATE,
    age INT,
    ph_no VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    FOREIGN KEY (users_id) REFERENCES users(users_id),
    FOREIGN KEY (school_id) REFERENCES school(school_id),
    FOREIGN KEY (created_by) REFERENCES users(users_id)
);

CREATE TABLE school_tsc_mapping (
    mapping_id VARCHAR(255) NOT NULL PRIMARY KEY,
    school_id VARCHAR(50),
    tsc_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id) REFERENCES school(school_id),
    FOREIGN KEY (tsc_id) REFERENCES tsc(tsc_id)
);

CREATE TABLE session_students_details (
    se_st_det_id VARCHAR(100) NOT NULL PRIMARY KEY,
    no_of_students INT,
    grade INT,
    section VARCHAR(255),
    feedback VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE teachers_projects (
    tea_pro_id VARCHAR(100) NOT NULL PRIMARY KEY,
    teacher_id VARCHAR(100),
    project_link VARCHAR(255) UNIQUE,
    feedback VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (teacher_id) REFERENCES teacher(teacher_id)
);

CREATE TABLE teachers_score (
    tea_sc_id VARCHAR(100) NOT NULL PRIMARY KEY,
    tea_pro_id VARCHAR(100),
    tsc_id VARCHAR(100),
    creativity INT,
    code_complexity INT,
    originality_of_code INT,
    usage_of_spr_bd INT,
    animations_sounds INT,
    total INT,
    feedback VARCHAR(255),
    evaluated_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tea_pro_id) REFERENCES teachers_projects(tea_pro_id),
    FOREIGN KEY (tsc_id) REFERENCES tsc(tsc_id),
    FOREIGN KEY (evaluated_by) REFERENCES users(users_id)
);

CREATE TABLE student_projects (
    stu_pro_id VARCHAR(100) NOT NULL PRIMARY KEY,
    teacher_id VARCHAR(100),
    project_link VARCHAR(255) UNIQUE,
    status VARCHAR(50) DEFAULT 'pending',
    se_st_det_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (teacher_id) REFERENCES teacher(teacher_id),
    FOREIGN KEY (se_st_det_id) REFERENCES session_students_details(se_st_det_id)
);

CREATE TABLE students_score (
    st_sc_id VARCHAR(100) NOT NULL PRIMARY KEY,
    stu_pro_id VARCHAR(100),
    tsc_id VARCHAR(100),
    creativity INT,
    code_complexity INT,
    originality_of_code INT,
    usage_of_spr_bd INT,
    animations_sounds INT,
    total INT,
    feedback VARCHAR(255),
    evaluated_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stu_pro_id) REFERENCES student_projects(stu_pro_id),
    FOREIGN KEY (tsc_id) REFERENCES tsc(tsc_id),
    FOREIGN KEY (evaluated_by) REFERENCES users(users_id)
);
