# --- imports ---
import os
from flask import Flask, session, request, redirect, url_for
from dotenv import load_dotenv
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from functools import wraps

# --- config ---
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key123'

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
SCOPE = 'playlist-read-private user-library-read'

cache_handler = FlaskSessionCacheHandler(session)
sp_oauth = SpotifyOAuth(
    client_id = CLIENT_ID,
    client_secret = CLIENT_SECRET,
    redirect_uri = REDIRECT_URI,
    scope = SCOPE,
    cache_handler = cache_handler,
    # show_dialog = True # true for debugging purposes, makes user authenticate every hour?
)

# --- helper functions ---
def require_spotify_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = sp_oauth.get_cached_token()
        if not token or not sp_oauth.validate_token(token):
            return redirect(sp_oauth.get_authorize_url())
        return f(*args, **kwargs)
    return wrapper

def get_spotify_client():
    token = sp_oauth.get_cached_token()
    if not token or not sp_oauth.validate_token(token):
        token = sp_oauth.refresh_access_token(token['refresh_token'])
    return Spotify(auth=token['access_token']) if token else None

def get_all_tracks(fetch_func, **kwargs):
    items = []
    limit = kwargs.get('limit', 50)
    offset = 0

    while True:
        page = fetch_func(limit=limit, offset=offset, **kwargs)
        page_items = page['items']
        if not page_items:
            break
        items.extend(page_items)
        offset += limit

    return items

# --- routes ---
@app.route('/')
def index():
    return """
    <h1>Welcome to Song Swiper!</h1>
    <a href='/login'><button>Login</button></a>
    """

@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    sp_oauth.get_access_token(request.args['code'])
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@require_spotify_auth
def dashboard():
    sp = get_spotify_client()
    user = sp.current_user()
    name = user.get('display_name', 'user')
    
    dashboard_html = f"""
    <h1>Welcome, {name}!</h1>
    <a href='/select_playlist'><button>Select playlist</button></a>
    <br><a href='/logout'><button>Logout</button></a>
    """
    
    return dashboard_html

@app.route('/select_playlist')
@require_spotify_auth
def select_playlist():
    sp = get_spotify_client()
    # user = sp.current_user()
    playlists = sp.current_user_playlists()
    form_html = "<h1>Select a playlist</h1><form method='POST' action='/selected_playlist'>"
    
    form_html += "<input type='radio' name='playlist_id' value='liked' required> Liked Songs<br>"
    
    for playlist in playlists['items']:
        playlist_id = playlist['id']
        playlist_name = playlist['name']
        form_html += f"<input type='radio' name='playlist_id' value='{playlist_id}' required> {playlist_name}<br>"
    
    form_html += "<br><button type='submit'>Start swiping</button></form>"
    form_html += "<br><a href='/dashboard'><button>Back to dashboard</button></a>"
    
    return form_html

@app.route('/selected_playlist', methods=['POST'])
@require_spotify_auth
def selected_playlist():
    sp = get_spotify_client()
    # user = sp.current_user()
    playlist_id = request.form['playlist_id']
    
    if playlist_id == 'liked':
        playlist = sp.current_user_saved_tracks()
        playlist_name = 'Liked Songs'
        tracks = get_all_tracks(sp.current_user_saved_tracks)
    else:
        playlist = sp.playlist(playlist_id)
        playlist_name = playlist['name']
        tracks = get_all_tracks(sp.playlist_items, playlist_id=playlist_id)
    
    track_list = "<ol style='line-height: 1.8;'>"
    for item in tracks:
        track = item['track']
        track_name = track['name']
        album_name = track['album']['name']
        artist_names = ', '.join([artist['name'] for artist in track['artists']])
        track_list += f"<li>{track_name}  |  {album_name}  |  {artist_names}</li>"
    track_list += "</ol>"
    
    return f"""
    <h1>Playlist: {playlist_name}</h1>
    {track_list}
    <br><a href='/select_playlist'><button>Choose another playlist</button></a>
    <br><a href='/dashboard'><button>Back to dashboard</button></a>
    """

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)