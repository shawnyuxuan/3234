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
        self.user_count_lock = threading.Lock()
        self.game_lock = threading.Lock()
        self.received_guesses = 0
        self.server_answer = None
        self.barrier = threading.Barrier(2)



users = {}
#TODO: 处理client意外退出的情况：更新users
user_passwd = {}
threads = []
ROOM_COUNT = 10
rooms = [Room(i+1) for i in range(ROOM_COUNT)] # room id, count, user1, user2

# TODO dict thread safety????
def calculate_game_result(user, room_no):
    room = rooms[room_no-1]
    print(room.user_guess)
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

    print(room.user_guess[user])
    # handle normal case
    if room.user_guess[user1] == room.user_guess[user2]:
        return "tie"
    else:
        with room.game_lock:
            if room.server_answer is None:
                room.server_answer = random.choice(["true", "false"])
        if room.user_guess[user] == room.server_answer:
            print(user, "guesses", room.user_guess[user], "answer is", room.server_answer, "return true")
            return True
        else:
            print(user, "guesses", room.user_guess[user], "answer is", room.server_answer, "return false")
            return False



def play_game(user, connectionSocket, room_no):
    # game result is determined here, and returned
    room = rooms[room_no-1]
    print(room.user_guess)
    while True:
        line = receive_message(connectionSocket)
        if line is None:
            room.user_guess[user] = "user_offline"
            break
            # return False
        # line = line.decode()
        try:
            line = line.split()
            if len(line) != 2 or line[0] != "/guess" or line[1] not in {"true", "false"}:
                connectionSocket.send("4002 Unrecognized message".encode())
                continue
            room.user_guess[user] = line[1]
            break

        except OSError:
            # socket closed
            room.user_guess[user] = "user_offline"
            break
            # return False

    with room.game_lock:
        room.received_guesses += 1
        # for backward compatibility

    room.barrier.wait()
    return calculate_game_result(user, room_no)



def clear_room(room_no, current_user):
    room = rooms[room_no-1]
    room.barrier.wait()
    del room.user_guess[current_user]
    users[current_user] = 0
    with room.user_count_lock:
        room.received_guesses = 0
        room.user_count = 0
        room.server_answer = None


# def send_message():


def handle_result(result, connectionSocket, current_user, room_no):
    # send result + close room
    room = rooms[room_no-1]

    if result == "tie":
        clear_room(room_no, current_user)
        if send_message(connectionSocket, "3023 The result is a tie") is None:
            return "user force quit"

    else:
        if result:
            clear_room(room_no, current_user)
            if send_message(connectionSocket, "3021 You are the winner") is None:
                return "user force quit"

        else:
            clear_room(room_no, current_user)
            if send_message(connectionSocket, "3022 You lost this game") is None:
                return "user force quit"


def login(connectionSocket):
    while True:
        line = receive_message(connectionSocket)
        if line is None:
            break
        line = line.split()
        if len(line) != 3:
            if send_message(connectionSocket, "4002 Unrecognized message") is None:
                break
            continue
        command, user, passwd = line

        if command != "/login":
            if send_message(connectionSocket, "4002 Unrecognized message") is None:
                break
            continue

        if user in users:
            if send_message(connectionSocket, "You have already logged in") is None:
                break
            continue

        if user in user_passwd and passwd == user_passwd[user]:
            if send_message(connectionSocket, "1001 Authentication successful") is None:
                break
            users[user] = 0 # room id that a user is in
            return user
        else:
            if send_message(connectionSocket, "1002 Authentication failed") is None:
                break
    return None



def receive_message(connectionSocket) -> None| str:
    try:
        line = connectionSocket.recv(1024)
        if not line:
            connectionSocket.close()
            return None # client closed the loop using close()
        return line.decode()

    except OSError:
        # client force close
        return None


def send_message(connectionSocket, message):
    try:
        connectionSocket.send(message.encode())
        return True
    except OSError:
        return None


def handle_client(client):
    connectionSocket, addr = client

    result = login(connectionSocket)
    if result is None:
        connectionSocket.close()
        return # client closed the socket
    current_user = result

    while True:
        line = receive_message(connectionSocket)
        if line is None:
            break

        if line.startswith("/list"):
            if line != "/list":
                if send_message(connectionSocket, "4002 Unrecognized message") is None:
                    break
                continue

            message = f"3001 {ROOM_COUNT} "
            room_info = []
            for i in range(ROOM_COUNT):
                room = rooms[i]
                with room.user_count_lock:
                    room_info.append(str(rooms[i].user_count))
            message += " ".join(room_info)
            if send_message(connectionSocket, message) is None:
                break
        elif line.startswith("/enter"):
            line = line.split(" ")
            if len(line) != 2:
                if send_message(connectionSocket, "4002 Unrecognized message") is None:
                    break
                continue
            elif line[0] != "/enter":
                if send_message(connectionSocket, "4002 Unrecognized message") is None:
                    break
                continue
            else:
                if users[current_user] != 0:
                    if send_message(connectionSocket, f"You are already in room {users[current_user]}") is None:
                        break
                    continue

            room_no = line[1]
            try:
                room_no = int(room_no)
            except:
                if send_message(connectionSocket, "4002 Unrecognized message") is None:
                    break
                continue


            if room_no > ROOM_COUNT or room_no < 1:
                if send_message(connectionSocket, "4002 Unrecognized message") is None:
                    break
                continue
            else:
                room = rooms[room_no-1]
                should_wait = False
                with room.user_count_lock:
                    if room.user_count == 0:
                        # 3011 wait
                        users[current_user] = room_no
                        room.user_count += 1
                        room.user_guess[current_user] = None
                        if send_message(connectionSocket, "3011 Wait") is None:
                            pass
                        should_wait = True
                    elif room.user_count == 1:
                        # 3012
                        users[current_user] = room_no
                        room.user_count += 1
                        room.user_guess[current_user] = None
                        should_wait = False

                    elif room.user_count == 2:
                        # 3013
                        if send_message(connectionSocket, "3013 The room is full") is None:
                            pass
                        continue
                if should_wait:
                    room.event.wait()
                else:
                    room.event.set()
                print(room.user_guess)
                if send_message(connectionSocket, "3012 Game started. Please guess true or false") is None:
                    pass
                result = play_game(current_user, connectionSocket, room_no)
                if handle_result(result, connectionSocket, current_user, room_no) == "user force quit":
                    break
                continue  # daoshihouzaishuoba


        elif line.strip() == "/exit":
            if send_message(connectionSocket, "4001 Bye Bye") is None:
                break
            if current_user in users:
                del users[current_user]
            connectionSocket.close()
            return
        else:
            if send_message(connectionSocket, "4002 Unrecognized message") is None:
                break

    connectionSocket.close()
    if current_user in users:
        # because there is no double login, this is thread safe (one thread per user)
        del users[current_user]


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