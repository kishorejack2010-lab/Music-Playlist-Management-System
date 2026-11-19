"""
TamilBeats - Python Flask Backend Server
Data Structures Project - Music Playlist Management System

Run: python server.py
Then open: http://localhost:5000
"""

from flask import Flask, jsonify, request, send_from_directory, session
import json
import os
import hashlib
from datetime import datetime, date
from collections import deque, defaultdict

app = Flask(__name__, static_folder='.')
app.secret_key = 'tamilbeats_secret_2024'

# ── Data Structures Used ──────────────────────────────────────────────────

class Node:
    """Doubly Linked List Node for Playlist"""
    def __init__(self, song):
        self.song = song
        self.prev = None
        self.next = None


class DoublyLinkedPlaylist:
    """
    Data Structure: Doubly Linked List
    Use: Playlist navigation (prev/next songs)
    Time Complexity: O(1) for prev/next navigation
    """
    def __init__(self):
        self.head = None
        self.tail = None
        self.current = None
        self.size = 0

    def append(self, song):
        node = Node(song)
        if not self.head:
            self.head = self.tail = node
            self.current = node
        else:
            node.prev = self.tail
            self.tail.next = node
            self.tail = node
        self.size += 1
        return node

    def next_song(self):
        if self.current and self.current.next:
            self.current = self.current.next
            return self.current.song
        return None

    def prev_song(self):
        if self.current and self.current.prev:
            self.current = self.current.prev
            return self.current.song
        return None

    def to_list(self):
        result = []
        node = self.head
        while node:
            result.append(node.song)
            node = node.next
        return result


class PlayHistoryStack:
    """
    Data Structure: Stack (using deque)
    Use: Recently played songs history
    Time Complexity: O(1) push/pop
    """
    def __init__(self, max_size=100):
        self.stack = deque(maxlen=max_size)

    def push(self, song_record):
        self.stack.appendleft(song_record)

    def get_recent(self, n=50):
        return list(self.stack)[:n]

    def size(self):
        return len(self.stack)


class SearchTrie:
    """
    Data Structure: Trie (Prefix Tree)
    Use: Fast song/artist search by prefix
    Time Complexity: O(m) search where m = query length
    """
    def __init__(self):
        self.root = {}
        self.songs_map = {}

    def insert(self, word, song_id):
        word = word.lower()
        node = self.root
        for ch in word:
            if ch not in node:
                node[ch] = {}
            node = node[ch]
        if '_ids' not in node:
            node['_ids'] = set()
        node['_ids'].add(song_id)

    def search(self, prefix):
        prefix = prefix.lower()
        node = self.root
        for ch in prefix:
            if ch not in node:
                return set()
            node = node[ch]
        return self._collect_ids(node)

    def _collect_ids(self, node):
        ids = set()
        if '_ids' in node:
            ids.update(node['_ids'])
        for ch, child in node.items():
            if ch != '_ids':
                ids.update(self._collect_ids(child))
        return ids


class PlayTimeTracker:
    """
    Data Structure: Hash Map (defaultdict)
    Use: Track play time per day per user
    Time Complexity: O(1) update and lookup
    """
    def __init__(self):
        self.daily_time = defaultdict(int)   # date -> seconds
        self.daily_count = defaultdict(int)  # date -> song count

    def record_play(self, duration_str):
        today = str(date.today())
        parts = duration_str.split(':')
        secs = int(parts[0]) * 60 + int(parts[1])
        self.daily_time[today] += secs
        self.daily_count[today] += 1

    def get_today_stats(self):
        today = str(date.today())
        total_secs = self.daily_time[today]
        hours = total_secs // 3600
        mins = (total_secs % 3600) // 60
        secs = total_secs % 60
        return {
            'songs': self.daily_count[today],
            'total_seconds': total_secs,
            'display': f'{hours}h {mins}m {secs}s' if hours > 0 else f'{mins}m {secs}s'
        }

    def get_weekly(self):
        from datetime import timedelta
        result = []
        for i in range(7):
            d = str(date.today() - timedelta(days=i))
            result.append({
                'date': d,
                'seconds': self.daily_time[d],
                'songs': self.daily_count[d]
            })
        return result


# ── In-Memory DB ──────────────────────────────────────────────────────────
users_db = {}
playlists_db = {}  # user_id -> DoublyLinkedPlaylist
history_db = {}    # user_id -> PlayHistoryStack
playtime_db = {}   # user_id -> PlayTimeTracker
search_trie = SearchTrie()

# Load artist data
def load_artists():
    data_path = os.path.join(os.path.dirname(__file__), 'js', 'data.js')
    # Return hardcoded sample for demo
    return []

# ── Build Search Index ────────────────────────────────────────────────────
SAMPLE_SONGS = [
    {'id': 101, 'title': 'Roja Janele', 'artist': 'A.R. Rahman', 'album': 'Roja', 'duration': '4:32'},
    {'id': 501, 'title': 'Why This Kolaveri Di', 'artist': 'Anirudh', 'album': '3', 'duration': '3:50'},
    {'id': 801, 'title': 'Rowdy Baby', 'artist': 'Dhanush', 'album': 'Maari 2', 'duration': '3:30'},
]

for song in SAMPLE_SONGS:
    for word in song['title'].split() + song['artist'].split():
        search_trie.insert(word, song['id'])
    search_trie.songs_map[song['id']] = song


# ── Routes ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    if username in users_db:
        return jsonify({'error': 'Username already exists'}), 409
    hashed = hashlib.sha256(password.encode()).hexdigest()
    users_db[username] = {'password': hashed, 'created': datetime.now().isoformat()}
    history_db[username] = PlayHistoryStack()
    playtime_db[username] = PlayTimeTracker()
    playlists_db[username] = DoublyLinkedPlaylist()
    session['user'] = username
    return jsonify({'success': True, 'user': username})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    hashed = hashlib.sha256(password.encode()).hexdigest()
    user = users_db.get(username)
    # Demo: allow any login
    if not user:
        users_db[username] = {'password': hashed, 'created': datetime.now().isoformat()}
        history_db[username] = PlayHistoryStack()
        playtime_db[username] = PlayTimeTracker()
        playlists_db[username] = DoublyLinkedPlaylist()
    session['user'] = username
    return jsonify({'success': True, 'user': username})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({'success': True})

@app.route('/api/play', methods=['POST'])
def record_play():
    user = session.get('user', 'guest')
    data = request.json
    song = data.get('song', {})

    if user not in history_db:
        history_db[user] = PlayHistoryStack()
    if user not in playtime_db:
        playtime_db[user] = PlayTimeTracker()

    record = {
        **song,
        'playedAt': datetime.now().isoformat()
    }
    history_db[user].push(record)
    playtime_db[user].record_play(song.get('duration', '3:00'))

    return jsonify({'success': True})

@app.route('/api/history')
def get_history():
    user = session.get('user', 'guest')
    if user not in history_db:
        return jsonify({'history': [], 'stats': {}})
    h = history_db[user].get_recent(50)
    stats = playtime_db[user].get_today_stats() if user in playtime_db else {}
    return jsonify({'history': h, 'stats': stats})

@app.route('/api/search')
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'results': []})
    ids = search_trie.search(q)
    results = [search_trie.songs_map[i] for i in ids if i in search_trie.songs_map]
    return jsonify({'results': results})

@app.route('/api/playlist/add', methods=['POST'])
def playlist_add():
    user = session.get('user', 'guest')
    if user not in playlists_db:
        playlists_db[user] = DoublyLinkedPlaylist()
    song = request.json.get('song', {})
    playlists_db[user].append(song)
    return jsonify({'success': True, 'size': playlists_db[user].size})

@app.route('/api/playlist/next', methods=['POST'])
def playlist_next():
    user = session.get('user', 'guest')
    pl = playlists_db.get(user)
    if not pl:
        return jsonify({'song': None})
    song = pl.next_song()
    return jsonify({'song': song})

@app.route('/api/playlist/prev', methods=['POST'])
def playlist_prev():
    user = session.get('user', 'guest')
    pl = playlists_db.get(user)
    if not pl:
        return jsonify({'song': None})
    song = pl.prev_song()
    return jsonify({'song': song})

@app.route('/api/stats/weekly')
def weekly_stats():
    user = session.get('user', 'guest')
    if user not in playtime_db:
        return jsonify({'weekly': []})
    return jsonify({'weekly': playtime_db[user].get_weekly()})

@app.route('/api/ds-info')
def ds_info():
    """Return info about data structures used"""
    return jsonify({
        'structures': [
            {
                'name': 'Doubly Linked List',
                'use': 'Playlist (prev/next navigation)',
                'complexity': 'O(1) prev/next'
            },
            {
                'name': 'Stack (deque)',
                'use': 'Play history (recently played)',
                'complexity': 'O(1) push/pop'
            },
            {
                'name': 'Trie (Prefix Tree)',
                'use': 'Search autocomplete',
                'complexity': 'O(m) search'
            },
            {
                'name': 'Hash Map (defaultdict)',
                'use': 'Daily play time tracking',
                'complexity': 'O(1) lookup/update'
            }
        ]
    })


if __name__ == '__main__':
    print("=" * 50)
    print("  TamilBeats Music Server")
    print("  Data Structures: Linked List, Stack, Trie, HashMap")
    print("  Open: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)