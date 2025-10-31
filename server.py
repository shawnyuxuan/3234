import os
import threading
import sys
import socket

users = {}
user_passwd = {}
threads = []
ROOM_COUNT = 10
rooms = [[i+1, 0, {}, threading.Event()] for i in range(ROOM_COUNT)] # room id, count, user1, user2


def play_game(user, socket, event: threading.Event):
    pass


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
            room_info = [str(rooms[i][1]) for i in range(ROOM_COUNT)]
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
                if room[1] == 0:
                    # 3011 wait
                    users[current_user] = room_no
                    room[1] += 1
                    room[2][current_user] = None
                    connectionSocket.send("3011 Wait".encode())
                    room[3].wait()
                    connectionSocket.send("3012 Game started. Please guess true or false".encode())
                    play_game(current_user, connectionSocket, room[3])
                    continue # daoshihouzaishuoba
                elif room[1] == 1:
                    # 3012
                    users[current_user] = room_no
                    room[1] += 1
                    room[2][current_user] = None
                    room[3].set()
                    connectionSocket.send("3012 Game started. Please guess true or false".encode())
                    play_game(current_user, connectionSocket, room[3])
                    continue

                elif room[1] == 2:
                    # 3013
                    connectionSocket.send("3013 The room is full".encode())
                    continue



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
    print(user_passwd)

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