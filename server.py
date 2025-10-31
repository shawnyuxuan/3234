# server.py

import socket
import threading
import sys
import random

NUM_ROOMS = 10  # Total game rooms

LOGGED_IN_USERS = set()  # Track currently logged in users

def client_handler(client_sock, addr, users, rooms, logged_in_users, lock):
    """
    Handle communication with a connected client.
    Manages authentication, lobby commands, and game play.
    """
    username = None
    state = 'AUTH'       # Can be 'AUTH', 'HALL', 'WAITING', or 'PLAYING'
    current_room = None  # Room number the user is in, or None

    try:
        # === Authentication Phase ===
        while True:
            data = client_sock.recv(1024).decode().strip()
            if not data:
                # Client disconnected unexpectedly
                return
            parts = data.split()
            # Expect format: /login username password
            if len(parts) != 3 or parts[0] != '/login':
                client_sock.sendall("4002 Unrecognized message".encode())
                continue
            _, user, pwd = parts
            if user in users and users[user] == pwd:
                # Reject if this username is already logged in
                with lock:
                    if user in LOGGED_IN_USERS:
                        client_sock.sendall("1003 Already logged in".encode())
                        continue
                # Success
                username = user
                client_sock.sendall("1001 Authentication successful".encode())
                state = 'HALL'
                
                LOGGED_IN_USERS.add(username)
                break
            else:
                client_sock.sendall("1002 Authentication failed".encode())
                # Prompt client again

        # === Main Loop: In Hall or Game ===
        while True:
            data = client_sock.recv(1024).decode().strip()
            if not data:
                # Client disconnected
                break
            parts = data.split()

            if state == 'HALL':
                # Client is in game hall
                if parts[0] == '/list' and len(parts) == 1:
                    # Respond with count of players in each room
                    with lock:
                        counts = [len(rooms[i]) for i in range(NUM_ROOMS)]
                    resp = "3001 " + str(NUM_ROOMS)
                    for c in counts:
                        resp += " " + str(c)
                    client_sock.sendall(resp.encode())

                elif parts[0] == '/enter' and len(parts) == 2:
                    # Attempt to enter a room
                    try:
                        room_no = int(parts[1])
                    except:
                        client_sock.sendall("4002 Unrecognized message".encode())
                        continue
                    if room_no < 1 or room_no > NUM_ROOMS:
                        client_sock.sendall("4002 Unrecognized message".encode())
                        continue
                    with lock:
                        room = rooms[room_no - 1]
                        if len(room) == 0:
                            # First player in room: wait
                            room.append({'username': username, 'socket': client_sock, 'guess': None})
                            current_room = room_no
                            state = 'WAITING'
                            client_sock.sendall("3011 Wait".encode())
                        elif len(room) == 1:
                            # Second player enters: start game
                            room.append({'username': username, 'socket': client_sock, 'guess': None})
                            current_room = room_no
                            start_msg = "3012 Game started. Please guess true or false"
                            # Notify both players
                            try:
                                room[0]['socket'].sendall(start_msg.encode())
                            except:
                                pass
                            client_sock.sendall(start_msg.encode())
                            state = 'PLAYING'
                        else:
                            # Room already has 2 players
                            client_sock.sendall("3013 The room is full".encode())

                elif parts[0] == '/exit' and len(parts) == 1:
                    # Client exits the system
                    client_sock.sendall("4001 Bye bye".encode())
                    break

                else:
                    # Invalid command in hall
                    client_sock.sendall("4002 Unrecognized message".encode())

            elif state == 'WAITING':
                # First player waiting for a second
                with lock:
                    room = rooms[current_room - 1]
                if len(room) < 2:
                    # Still waiting, ignore commands
                    client_sock.sendall("4002 Unrecognized message".encode())
                    continue
                # Second player has joined, start game
                state = 'PLAYING'
                # No break; fall through to PLAYING logic

            if state == 'PLAYING':
                # Game in progress for this room
                # Check partner presence (for disconnection)
                with lock:
                    room = rooms[current_room - 1] if current_room else []
                if len(room) < 2:
                    # Partner left; return this player to hall
                    state = 'HALL'
                    current_room = None
                    continue

                # Process guess command
                if parts[0] == '/guess' and len(parts) == 2:
                    guess_val = parts[1].lower()
                    if guess_val not in ('true', 'false'):
                        client_sock.sendall("4002 Unrecognized message".encode())
                        continue
                    guess_bool = (guess_val == 'true')
                    with lock:
                        # Record this player's guess
                        for player in room:
                            if player['username'] == username:
                                player['guess'] = guess_bool
                        # If both have guessed, decide outcome
                        if len(room) == 2 and room[0]['guess'] is not None and room[1]['guess'] is not None:
                            p1 = room[0]
                            p2 = room[1]
                            g1 = p1['guess']
                            g2 = p2['guess']
                            # Reset guesses for next game
                            p1['guess'] = None
                            p2['guess'] = None
                            if g1 == g2:
                                # Tie
                                try:
                                    p1['socket'].sendall("3023 The result is a tie".encode())
                                except:
                                    pass
                                try:
                                    p2['socket'].sendall("3023 The result is a tie".encode())
                                except:
                                    pass
                            else:
                                # Determine random outcome
                                random_truth = random.choice([True, False])
                                if g1 == random_truth:
                                    try:
                                        p1['socket'].sendall("3021 You are the winner".encode())
                                    except:
                                        pass
                                    try:
                                        p2['socket'].sendall("3022 You lost this game".encode())
                                    except:
                                        pass
                                else:
                                    try:
                                        p2['socket'].sendall("3021 You are the winner".encode())
                                    except:
                                        pass
                                    try:
                                        p1['socket'].sendall("3022 You lost this game".encode())
                                    except:
                                        pass
                            # Game over, clear room
                            rooms[current_room - 1] = []
                            state = 'HALL'
                            current_room = None
                else:
                    # Not a guess command
                    client_sock.sendall("4002 Unrecognized message".encode())

    except Exception as e:
        # An error or disconnect has occurred
        pass
    finally:
        client_sock.close()
        # Cleanup: remove user from logged in users and from room
        if username:
            with lock:
                LOGGED_IN_USERS.remove(username)
        if current_room:
            with lock:
                room = rooms[current_room - 1]
                for player in list(room):
                    if player['username'] == username:
                        room.remove(player)
                if len(room) == 1:
                    # Other player wins by default
                    other = room[0]
                    try:
                        other['socket'].sendall("3021 You are the winner".encode())
                    except:
                        pass
                    rooms[current_room - 1] = []
                    
def main():
    if len(sys.argv) != 3:
        print("Usage: python server.py <port> <UserInfo.txt>")
        sys.exit(1)
    port = int(sys.argv[1])
    user_file = sys.argv[2]
    # Load user credentials into a dictionary
    users = {}
    try:
        with open(user_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or ':' not in line:
                    continue
                user, pwd = line.split(':', 1)
                users[user] = pwd
    except FileNotFoundError:
        print(f"User info file not found: {user_file}")
        sys.exit(1)
    # Initialize game rooms (each room holds a list of players)
    rooms = [[] for _ in range(NUM_ROOMS)]
    logged_in_users = set()  # Track currently logged in users
    lock = threading.Lock()
    # Set up server socket
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(('', port))
    server_sock.listen(5)
    print(f"Server listening on port {port}")
    try:
        while True:
            client_sock, addr = server_sock.accept()
            # Spawn a new thread for each client
            thread = threading.Thread(target=client_handler,
                                      args=(client_sock, addr, users, rooms, logged_in_users, lock))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("Server shutting down.")
    finally:
        server_sock.close()

if __name__ == "__main__":
    main()
