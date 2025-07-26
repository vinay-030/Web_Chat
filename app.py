# app.py
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import json
import os
import uuid
import datetime

app = Flask(__name__)
# Enable CORS for all origins to allow frontend to connect
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet') # Use eventlet for better performance with WebSockets

# --- In-memory storage for users and messages (for demonstration purposes) ---
# For a real application, use a database (e.g., SQLite, PostgreSQL, MongoDB, Firestore)
USERS_FILE = 'users.json'
CHATS_FILE = 'chats.json'

def load_data(filename, default_data):
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {filename} is empty or invalid JSON. Initializing with default data.")
            return default_data
    return default_data

def save_data(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

users = load_data(USERS_FILE, {}) # {user_id: {username, email, password}}
chats = load_data(CHATS_FILE, {}) # {chat_id: [{sender_id, message, timestamp}]}

# --- Helper to get a consistent chat ID ---
def get_chat_id(user_id1, user_id2):
    # Sort UIDs to ensure a consistent chat ID regardless of who initiated the chat
    sorted_uids = sorted([user_id1, user_id2])
    return f"chat_{sorted_uids[0]}_{sorted_uids[1]}"

# --- API Endpoints ---

@app.route('/')
def index():
    return "Chat Backend Running!"

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({"message": "Username, email, and password are required"}), 400

    # Check if email already exists
    for user_id, user_data in users.items():
        if user_data['email'] == email:
            return jsonify({"message": "Email already registered"}), 409

    user_id = str(uuid.uuid4())
    users[user_id] = {
        "username": username,
        "email": email,
        "password": password, # In a real app, hash this password!
        "id": user_id # Store ID for easier lookup
    }
    save_data(USERS_FILE, users)
    return jsonify({"message": "Registration successful", "userId": user_id, "username": username}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    for user_id, user_data in users.items():
        if user_data['email'] == email and user_data['password'] == password:
            # In a real app, generate a JWT token here for session management
            return jsonify({"message": "Login successful", "userId": user_id, "username": user_data['username']}), 200
    return jsonify({"message": "Invalid email or password"}), 401

@app.route('/users', methods=['GET'])
def get_all_users():
    current_user_id = request.args.get('currentUserId')
    user_list = []
    for user_id, user_data in users.items():
        if user_id != current_user_id:
            user_list.append({
                "id": user_id,
                "username": user_data['username'],
                "email": user_data['email']
            })
    return jsonify(user_list), 200

@app.route('/delete_account', methods=['POST'])
def delete_account():
    data = request.json
    user_id_to_delete = data.get('userId')

    if not user_id_to_delete:
        return jsonify({"message": "User ID is required"}), 400

    if user_id_to_delete in users:
        del users[user_id_to_delete]
        save_data(USERS_FILE, users)

        # Remove all chats involving this user
        chat_ids_to_remove = []
        for chat_id in chats.keys():
            if user_id_to_delete in chat_id: # Simple check, assumes chat_id format
                chat_ids_to_remove.append(chat_id)

        for chat_id in chat_ids_to_remove:
            del chats[chat_id]
        save_data(CHATS_FILE, chats)

        return jsonify({"message": "Account deleted successfully"}), 200
    else:
        return jsonify({"message": "User not found"}), 404


# --- SocketIO Events ---

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('join_chat')
def handle_join_chat(data):
    user_id = data.get('userId')
    chat_partner_id = data.get('chatPartnerId')
    if not user_id or not chat_partner_id:
        return

    room = get_chat_id(user_id, chat_partner_id)
    join_room(room)
    print(f"User {user_id} joined room {room}")

    # Emit existing messages for this chat room to the joining user
    if room in chats:
        emit('load_messages', chats[room], room=request.sid)

@socketio.on('leave_chat')
def handle_leave_chat(data):
    user_id = data.get('userId')
    chat_partner_id = data.get('chatPartnerId')
    if not user_id or not chat_partner_id:
        return

    room = get_chat_id(user_id, chat_partner_id)
    leave_room(room)
    print(f"User {user_id} left room {room}")

@socketio.on('send_message')
def handle_send_message(data):
    sender_id = data.get('senderId')
    receiver_id = data.get('receiverId')
    message_text = data.get('messageText')
    sender_username = data.get('senderUsername')

    if not sender_id or not receiver_id or not message_text or not sender_username:
        return

    room = get_chat_id(sender_id, receiver_id)
    timestamp = datetime.datetime.now().isoformat()

    message = {
        "senderId": sender_id,
        "senderUsername": sender_username,
        "receiverId": receiver_id,
        "messageText": message_text,
        "timestamp": timestamp
    }

    if room not in chats:
        chats[room] = []
    chats[room].append(message)
    save_data(CHATS_FILE, chats) # Save messages to file

    # Emit message to all clients in the chat room
    emit('receive_message', message, room=room)
    print(f"Message sent in room {room}: {message_text}")

@socketio.on('clear_chat')
def handle_clear_chat(data):
    user_id1 = data.get('userId1')
    user_id2 = data.get('userId2')
    if not user_id1 or not user_id2:
        return

    room = get_chat_id(user_id1, user_id2)
    if room in chats:
        chats[room] = [] # Clear messages for this chat
        save_data(CHATS_FILE, chats)
        emit('chat_cleared', room=room) # Notify clients in the room that chat is cleared
        print(f"Chat room {room} cleared.")


if __name__ == '__main__':
    print("Starting Flask-SocketIO server on http://127.0.0.1:5000")
    socketio.run(app, debug=True, port=5000)
