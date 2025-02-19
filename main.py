import socket

from flask import Flask, session, redirect, url_for, request, render_template, jsonify
import os
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from time import gmtime
from time import strftime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

client_id = os.getenv('client_id')
client_secret = os.getenv('client_secret')

local_ip = socket.gethostbyname(socket.gethostname())
vercel_url = os.getenv('VERCEL_URL')

# redirect_uri for local and production environments
redirect_uri = f'http://{local_ip}:5000/callback' if not vercel_url else f'https://{vercel_url}/callback'

scope = 'playlist-read-private user-read-currently-playing user-modify-playback-state user-read-playback-state app-remote-control user-read-recently-played'  # more scopes do this - scope = 'playlist-read-private,streaming'. so basically add a comma

cache_handler = FlaskSessionCacheHandler(session)
sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_handler=cache_handler,
    show_dialog=True
)
sp = Spotify(auth_manager=sp_oauth)

@app.route('/')
def home():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    return redirect(url_for('get_playlists'))

@app.route('/callback')
def callback():
    sp_oauth.get_access_token(request.args['code'])
    return redirect((url_for('get_playlists')))

@app.route('/get_playlists')
def get_playlists():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)

    playlists = sp.current_user_playlists()
    playlists_info = []

    current_playback = sp.current_playback()
    if current_playback:
        for pl in playlists['items']:
            name = pl['name']
            image_url = None
            playlist_uri = pl['uri']
            if pl.get('images'):
                image_url = pl['images'][0]['url']
                playlists_info.append({'name': name, 'image_url' : image_url,'playlist_uri' : playlist_uri})

        #playlists_info.sort(key=lambda x: x['image_url'])
        #return playlists_html
    return render_template('MainPage.html', playlists=playlists_info)

@app.route('/get_current_song')
def get_current_song():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)

    current_song_name = []
    album_image_url = []
    song_total_duration = []

    current_playback = sp.current_playback()
    if current_playback:
        current_song_details = sp.currently_playing()
        if current_song_details and current_song_details.get('item'):
            current_song_name = current_song_details['item']['name']
            song_total_duration = current_song_details['item']["duration_ms"]
            album_image_url = current_song_details['item']['album']['images'][0]['url']

        else:
            current_song_name = "No song playing"
            album_image_url = "Default image URL or fallback"

    return jsonify({'current_song_name': current_song_name,'album_image_url': album_image_url, 'song_total_duration': song_total_duration})

@app.route('/starting_playback_state')
def get_starting_playback_state():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)

    status = ""
    current_playback = sp.current_playback()
    if current_playback and current_playback.get('is_playing'):
        return jsonify({'status': 'pause'})
    else:
        return jsonify({'status': 'play'})

@app.route('/play_pause', methods =['POST'])
def play_pause():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)

    current_playback = sp.current_playback()


    if current_playback and current_playback.get('is_playing'):
        sp.pause_playback()
        return jsonify({'status': 'pause'})
    else:
        sp.start_playback()
        return jsonify({'status': 'play'})

@app.route('/start_playlist', methods=['POST'])
def start_playlist():
    if request.method == 'POST':
        #print("reguest form: " + str(request.form))
        bar = request.form.get('playlist_uri')

        if bar: #sees if it exists
            sp.start_playback(context_uri=bar)
        else:
            return "Error: Playlist URI not found"
    return redirect((url_for('get_playlists')))

@app.route('/song_related_time_items', methods=['POST'])
def song_related_time_items():
    current_song_details = sp.currently_playing()

    if current_song_details is not None:
        song_completion_seconds = float(current_song_details["progress_ms"]) / 1000
        song_length_seconds = float(current_song_details['item']["duration_ms"]) / 1000

        song_completion = strftime("%M:%S", gmtime(song_completion_seconds))
        song_Total_length = strftime("%M:%S", gmtime(song_length_seconds))
        if song_completion_seconds != 0:
            progressOfSong = (song_completion_seconds/song_length_seconds)*100
            #print(progressOfSong)
        else:
            progressOfSong = 0
        return jsonify({'song_completion': song_completion,'song_Total_length': song_Total_length,'progressOfSong': progressOfSong})
    else:
        return jsonify({'song_completion': '0:00','song_Total_length' : "0:00", 'progressOfSong':"0"}), 400

@app.route('/rewindOrSkip', methods=['POST'])
def previous_song():

    bar = request.form.get('rewindOrSkip')
    #print(bar)
    if bar == "rewind":
        sp.previous_track()
        return redirect(url_for('get_playlists'))
    if bar == "skip":
        sp.next_track()
        return redirect(url_for('get_playlists'))

@app.route('/enableDisableShuffle', methods=['POST'])
def enableDisableShuffle():
    current_playback = sp.current_playback()
    context = current_playback['context']

    if current_playback and 'shuffle_state' in current_playback:
        shuffle_enabled = current_playback['shuffle_state']

        bar = request.form.get('setShuffleState')
        print(bar)
        print("shuffle_enabled: " + str(shuffle_enabled))
        if bar == "startingState":
            print("here?1")
            if shuffle_enabled == False:
                print("shuffle start disabled!")
                return jsonify({'shuffleState': "false"})
            else:
                print("shuffle start enabled!")
                return jsonify({'shuffleState': "true"})

        elif bar == None:
            print("here?2")
            if shuffle_enabled:
                print("here?3")
                sp.shuffle(False)
                return jsonify({'shuffleState': False})

            else:
                print("here?4")
                sp.shuffle(True)
                return jsonify({'shuffleState': True})

    else:
        print("Shuffle state not available")
        return jsonify({'shuffleState':'XX'}),403

    return jsonify({'shuffleState': 'XX'}),403

@app.route('/set_repeat_song_state', methods=['POST'])
def repeatModeSetup():
    current_playback = sp.current_playback()

    if current_playback and 'repeat_state' in current_playback:
        current_repeat_state = current_playback['repeat_state']
        context = current_playback['context']

        bar = request.form.get('setRepeatState')
        print(current_repeat_state)
        if bar == "startingState":
            return jsonify({'repeatState': current_repeat_state})
        elif bar == None and context is not None:
            print("here1")
            if current_repeat_state == "track":
                print("here2")
                sp.repeat("context")
                print("here5")
                return jsonify({'repeatState': "context"})

            elif current_repeat_state == "context":
                print("here3")
                sp.repeat("off")
                print("here5")
                return jsonify({'repeatState': "off"})
            elif current_repeat_state == "off":
                print(context['type'])
                sp.repeat("track")
                print("here5")
                return jsonify({'repeatState': "track"})

    else:
        print("replay state not available")
        return jsonify({'repeatState':'XX'}),403

    return jsonify({'replayState': 'Error'}), 400


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    #app.run(debug=True)

