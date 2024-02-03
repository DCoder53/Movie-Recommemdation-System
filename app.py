import pickle
from flask import Flask, render_template, request
import aiohttp
import asyncio

app = Flask(__name__, template_folder='templates')

movies = pickle.load(open("movies_list.pkl", 'rb'))
similarity = pickle.load(open("similarity.pkl", 'rb'))
movies_list = movies['title'].values
TMDB_API_KEY = '3403725145e14a315dce569732e354b0'

async def fetch_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

async def fetch_movie_details(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=en-US"
    return await fetch_data(url)

async def fetch_poster(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=en-US"
    data = await fetch_data(url)
    poster_path = data.get('poster_path')
    full_path = f"https://image.tmdb.org/t/p/w500/{poster_path}" if poster_path else None
    return full_path

async def f_i(id):
    base_url = f"https://api.themoviedb.org/3/person/{id}?api_key={TMDB_API_KEY}&language=en-US"
    data = await fetch_data(base_url)
    profile_path = data.get('profile_path')
    full_path = f"https://image.tmdb.org/t/p/w500/{profile_path}" if profile_path else None
    return full_path

async def fetch_background_image_by_id(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=en-US"
    movie_details = await fetch_data(url)
    backdrop_path = movie_details.get('backdrop_path')
    background_path = f"https://image.tmdb.org/t/p/original/{backdrop_path}" if backdrop_path else None
    return background_path

async def get_movies_by_actor(actor_name):
    search_actor_url = f'https://api.themoviedb.org/3/search/person?api_key={TMDB_API_KEY}&query={actor_name}'
    actor_data = await fetch_data(search_actor_url)

    if 'results' in actor_data and actor_data['results']:
        actor_id = actor_data['results'][0]['id']

        credits_url = f'https://api.themoviedb.org/3/person/{actor_id}/movie_credits?api_key={TMDB_API_KEY}'
        credits_data = await fetch_data(credits_url)

        movies_info = [{'id': movie['id'], 'title': movie['title'], 'poster_path': movie['poster_path']} for movie in credits_data.get('cast', [])]

        return movies_info
    
    return None

async def run_asyncio(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, func, *args, **kwargs)

    if asyncio.iscoroutine(result):
        result = await result

    if not isinstance(result, (list, tuple)):
        result = [result]

    return result

async def get_movies_by_genre(genre_name, target_num_movies=50):
    search_genre_url = f'https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}'
    genre_data = await fetch_data(search_genre_url)

    genre_id = None
    for genre in genre_data.get('genres', []):
        if genre['name'].lower() == genre_name.lower():
            genre_id = genre['id']
            break

    if genre_id is not None:
        movies_info = []
        page = 1

        while len(movies_info) < target_num_movies:
            discover_url = f'https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_genres={genre_id}&page={page}'
            movies_data = await fetch_data(discover_url)

            movies_info.extend([{'id': movie['id'], 'title': movie['title'], 'poster_path': movie['poster_path']} for movie in movies_data.get('results', [])])

            page += 1
  
        return movies_info[:target_num_movies]
    
    return None


async def recommend(movie):
    index = movies[movies['title'] == movie].index[0]
    distance = sorted(enumerate(similarity[index]), reverse=True, key=lambda act: act[1])
    recommend_titles = []
    recommend_posters = []

    # Fetching movie details and posters concurrently
    tasks = [asyncio.gather(fetch_movie_details(movies.iloc[i[0]].id), fetch_poster(movies.iloc[i[0]].id)) for i in distance[0:10]]
    results = await asyncio.gather(*tasks)

    for i, (movie_details, poster_url) in enumerate(results):
        recommend_titles.append(movie_details)
        if poster_url:
            recommend_posters.append(poster_url)

    return recommend_titles, recommend_posters


async def recommend2(genre):
    target_num_movies = 50
    movies_by_genre = await get_movies_by_genre(genre, target_num_movies)
    movies_title = []
    movies_poster = []
    movies_id = []

    if movies_by_genre:
        print(f'Movies in the {genre} genre:')
        # Fetching movie details and posters concurrently
        tasks = [asyncio.gather(fetch_movie_details(movie['id']), fetch_poster(movie['id'])) for movie in movies_by_genre]
        results = await asyncio.gather(*tasks)

        for i, (movie_details, poster_url) in enumerate(results):
            if movie_details and poster_url:
                movies_id.append(movies_by_genre[i]['id'])
                movies_title.append(movie_details['title'])
                movies_poster.append(poster_url)

    return movies_title, movies_poster, movies_id

def render_actor_page(actor_name):
    movies_info = run_asyncio(get_movies_by_actor, actor_name)

    if movies_info:
        movies_id = []
        recommend_titles = []
        poster_paths = []

        for movie in movies_info:
            movie_id = movie.get('id')
            title = movie.get('title')
            poster_path = movie.get('poster_path')

            if movie_id and title and poster_path:
                movies_id.append(movie_id)
                recommend_titles.append(title)
                poster_paths.append(f"https://image.tmdb.org/t/p/w500/{poster_path}")

        return render_template('actors.html', actor_name=actor_name, movies_id=movies_id, movies_title=recommend_titles, movies_poster=poster_paths)

    return render_template('actors.html', actor_name=actor_name, movies_id=[], movies_title=[], movies_poster=[])

async def fetch_trailer(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={TMDB_API_KEY}&language=en-US"
    data = await fetch_data(url)

    for video in data.get('results', []):
        if video.get('type') == 'Trailer':
            return f"https://www.youtube.com/watch?v={video.get('key')}"

    return None


def run_asyncio(func, *args):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(func(*args))
    finally:
        loop.close()

@app.route("/")
async def home():
    selected_movie = request.args.get("movie")

    if not selected_movie or selected_movie not in movies_list:
        selected_movie = "The Godfather"

    recommend_movie, recommend_poster = await recommend(selected_movie)

    return render_template('index1.html', recommend_movie=recommend_movie, recommend_poster=recommend_poster, movies_list=movies_list, movies=movies)


@app.route("/Action")
def action_page():
    genre = "Action"
    recommend_titles, recommend_poster, movies_id = run_asyncio(recommend2, genre)
    return render_template('genre.html', genre=genre, recommend_movie=recommend_titles, recommend_poster=recommend_poster, movies_id=movies_id)

@app.route("/Comedy")
def comedy_page():
    genre = "Comedy"
    recommend_titles, recommend_poster, movies_id = run_asyncio(recommend2, genre)
    return render_template('genre.html', genre=genre, recommend_movie=recommend_titles, recommend_poster=recommend_poster, movies_id=movies_id)
@app.route("/Drama")
def drama_page():
    genre="Drama"
    # For now, let's assume you have a function to get top movies for the specified genre
    recommend_titles, recommend_poster , movies_id= run_asyncio(recommend2,genre)
    return render_template('genre.html',genre=genre, recommend_movie=recommend_titles, recommend_poster=recommend_poster ,movies_id=movies_id)

@app.route("/Scify")
def Scify_page():
    genre='Science Fiction'
    # For now, let's assume you have a function to get top movies for the specified genre
    recommend_titles, recommend_poster , movies_id= run_asyncio(recommend2,genre)
    return render_template('genre.html',genre=genre, recommend_movie=recommend_titles, recommend_poster=recommend_poster ,movies_id=movies_id)

@app.route("/genre/<genre_name>")
def genre_page(genre_name):
    # For now, let's assume you have a function to get top movies for the specified genre
    recommend_titles, recommend_poster, movies_id = asyncio.run(recommend2(genre_name))
    return render_template('genre.html', genre=genre_name, recommend_movie=recommend_titles, recommend_poster=recommend_poster, movies_id=movies_id)

@app.route("/Srk")
def srk_page():
    return render_actor_page('Shah Rukh Khan')

@app.route("/Suriya")
def Suriya():
    return render_actor_page('Suriya')

@app.route("/ShahidKapoor")
def Shahid():
    return render_actor_page('Shahid Kapoor')

@app.route("/Vijay")
def Vijay():
    return render_actor_page('Vijay Sethupathi')

@app.route("/Ranbir")
def Ranbir():
    return render_actor_page('Ranbir Kapoor')

@app.route("/Manoj")
def Manoj():
    return render_actor_page('Manoj Bajpayee')

@app.route("/RDJ")
def RDJ():
    return render_actor_page('Robert Downey Jr.')


@app.route("/actor/<actor_name>")
def a_page(actor_name):
    return render_actor_page(actor_name)

@app.route("/details/<movie_id>")
async def details(movie_id):
    movie_details, credits_data = await asyncio.gather(fetch_movie_details(movie_id), fetch_data(f"https://api.themoviedb.org/3/movie/{movie_id}/credits?api_key={TMDB_API_KEY}"))

    title = movie_details['title']
    overview = movie_details['overview']
    release_date = movie_details['release_date']
    vote_average = movie_details['vote_average']
    tagline = movie_details['tagline']
    original_language = movie_details['original_language']
    status=movie_details["status"]
    poster_path = f"https://image.tmdb.org/t/p/w500/{movie_details.get('poster_path')}" if movie_details.get('poster_path') else None

    # Additional details
    genres = ', '.join([genre['name'] for genre in movie_details.get('genres', [])])

    # Director
    directors = [crew['name'] for crew in credits_data.get('crew', []) if crew['job'] == 'Director']

    # Cast posters and names
    cast_tasks = [f_i(cast_info['id']) for cast_info in credits_data.get('cast', [])[:9]]
    cast_results = await asyncio.gather(*cast_tasks)
    cast_posters = [result for result in cast_results if result]
    cast_names = [cast_info['name'] for cast_info in credits_data.get('cast', [])[:9]]

    # Fetch trailer link
    trailer_link = await fetch_trailer(movie_id)
    background_image = await fetch_background_image_by_id(movie_id)

    recommend_titles = []
    recommend_posters = []

    if title in movies_list: 
        recommend_titles, recommend_posters = await recommend(title)
        
    # Zipping data
    zipped_cast = zip(cast_posters, cast_names)

    return render_template("details.html", title=title, overview=overview, release_date=release_date, vote_average=vote_average, 
                            poster_path=poster_path, genres=genres, original_language=original_language, 
                            directors=directors, zipped_cast=zipped_cast, trailer_link=trailer_link, tagline=tagline,
                            background_image=background_image,status=status,recommend_movie=recommend_titles,recommend_poster=recommend_posters)

if __name__ == '__main__':
    app.run(debug=True)