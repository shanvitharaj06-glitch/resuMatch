from pymongo import MongoClient
from pymongo.server_api import ServerApi

uri = "mongodb+srv://resuMatch_user:resuMatch_user@cluster0.qkbdtb9.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

client = MongoClient(uri, server_api=ServerApi('1'))

try:
    client.admin.command('ping')
    print("Connected to MongoDB Atlas!")
except Exception as e:
    print("Connection Error:", e)

db = client["resumatch_db"]

users = db["users"]
profiles = db["profiles"]
resumes = db["resumes"]
applications = db["applications"]
ats_scores = db["ats_scores"]
jobs = db["jobs"]