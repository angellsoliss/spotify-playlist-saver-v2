from dotenv import load_dotenv
import os
from flask import Flask, redirect, jsonify, session, request, url_for, render_template
import requests
import urllib
from datetime import datetime
import spotipy

#load environment variables
load_dotenv()
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
#set redirect uri
REDIRECT_URI = "http://localhost:5000/callback"

#initialize app
app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY")

#url to authorize user
AUTH_URL = "https://accounts.spotify.com/authorize"

#url to refresh token
TOKEN_URL = "https://accounts.spotify.com/api/token"

#home page, prompt user to log in with their spotify account
@app.route('/')
def index():
    return render_template('index.html')

#login page
@app.route('/login', methods=['POST'])
def login():
    scope = 'user-read-private user-read-email user-library-read playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative'

    params = {
        'client_id': client_id,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': REDIRECT_URI,
        'show_dialog': True
    }

    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    #redirect user to authorization page
    return redirect(auth_url)

@app.route('/callback')
def callback():
    #check if error occured while logging in
    if 'error' in request.args:
        return jsonify({"error": request.args['error']})

    #if user successfully logs in
    if 'code' in request.args:
        #create request_body to exchange it for access token
        request_body = {
            'code': request.args['code'],
            'grant_type': 'authorization_code',
            'redirect_uri': REDIRECT_URI,
            'client_id': client_id,
            'client_secret': client_secret
        }

        #send request body to token url to get access token
        response = requests.post(TOKEN_URL, data=request_body)
        #store token info
        token_info = response.json()

        #store acces token and refresh token within session
        session['access_token'] = token_info['access_token']
        session['refresh_token'] = token_info['refresh_token']

        #store token expiration date within token
        session['expires_at'] = datetime.now().timestamp() + token_info['expires_in']

        #redirect user to app functionality page
        return redirect('/playlists')

@app.route('/playlists', methods=['POST', 'GET'])
def get_playlists():
    #check if access token is present within session
    if 'access_token' not in session:
        #if access token is not present, prompt user to login again
        return redirect('/login')
    
    #otherwise, check if access token has expired
    if datetime.now().timestamp() > session['expires_at']:
        #if token has expired, refresh token
        return redirect('/refresh-token')
    
    #create spotipy object, pass access token
    sp = spotipy.Spotify(auth=session['access_token'])
    
    #store user id to create playlist
    user_id = sp.current_user()['id']

    #get user playlists
    current_playlists = sp.current_user_playlists()['items']

    #array used to hold playlist names
    playlist_names = []

    #iterate through playlists
    for playlist in current_playlists:
        #add the name of each playlist to playlist_names array
        playlist_names.append(f"{playlist['name']}")
    
    #if user enters playlist name
    if request.method == 'POST':
        #get text entered by user
        submittedName = request.form.get('submittedName', '')

        #create playlist name with the user submitted text
        formattedName = f"{submittedName} - {datetime.now().strftime('%m/%d/%Y')}"

        #initialize playlist id
        playlist_id = None

        #iterate through user playlists
        for playlist in current_playlists:
            #check if submitted text matches the name of an existing playlist
            if playlist['name'].lower() == submittedName.lower():
                #grab the id of the playlist that is to be saved
                playlist_id = playlist['id']
                break
            
        #if user playlist is not found
        if not playlist_id:
            return playlistNotFound()
            
        #create new playlist
        new_playlist = sp.user_playlist_create(user_id, name=formattedName)

        #get tracks from playlist being saved
        playlist_tracks = sp.playlist_items(playlist_id=playlist_id)

        #get song uris
        song_uris = []
        for track in playlist_tracks['items']:
            track_uri = track['track']['uri']
            song_uris.append(track_uri)
            
        #add songs from temporary playlist to new permanent playlist
        sp.user_playlist_add_tracks(user_id, new_playlist['id'], song_uris, None)
    
    #return html page
    return render_template('playlists.html', playlist_names=playlist_names)

@app.route('/refresh-token')
def refresh():
    #check if refresh token is in session
    if 'refresh_token' not in session:
        #if refresh token is not in session, prompt user to log in again
        redirect('/login')
    
    #otherwise, check if access token has expired
    if datetime.now().timestamp() > session['expires_at']:
        #build request body
        request_body = {
            'grant-type': 'refresh_token',
            'refresh_token': session['refresh_token'],
            'client_id': client_id,
            'client_secret': client_secret
        }

        #request fresh access token using request body
        response = requests.post(TOKEN_URL, data=request_body)
        #store fresh token
        new_token_info = response.json()

        #update session token/expires_at values
        session['access_token'] = new_token_info['access_token']
        session['expires_at'] = datetime.now().timestamp() + new_token_info['expires_in']

        #redirect user
        return redirect('/playlists')

@app.route('/notFound')
def playlistNotFound():
    return render_template('notFound.html')

#run app
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, threaded=True)