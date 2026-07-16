import pandas as pd

movies = pd.read_csv("dataset/TMDB_all_movies.csv")

print(movies.columns.tolist())