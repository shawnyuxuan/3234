import os
import random
import threading
import sys
import socket

class Room:
    def __init__(self, room_id):
        self.id = room_id
        self.user_count = 0
        self.user_guess = {}
        self.event = threading.Event()
        self.lock = threading.Lock()
        self.received_guesses = 0
        self.server_answer = None
        self.barrier = threading.Barrier(2)



users = {}
#TODO: 处理client意外退出的情况：更新users
user_passwd = {}
threads = []
ROOM_COUNT = 10
rooms = [Room(i+1) for i in range(ROOM_COUNT)] # room id, count, user1, user2


def calculate_game_result(user, room_no):
    room = rooms[room_no-1]
    user1, user2 = room.user_guess

    # handle offline cases, if both offline, both are false
    if user1 == user:
        if room.user_guess[user1] == "user_offline" and room.user_guess[user2] != "user_offline":
            return False
        if room.user_guess[user1] != "user_offline" and room.user_guess[user2] == "user_offline":
            return True
        if room.user_guess[user1] == "user_offline" and room.user_guess[user2] == "user_offline":
            return False
    elif user2 == user:
        if room.user_guess[user1] == "user_offline" and room.user_guess[user2] != "user_offline":
            return True
        if room.user_guess[user1] != "user_offline" and room.user_guess[user2] == "user_offline":
            return False
        if room.user_guess[user1] == "user_offline" and room.user_guess[user2] == "user_offline":
            return False

    # handle normal case
    if room.user_guess[user1] == room.user_guess[user2]:
        return "tie"
    else:
        room.server_answer = random.choice(["true", "false"])
        if room.user_guess[user] == room.server_answer:
            return True
        else:
            return False



def play_game(user, connectionSocket, room_no):
    # game result is determined here, and returned
    room = rooms[room_no-1]
    while True:
        line = connectionSocket.recv(1024)
        if not line:
            room.user_guess[user] = "user_offline"
            break
            # return False
        line = line.decode()
        try:
            line = line.split()
            if len(line) != 2 or line[0] != "/guess" or line[1] not in {"true", "false"}:
                connectionSocket.send("4002 Unrecognized message")
                continue
            room.user_guess[user] = line[1]
            break

        except OSError:
            # socket closed
            room.user_guess[user] = "user_offline"
            break
            # return False

    with room.lock:
        room.received_guesses += 1
        # for backward compatibility

    room.barrier.wait()
    return calculate_game_result(user, room_no)



def clear_room(room_no, current_user):
    room = rooms[room_no-1]
    del room.user_guess[current_user]
    users[current_user] = 0
    room.received_guesses -= 1
    room.user_count -= 1
    room.server_answer = None


# def send_message():


def handle_result(result, connectionSocket, current_user, room_no):
    room = rooms[room_no-1]

    if result == "tie":
        try:
            clear_room(room_no, current_user)
            connectionSocket.send("3023 The result is a tie".encode())
        except OSError:
            # TODO
            print("user exitted")
            connectionSocket.close()
            del users[current_user]

    else:
        if result:
            try:
                clear_room(room_no, current_user)
                connectionSocket.send("3021 You are the winner".encode())
            except OSError:
                # TODO
                print("user exitted")
                connectionSocket.close()
                del users[current_user]

        else:
            try:
                clear_room(room_no, current_user)
                connectionSocket.send("3022 You lost this game".encode())
            except OSError:
                # TODO
                print("user exitted")
                connectionSocket.close()
                del users[current_user]


def login(connectionSocket):
    while True:
        line = connectionSocket.recv(1024)
        if not line:
            # client closed the socket
            connectionSocket.close()
            return None
        line = line.decode()
        line = line.split(" ")
        if len(line) != 3:
            connectionSocket.send("4002 Unrecognized message".encode())
            continue
        command, user, passwd = line

        if command != "/login":
            connectionSocket.send("4002 Unrecognized message".encode())
            continue

        if user in users:
            connectionSocket.send("You have already logged in".encode())
            continue

        if user in user_passwd and passwd == user_passwd[user]:
            connectionSocket.send("1001 Authentication successful".encode())
            users[user] = 0 # room id that a user is in
            return user
        else:
            connectionSocket.send("1002 Authentication failed".encode())



def handle_client(client):
    connectionSocket, addr = client

    result = login(connectionSocket)
    if result is None: return # client closed the socket
    current_user = result

    while True:
        line = connectionSocket.recv(1024)
        if not line:
            connectionSocket.close()
            break # client closed the loop
        line = line.decode()

        if line.startswith("/list"):
            if line != "/list":
                connectionSocket.send("4002 Unrecognized message".encode())
                continue

            message = f"3001 {ROOM_COUNT} "
            room_info = [str(rooms[i].user_count) for i in range(ROOM_COUNT)]
            message += " ".join(room_info)
            connectionSocket.send(message.encode())
        elif line.startswith("/enter"):
            line = line.split(" ")
            if len(line) != 2:
                connectionSocket.send("4002 Unrecognized message".encode())
                continue
            elif line[0] != "/enter":
                connectionSocket.send("4002 Unrecognized message".encode())
                continue
            else:
                if users[current_user] != 0:
                    connectionSocket.send(f"You are already in room {users[current_user]}".encode())
                    continue

            room_no = line[1]
            try:
                room_no = int(room_no)
            except:
                connectionSocket.send("4002 Unrecognized message".encode())
                continue


            if room_no > ROOM_COUNT or room_no < 1:
                connectionSocket.send("4002 Unrecognized message".encode())
                continue
            else:
                room = rooms[room_no-1]
                if room.user_count == 0:
                    # 3011 wait
                    users[current_user] = room_no
                    room.user_count += 1
                    room.user_guess[current_user] = None
                    connectionSocket.send("3011 Wait".encode())
                    room.event.wait()
                    connectionSocket.send("3012 Game started. Please guess true or false".encode())
                    result = play_game(current_user, connectionSocket, room_no)
                    handle_result(result, connectionSocket, current_user, room_no)
                    continue # daoshihouzaishuoba
                elif room.user_count == 1:
                    # 3012
                    users[current_user] = room_no
                    room.user_count += 1
                    room.user_guess[current_user] = None
                    room.event.set()
                    connectionSocket.send("3012 Game started. Please guess true or false".encode())
                    play_game(current_user, connectionSocket, room_no)
                    handle_result(result, connectionSocket, current_user, room_no)
                    continue

                elif room.user_count == 2:
                    # 3013
                    connectionSocket.send("3013 The room is full".encode())
                    continue

        elif line.strip() == "/exit":
            connectionSocket.send("4001 Bye Bye".encode())
            if current_user in users:
                del users[current_user]
            connectionSocket.close()
            return
        else:
            connectionSocket.send("4002 Unrecognized message".encode())



def main ():
    if len(sys.argv) == 2:
        print("no UserInfo.txt specified, searching in current directory")
        cwd = os.getcwd()
        user_info_path = os.path.join(cwd, "UserInfo.txt")
        server_port = int(sys.argv[1])
    elif len(sys.argv) == 3:
        user_info_path = sys.argv[-1]
        server_port = int(sys.argv[1])

    else:
        print("usage: python server.py <port_num> <user_info_path>")
        return

    with open(user_info_path, "r") as f:
        while True:
            line = f.readline().strip()
            if not line:
                break
            user, passwd = line.split(":")
            user_passwd[user] = passwd
    # print(user_passwd)

    serverSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSock.bind(("", server_port))
    serverSock.listen()
    print("server started")
    while True:
        client = serverSock.accept()
        thread = threading.Thread(target=handle_client, args=(client, ))
        thread.start()
        threads.append(thread)



if __name__=="__main__":
    main()