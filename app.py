import os
import pandas as pd
import sqlite3
import requests
import re
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.metrics.pairwise import cosine_similarity
from flask import Flask, render_template, request, redirect, session, url_for
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from model.recommend import recommend

app = Flask(__name__)
app.secret_key = "movie_secret_key"
API_KEY = "" #replace with your tmdb api key
load_dotenv()
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)
# ---------------------------------
# Load TMDB Dataset
# ---------------------------------
movies = pd.read_csv("dataset/tmdb_5000_movies.csv")

# ---------------------------------
# Create Database
# ---------------------------------
def create_database():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    # Watchlist table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watchlist(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        movie_id INTEGER,
        title TEXT,
        poster TEXT,
        rating REAL,
        release_date TEXT,
        overview TEXT,
        trailer TEXT
    )
    """)

    conn.commit()
    conn.close()

create_database()
# ---------------------------------
# Get Movie Details from TMDB
# ---------------------------------
# ==========================================
# Get Movie Details from TMDB API
# ==========================================

def get_movie_details(movie_name):

    # Search Movie
    url = (
        f"https://api.themoviedb.org/3/search/movie"
        f"?api_key={API_KEY}&query={movie_name}"
    )

    response = requests.get(url)

    if response.status_code == 200:

        data = response.json()

        if len(data["results"]) > 0:

            movie = data["results"][0]

            # Poster
            poster = ""

            if movie["poster_path"]:
                poster = (
                    "https://image.tmdb.org/t/p/w500"
                    + movie["poster_path"]
                )

            # Trailer
            movie_id = movie["id"]

            video_url = (
                f"https://api.themoviedb.org/3/movie/"
                f"{movie_id}/videos?api_key={API_KEY}"
            )

            video_response = requests.get(video_url)

            trailer = ""

            if video_response.status_code == 200:

                video_data = video_response.json()

                for video in video_data["results"]:

                    if (
                        video["site"] == "YouTube"
                        and video["type"] == "Trailer"
                    ):

                        trailer = (
                            "https://www.youtube.com/embed/"
                            + video["key"]
                        )
                        break

            return {
                "movie_id": movie["id"],
                "title": movie["title"],
                "poster": poster,
                "rating": movie["vote_average"],
                "release_date": movie["release_date"],
                "overview": movie["overview"],
                "trailer": trailer
            }

    return None
# ---------------------------------
# Recommendation Page
# ---------------------------------
@app.route("/recommendation", methods=["GET", "POST"])
def recommendation():

    recommendations = []
    message = ""

    if request.method == "POST":

        movie_name = request.form["movie"]

        result = recommend(movie_name)

        if len(result) == 0:
            message = "❌ Movie Not Found! Please enter a valid movie name."

        else:
            for title in result:

                details = get_movie_details(title)

                if details:
                    recommendations.append(details)

    return render_template(
        "recommendation.html",
        recommendations=recommendations,
        movie_titles=movies["title"].tolist(),
        message=message
    )
# Home Page
# ---------------------------------
@app.route("/")
def home():

    movie_data = []

    for title in movies["title"].head(100):
        details = get_movie_details(title)
        if details:
            movie_data.append(details)

    return render_template(
        "index.html",
        movies=movie_data
    )

# ---------------------------------
# Movies Page
# ---------------------------------
@app.route("/movie")
def movie():

    movie_data = []

    for title in movies["title"].head(20):

        details = get_movie_details(title)

        if details:
            movie_data.append(details)

    return render_template(
        "movie.html",
        movies=movie_data
    )

@app.route("/movie/<int:movie_id>")
def movie_details(movie_id):

    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY}"

    response = requests.get(url)

    if response.status_code != 200:
        return "Movie not found"

    data = response.json()

    poster = ""
    if data.get("poster_path"):
        poster = "https://image.tmdb.org/t/p/w500" + data["poster_path"]

    trailer = ""

    video_url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={API_KEY}"

    video_response = requests.get(video_url)

    if video_response.status_code == 200:

        videos = video_response.json()

        for video in videos["results"]:

            if video["site"] == "YouTube" and video["type"] == "Trailer":

                trailer = "https://www.youtube.com/embed/" + video["key"]

                break

    movie = {
        "movie_id": data["id"],
        "title": data["title"],
        "poster": poster,
        "rating": data["vote_average"],
        "release_date": data["release_date"],
        "overview": data["overview"],
        "trailer": trailer
    }

    return render_template("movie_details.html", movie=movie)

# ---------------------------------

# ---------------------------------
# Watchlist
# ---------------------------------
@app.route("/watchlist")
def watchlist():

    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            movie_id,
            title,
            poster,
            rating,
            release_date,
            overview,
            trailer
        FROM watchlist
        WHERE username=?
        ORDER BY id DESC
    """, (session["user"],))

    rows = cursor.fetchall()

    conn.close()

    movie_data = []

    for row in rows:
        movie_data.append({
            "movie_id": row[0],
            "title": row[1] if row[1] else "Unknown Movie",
            "poster": row[2] if row[2] else "",
            "rating": row[3] if row[3] else 0,
            "release_date": row[4] if row[4] else "Not Available",
            "overview": row[5] if row[5] else "No overview available.",
            "trailer": row[6] if row[6] else ""
        })

    return render_template(
        "watchlist.html",
        movies=movie_data
    )
#remove movie
@app.route("/remove_watchlist/<int:movie_id>")
def remove_watchlist(movie_id):

    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM watchlist
        WHERE username=? AND movie_id=?
    """, (session["user"], movie_id))

    conn.commit()
    conn.close()

    return redirect("/watchlist")
# ---------------------------------
# Profile
# ---------------------------------
@app.route("/profile")
def profile():

    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT username, email FROM users WHERE username=?",
        (session["user"],)
    )

    user = cursor.fetchone()

    conn.close()

    if user:
        return render_template(
            "profile.html",
            username=user[0],
            email=user[1]
        )

    return redirect("/login")

# ---------------------------------
# Signup
# ---------------------------------

from werkzeug.security import generate_password_hash
import re

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        # Connect Database
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        # Check Duplicate Username
        cursor.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        )

        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return render_template(
                "signup.html",
                message="Username already exists"
            )

        # Validate Email
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

        if not re.match(pattern, email):
            conn.close()
            return render_template(
                "signup.html",
                message="Invalid Email Address"
            )

        # Hash Password
        password = generate_password_hash(password)

        # Insert User
        cursor.execute(
            """
            INSERT INTO users(username,email,password)
            VALUES(?,?,?)
            """,
            (username, email, password)
        )

        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("signup.html")

# ---------------------------------
# Login
# ---------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        )

        user = cursor.fetchone()

        conn.close()

        if user:

            # user[3] = password column
            if check_password_hash(user[3], password):

                session["user"] = user[1]   # username

                return redirect("/")

        return render_template(
            "login.html",
            message="Invalid Email or Password"
        )

    return render_template("login.html")
#add watchlist
@app.route("/add_watchlist/<int:movie_id>")
def add_watchlist(movie_id):

    if "user" not in session:
        return redirect("/login")

    movie = None

    # Find selected movie
    for title in movies["title"]:
        details = get_movie_details(title)

        if details and details["movie_id"] == movie_id:
            movie = details
            break

    if movie:

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        # Check if movie already exists in watchlist
        cursor.execute("""
            SELECT * FROM watchlist
            WHERE username=? AND movie_id=?
        """, (session["user"], movie_id))

        existing_movie = cursor.fetchone()

        if not existing_movie:

            cursor.execute("""
                INSERT INTO watchlist
                (
                    username,
                    movie_id,
                    title,
                    poster,
                    rating,
                    release_date,
                    overview,
                    trailer
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session["user"],
                movie["movie_id"],
                movie["title"],
                movie["poster"],
                movie["rating"],
                movie["release_date"],
                movie["overview"],
                movie["trailer"]
            ))

            conn.commit()

        conn.close()

    return redirect("/watchlist")


#login google
@app.route("/google")
def google_login():
    redirect_uri = url_for("authorize", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/authorize")
def authorize():
    token = google.authorize_access_token()

    user = token["userinfo"]

    session["user"] = user["name"]
    session["email"] = user["email"]

    return redirect("/")
# -------------------------
# Logout
# -------------------------
@app.route("/logout")
def logout():
    session.clear()      # Remove all session data
    return redirect("/")


# ---------------------------------
# Run App
# ---------------------------------
if __name__ == "__main__":
    app.run(debug=True)