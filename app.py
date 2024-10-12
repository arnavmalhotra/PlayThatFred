import re
from flask import Flask, request, jsonify, send_file, session, render_template
import os
import random
from mutagen.mp3 import MP3
from pydub import AudioSegment
from io import BytesIO
from difflib import SequenceMatcher

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configure directories
SONG_DIRECTORY = 'Music'
ALBUM_DIRECTORY = 'Albums'
SET_DIRECTORY = 'Sets'

DURATIONS = [1, 2, 5, 10, 15, 30]

def load_music_data():
    songs = [f[:-4] for f in os.listdir(SONG_DIRECTORY) if f.endswith('.mp3')]
    albums = {
        album: [f[:-4] for f in os.listdir(os.path.join(ALBUM_DIRECTORY, album))]
        for album in os.listdir(ALBUM_DIRECTORY)
    }
    sets = [f[:-4] for f in os.listdir(SET_DIRECTORY) if f.endswith('.mp3')]
    return songs, albums, sets

SONGS, ALBUMS, SETS = load_music_data()

def normalize_text(text):
    """Remove punctuation, extra spaces, and make the text lowercase."""
    return re.sub(r'[^\w\s]', '', text).strip().lower()

def get_random_clip(directory, duration):
    song_file = random.choice([
        os.path.join(root, file)
        for root, _, files in os.walk(directory)
        for file in files if file.endswith('.mp3')
    ])
    audio = MP3(song_file)
    song_length = int(audio.info.length)

    if song_length <= duration:
        start_time = 0
    else:
        start_time = random.randint(0, song_length - duration)

    return song_file, start_time, os.path.basename(song_file)[:-4]

def is_partial_match(guess, correct_answer, threshold=0.9):
    normalized_guess = normalize_text(guess)
    correct_parts = [normalize_text(part) for part in correct_answer.split('(')]
    for part in correct_parts:
        if SequenceMatcher(None, normalized_guess, part).ratio() >= threshold:
            return True
    return False

@app.route('/play', methods=['GET'])
def play_random_clip():
    game_mode = request.args.get('mode', 'song')
    duration = int(request.args.get('duration', 10))

    if duration not in DURATIONS:
        return jsonify({'error': 'Invalid duration'}), 400

    if game_mode == 'song':
        song_file, start_time, answer = get_random_clip(SONG_DIRECTORY, duration)
    elif game_mode == 'album':
        album = random.choice(list(ALBUMS.keys()))
        song_file, start_time, answer = get_random_clip(os.path.join(ALBUM_DIRECTORY, album), duration)
        session['correct_album'] = album
    elif game_mode == 'set':
        song_file, start_time, answer = get_random_clip(SET_DIRECTORY, duration)
    else:
        return jsonify({'error': 'Invalid game mode'}), 400

    session['correct_answer'] = answer
    audio = AudioSegment.from_mp3(song_file)
    clip = audio[start_time * 1000:(start_time + duration) * 1000]

    buffer = BytesIO()
    clip.export(buffer, format="mp3")
    buffer.seek(0)

    return send_file(buffer, as_attachment=False, download_name="clip.mp3", mimetype="audio/mp3")

@app.route('/guess', methods=['POST'])
def guess():
    if 'correct_answer' not in session:
        return jsonify({'result': 'No active game! Play a clip first.'}), 400

    guess = request.json.get('guess', '').strip().lower()
    mode = request.json.get('mode', 'song')
    correct_answer = session.pop('correct_answer', '').strip()

    if is_partial_match(guess, correct_answer):
        update_score(1)
        result = 'Correct!'
    else:
        reset_score()
        result = f'Incorrect. Correct Answer: {correct_answer}'

    return jsonify({'result': result, 'score': session.get('score', 0)})

def update_score(points):
    if 'score' not in session:
        session['score'] = 0
    session['score'] += points

@app.route('/reset-score', methods=['POST'])
def reset_score():
    session['score'] = 0
    return jsonify({'result': 'Score reset!', 'score': 0})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
