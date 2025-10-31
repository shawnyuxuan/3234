# client.py

import socket
import sys

def main():
    if len(sys.argv) != 3:
        print("Usage: python client.py <server_ip> <server_port>")
        sys.exit(1)
    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((server_ip, server_port))
    except Exception as e:
        print(f"Failed to connect to server: {e}")
        sys.exit(1)
    
    try:
        # === User Authentication ===
        while True:
            username = input("Please input your user name: ").strip()
            password = input("Please input your password: ").strip()
            login_msg = f"/login {username} {password}"
            sock.sendall(login_msg.encode())
            response = sock.recv(1024).decode()
            if not response:
                print("Server closed the connection.")
                sock.close()
                return
            print(response)  # Display server response
            if response.startswith("1001"):
                # Auth successful
                break
            # Otherwise loop to prompt again
        
        # === In Game Hall ===
        while True:
            command = input("Enter command (/list, /enter <room>, /exit): ").strip()
            if not command:
                continue
            parts = command.split()
            cmd = parts[0]
            
            if cmd == "/list" and len(parts) == 1:
                sock.sendall(command.encode())
                data = sock.recv(1024).decode()
                if not data:
                    print("Server closed the connection.")
                    break
                tokens = data.split()
                if tokens[0] == "3001":
                    # Parse and display room counts
                    num_rooms = int(tokens[1])
                    counts = tokens[2:]
                    print("Number of players in each room:")
                    for i, count in enumerate(counts, start=1):
                        print(f"Room {i}: {count}")
                else:
                    print(data)
            
            elif cmd == "/enter" and len(parts) == 2:
                try:
                    room_no = int(parts[1])
                except ValueError:
                    print("Invalid room number.")
                    continue
                sock.sendall(command.encode())
                data = sock.recv(1024).decode()
                if not data:
                    print("Server closed the connection.")
                    break
                print(data)
                tokens = data.split()
                code = tokens[0]
                
                if code == "3011":
                    # Waiting for second player
                    print("Waiting for another player...")
                    data = sock.recv(1024).decode()
                    if not data:
                        print("Server closed the connection.")
                        break
                    print(data)
                    tokens = data.split()
                    code = tokens[0]
                
                if code == "3012":
                    # Game started, prompt for guess
                    while True:
                        guess = input("Enter your guess (true/false): ").strip().lower()
                        if guess in ("true", "false"):
                            break
                        print("Invalid guess. Please enter 'true' or 'false'.")
                    sock.sendall(f"/guess {guess}".encode())
                    result = sock.recv(1024).decode()
                    if not result:
                        print("Server closed the connection.")
                        break
                    print(result)  # 3021, 3022, or 3023
                    # After game, back to hall
                elif code == "3013":
                    # Room was full
                    continue
                else:
                    print(f"Unexpected response: {data}")
            
            elif cmd == "/exit" and len(parts) == 1:
                sock.sendall(command.encode())
                data = sock.recv(1024).decode()
                if data:
                    print(data)  # Expect "4001 Bye bye"
                print("Exiting.")
                break
            
            else:
                print("Invalid command.")
    
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
