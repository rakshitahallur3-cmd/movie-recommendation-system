import pandas as pd
import ast

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ==========================================
# Load Dataset
# ==========================================

movies = pd.read_csv("dataset/tmdb_5000_movies.csv")
credits = pd.read_csv("dataset/tmdb_5000_credits.csv")

# Merge both datasets
movies = movies.merge(credits, on="title")

# Keep required columns
movies = movies[
    [
        "movie_id",
        "title",
        "overview",
        "genres",
        "keywords",
        "cast",
        "crew",
    ]
]

# Remove missing values
movies.dropna(inplace=True)

# ==========================================
# Helper Functions
# ==========================================

def convert(text):
    L = []
    for i in ast.literal_eval(text):
        L.append(i["name"])
    return L


def convert_cast(text):
    L = []
    counter = 0

    for i in ast.literal_eval(text):
        if counter != 3:
            L.append(i["name"])
            counter += 1
        else:
            break

    return L


def fetch_director(text):
    L = []

    for i in ast.literal_eval(text):
        if i["job"] == "Director":
            L.append(i["name"])
            break

    return L


# ==========================================
# Data Cleaning
# ==========================================

movies["genres"] = movies["genres"].apply(convert)
movies["keywords"] = movies["keywords"].apply(convert)
movies["cast"] = movies["cast"].apply(convert_cast)
movies["crew"] = movies["crew"].apply(fetch_director)

movies["overview"] = movies["overview"].apply(lambda x: x.split())

movies["genres"] = movies["genres"].apply(
    lambda x: [i.replace(" ", "") for i in x]
)

movies["keywords"] = movies["keywords"].apply(
    lambda x: [i.replace(" ", "") for i in x]
)

movies["cast"] = movies["cast"].apply(
    lambda x: [i.replace(" ", "") for i in x]
)

movies["crew"] = movies["crew"].apply(
    lambda x: [i.replace(" ", "") for i in x]
)

# ==========================================
# Create Tags
# ==========================================

movies["tags"] = (
    movies["overview"]
    + movies["genres"]
    + movies["keywords"]
    + movies["cast"]
    + movies["crew"]
)

new_df = movies[["movie_id", "title", "tags"]]

new_df["tags"] = new_df["tags"].apply(lambda x: " ".join(x))
new_df["tags"] = new_df["tags"].apply(lambda x: x.lower())

# ==========================================
# Vectorization
# ==========================================

cv = CountVectorizer(
    max_features=5000,
    stop_words="english"
)

vectors = cv.fit_transform(new_df["tags"]).toarray()

# ==========================================
# Similarity Matrix
# ==========================================

similarity = cosine_similarity(vectors)

# ==========================================
# Recommendation Function
# ==========================================

def recommend(movie):

    movie = movie.lower().strip()

    if movie not in new_df["title"].str.lower().values:
        return []

    movie_index = new_df[
        new_df["title"].str.lower() == movie
    ].index[0]

    distances = similarity[movie_index]

    movies_list = sorted(
        list(enumerate(distances)),
        reverse=True,
        key=lambda x: x[1]
    )[1:11]

    recommendations = []

    for i in movies_list:
        recommendations.append(
            new_df.iloc[i[0]].title
        )

    return recommendations


# ==========================================
# Test
# ==========================================

if __name__ == "__main__":

    movie_name = input("Enter Movie Name: ")

    result = recommend(movie_name)

    print("\nRecommended Movies:\n")

    if len(result) == 0:
        print("Movie not found.")

    else:
        for movie in result:
            print(movie)