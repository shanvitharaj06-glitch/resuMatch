from werkzeug.utils import secure_filename
import os
from flask import Flask, render_template, request, redirect, session
from database.mongodb import *
import bcrypt
from pymongo import MongoClient
from dotenv import load_dotenv

# 1. Load the hidden .env file (used when running locally on your computer)
load_dotenv()

# 2. Grab the MONGO_URI variable securely from the system environment
MONGO_URI = os.environ.get("MONGO_URI")

# 3. Connect to MongoDB Atlas with secure TLS/SSL settings enabled
client = MongoClient(MONGO_URI, tls=True)

# 4. Select your specific database name
db = client.get_database("resuMatch_db") 
app = Flask(__name__)

# Secret key for sessions
app.secret_key = "resumatch_secret_key"


# ---------------- HOME PAGE ----------------
@app.route('/')
def home():
    return render_template('index.html')


# ---------------- REGISTER PAGE ----------------
@app.route('/register')
def register_page():
    return render_template('register.html')


# ---------------- REGISTER USER ----------------
@app.route('/register', methods=['POST'])
def register_user():

    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    role = request.form['role']

    # Check whether email already exists
    existing_user = users.find_one({"email": email})

    if existing_user:
        return "Email already exists!"

    # Hash password
    hashed_password = bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    )

    # Insert into MongoDB
    users.insert_one({
        "name": name,
        "email": email,
        "password": hashed_password,
        "role": role
    })

    return redirect('/login')


# ---------------- LOGIN PAGE ----------------
@app.route('/login')
def login_page():
    return render_template('login.html')


# ---------------- LOGIN USER ----------------
@app.route('/login', methods=['POST'])
def login_user():

    email = request.form['email']
    password = request.form['password']

    user = users.find_one({"email": email})

    if not user:
        return "Invalid Email!"

    if bcrypt.checkpw(
        password.encode('utf-8'),
        user['password']
    ):

        session['name'] = user['name']
        session['email'] = user['email']
        session['role'] = user['role']

        if user['role'] == 'candidate':
            return redirect('/candidate')
        else:
            return redirect('/recruiter')

    return "Wrong Password!"


# ---------------- CANDIDATE DASHBOARD ----------------
@app.route('/candidate')
def candidate_dashboard():

    if 'email' not in session:
        return redirect('/login')

    email = session['email']

    profile = profiles.find_one({"email": email})
    resume = resumes.find_one({"email": email})

    applications_count = applications.count_documents({"email": email})

    score = ats_scores.find_one({"email": email})
    ats = score['score'] if score else 0

    # 🔥 ADD THIS: recent applications
    recent_apps = applications.find(
        {"email": email}
    ).sort("_id", -1).limit(5)

    return render_template(
        'candidate_dashboard.html',
        name=session['name'],
        profile=profile,
        resume=resume,
        applications=applications_count,
        ats=ats,
        recent_apps=recent_apps   # 🔥 IMPORTANT
    )

# ---------------- RECRUITER DASHBOARD ----------------
@app.route('/recruiter')
def recruiter_dashboard():

    if 'email' not in session:
        return redirect('/login')

    jobs_count = jobs.count_documents({})
    applications_count = applications.count_documents({})
    shortlisted = applications.count_documents({"status": "Shortlisted"})
    interviews = applications.count_documents({"status": "Interview"})

    candidates = applications.find()

    return render_template(
        'recruiter_dashboard.html',
        jobs_count=jobs_count,
        applications_count=applications_count,
        shortlisted=shortlisted,
        interviews=interviews,
        candidates=candidates
    )

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/ats_score')
def ats_score():
    if 'email' not in session:
        return redirect('/login')

    # Get user email from session
    user_email = session.get('email')

    # Fetch ATS record
    record = ats_scores.find_one({"email": user_email})

    # Default score
    score = 0

    # Safe extraction (handles missing / string / % formats)
    if record and record.get("score") is not None:
        try:
            raw_score = record.get("score")

            # remove % if stored like "85%"
            if isinstance(raw_score, str):
                raw_score = raw_score.replace("%", "")

            score = int(raw_score)

        except:
            score = 0

    # Color logic
    if score >= 75:
        color = "#00c853"
        gradient = "linear-gradient(90deg,#00c853,#66bb6a)"
    elif score >= 50:
        color = "#ff9800"
        gradient = "linear-gradient(90deg,#ff9800,#ffb74d)"
    else:
        color = "#ff5252"
        gradient = "linear-gradient(90deg,#ff5252,#ef5350)"

    return render_template(
        'ats_score.html',
        ats=score,
        color=color,
        gradient=gradient
    )


@app.route('/profile')
def profile():

    if 'email' not in session:
        return redirect('/login')

    user_profile = profiles.find_one({
        "email": session['email']
    })

    return render_template(
        'profile.html',
        profile=user_profile
    )

@app.route('/save_profile', methods=['POST'])
def save_profile():

    phone = request.form['phone']
    qualification = request.form['qualification']
    skills = request.form['skills']
    linkedin = request.form['linkedin']
    github = request.form['github']

    profiles.update_one(
        {
            "email": session['email']
        },
        {
            "$set": {
                "email": session['email'],
                "phone": phone,
                "qualification": qualification,
                "skills": skills,
                "linkedin": linkedin,
                "github": github
            }
        },
        upsert=True
    )

    return redirect('/candidate')
@app.route('/upload_resume', methods=['GET', 'POST'])
def upload_resume():

    if 'email' not in session:
        return redirect('/login')

    if request.method == 'POST':

        file = request.files['resume']

        if file.filename != "":

            filename = secure_filename(
                file.filename
            )

            path = os.path.join(
                'static/uploads',
                filename
            )

            file.save(path)

            resumes.update_one(
                {
                    "email": session['email']
                },
                {
                    "$set": {
                        "email": session['email'],
                        "file": filename
                    }
                },
                upsert=True
            )

            return redirect('/candidate')

    return render_template(
        'upload_resume.html'
    )

@app.route('/jobs')
def jobs_page():

    if 'email' not in session:
        return redirect('/login')

    if session['role'] != 'candidate':
        return "Access Denied"

    user_profile = profiles.find_one({"email": session['email']})

    user_skills = []
    if user_profile and "skills" in user_profile:
        user_skills = user_profile["skills"].lower().split(",")

    all_jobs = list(jobs.find())

    recommended = []
    others = []

    for job in all_jobs:
        job_skills = job.get("skills", [])

        match_score = len(set(user_skills) & set(job_skills))

        job["match_score"] = match_score

        if match_score > 0:
            recommended.append(job)
        else:
            others.append(job)

    return render_template(
        "jobs.html",
        recommended=recommended,
        jobs=others
    )


@app.route('/apply/<job_id>')
def apply_job(job_id):

    if 'email' not in session:
        return redirect('/login')

    from bson.objectid import ObjectId

    job = jobs.find_one({"_id": ObjectId(job_id)})

    # 🔥 CHECK DUPLICATE APPLICATION
    existing_application = applications.find_one({
        "email": session['email'],
        "position": job['title']
    })

    if existing_application:
        return "⚠ You have already applied for this job!"

    # skills + ATS logic (your existing logic)
    profile = profiles.find_one({"email": session['email']})
    name = profile.get("name") if profile else "Unknown"
    user_skills = profile.get("skills", "").lower().split(",") if profile else []
    job_skills = job.get("skills", [])

    match_score = len(set(user_skills) & set(job_skills))

    ats_score = int((match_score / len(job_skills)) * 100) if job_skills else 0

    applications.insert_one({
        "name": session['name'],
        "email": session['email'],
        "company": job['company'],
        "position": job['title'],
        "status": "Applied",
        "ats": ats_score,
        "job_id": str(job["_id"])   # 🔥 extra safety
    })

    return redirect('/applied_jobs')

@app.route('/applied_jobs')
def applied_jobs():

    if 'email' not in session:
        return redirect('/login')

    user_jobs = applications.find({
        "email": session['email']
    })

    return render_template(
        'applied_jobs.html',
        jobs=user_jobs
    )

@app.route('/jobs_list')
def jobs_list():
    if 'email' not in session:
        return redirect('/login')

    all_jobs = jobs.find()
    return render_template('job_listing.html', jobs=all_jobs)

@app.route('/post_jobs', methods=['GET', 'POST'])
def post_jobs():

    if 'email' not in session:
        return redirect('/login')

    if request.method == 'POST':

        jobs.insert_one({
            "title": request.form['title'],
            "company": request.form['company'],
            "location": request.form['location'],
            "type": request.form['type'],
            "salary": request.form['salary'],
            "description": request.form['description']
        })

        return redirect('/jobs_list')

    return render_template('post_jobs.html')

@app.route('/candidates')
def candidates_page():

    if 'email' not in session:
        return redirect('/login')

    # get applications as candidates
    candidates = applications.find()

    return render_template(
        'candidates.html',
        candidates=candidates
    )

@app.route('/view_resume/<app_id>')
def view_resume(app_id):

    from bson.objectid import ObjectId

    app = applications.find_one({"_id": ObjectId(app_id)})

    if not app:
        return "Application not found"

    resume = resumes.find_one({"email": app["email"]})

    if resume:
        return redirect("/static/uploads/" + resume["file"])

    return "No resume uploaded"

@app.route('/shortlist/<app_id>')
def shortlist(app_id):

    from bson.objectid import ObjectId

    applications.update_one(
        {"_id": ObjectId(app_id)},
        {"$set": {"status": "Shortlisted"}}
    )

    return redirect('/candidates')

@app.route('/reject/<app_id>')
def reject(app_id):

    from bson.objectid import ObjectId

    applications.update_one(
        {"_id": ObjectId(app_id)},
        {"$set": {"status": "Rejected"}}
    )

    return redirect('/candidates')

@app.route('/shortlisted_candidates')
def shortlisted_candidates():

    if 'email' not in session:
        return redirect('/login')

    shortlisted = applications.find({
        "status": "Shortlisted"
    })

    return render_template(
        "shortlisted_candidates.html",
        candidates=shortlisted
    )
@app.route('/interview/<app_id>')
def interview(app_id):

    from bson.objectid import ObjectId

    applications.update_one(
        {"_id": ObjectId(app_id)},
        {"$set": {"status": "Interview"}}
    )

    return redirect('/recruiter')
if __name__ == '__main__':
    app.run(debug=True)
