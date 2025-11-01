import socket
import sys

DEFAULT_SERVER_IP = "localhost"
DEFAULT_PORT = 9999
MAX_RECURSION_DEPTH = 5

state = "OUT" #"HALL", "WAIT", "GAMING"

def client_loop(sock: socket.socket):
    state = "OUT"
    """User Authentication"""
    while True:
        username = input("Please input your username: ").strip()
        password = input("Please input your password: ").strip()
        login_command = f"/login {username} {password}"
        sock.send(login_command.encode())
        
        response = sock.recv(1024).decode()
        if response is None:
            print("Failed to retrieve from the server.")
            continue
        
        if response.startswith("1001"):
            print("Authentication successful! Bringing you into the hall...")
            break
        elif response.startswith("1002"):
            print("Authentication failed.")
        elif response.startswith("1003"):
            print("You have logged in elsewhere.")
        else:
            print("Internal error.")
    
    """Playing stage"""
    while True:
        state = "HALL"
        command = input("Command: ")
        arguments = command.split()
        if arguments == []: continue
        cmd = arguments[0]
        match cmd:
            case "/exit":
                sock.send("/exit".encode())
                response = sock.recv(1024).decode()
                if response.startswith("4002"):
                    print("Invalid command.")
                    continue
                if response.startswith("4001"): # Should be fine
                    return
                
            case "/enter":
                if state != "HALL":
                    print("Invalid command.")
                    continue
                sock.send(command.encode())
                
                response = sock.recv(1024).decode()
                if response.startswith("4002"):
                    print("Invalid command.")
                    continue

                if response.startswith("3013"):
                    print("The room is full. Try another room.")
                    # Go to next iteration directly.
                    continue
                
                if response.startswith("3011"):
                    print("Waiting for another player to join...")
                    state = "WAIT"
                    # Waiting until the server sends with 3012 message.
                    while True:
                        response = sock.recv(1024).decode()
                        if response.startswith("3012"):
                            break
                
                """Gaming"""
                if response.startswith("3012"):
                    state = "GAMING"
                    guess = input("Game started! Please take a guess (true/false): ")
                    sock.send(f"/guess {guess}".encode())
                    
                    # Wait for result from the server.
                    game_result = None
                    while True:
                        response = sock.recv(1024).decode()
                        if response.startswith("4002"):
                            print("Invalid command.")
                            continue

                        if response.startswith("3021") or\
                            response.startswith("3022") or\
                            response.startswith("3023"):
                                game_result = response[:4]
                                break
                    
                    match game_result:
                        case "3021":
                            print("You won!")
                        case "3022":
                            print("You lost...")
                        case "3023":
                            print("The result is a tie.")
                        case _:
                            print("?")
                
            case "/list":
                if state != "HALL":
                    print("Invalid command.")
                    continue
                sock.send("/list".encode())
                response = sock.recv(1024).decode()
                if response.startswith("4002"):
                    print("Invalid command.")
                    continue

                room_num = int(response.split()[1])
                numbers = response.split()[2:]
                for i in range(room_num):
                    print(f"Room {i+1}: {numbers[i]} players")
            
            case _:
                # It should be discarded at the first place, 
                # though the requirement is for the server to respond with 4002.
                sock.send(cmd.encode())
                response = sock.recv(1024).decode()
                if response.startswith("4002"):
                    print("Invalid command.")
                    continue
                 
if __name__ == "__main__":
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ip = DEFAULT_SERVER_IP if len(sys.argv) < 2 else sys.argv[1]
    port = DEFAULT_PORT if len(sys.argv) < 3 else int(sys.argv[2])
    try:
        client.connect((ip, port))
        print(f"Connected to server at {ip}:{port}")
        client_loop(client)
    except:
        print(f"Failed to connect to server at {ip}:{port}")
        sys.exit(1)
    finally:
        print("Exiting...")
        client.close()  