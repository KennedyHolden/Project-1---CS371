# =================================================================================================
# Contributing Authors:	    Holden Kennedy  ,
# Email Addresses:          hlke229@uky.edu , 
# Date:                     11/7/2026
# Purpose:                  This is the server code. It will handle all server responsibilities including receiving and echoing data. 
# Misc:                     <Not Required.  Anything else you might want to include>
# =================================================================================================

import socket
import threading
import select #added for select.select()

# Use this file to write your server logic
# You will need to support at least two clients
# You will need to keep track of where on the screen (x,y coordinates) each paddle is, the score 
# for each player and where the ball is, and relay that to each client
# I suggest you use the sync variable in pongClient.py to determine how out of sync your two
# clients are and take actions to resync the games

# Pull the IP address and port number from the user from the other function
# Push it into a queue
# When the queue has two items, pop them and start a new thread for each client
# Assume socket is using AF_INET (IPv4) and SOCK_STREAM (TCP)
# Once the two clients are connected, they will be pushed into 
# a new thread that will handle the game logic for those two clients
waitingClients = []
def handleMultiple(cliConn, addr):
    waitingClients.append([cliConn, addr])
    if len(waitingClients) < 2:
        return
    newGame = threading.Thread(target = testThread, args = (waitingClients[0], waitingClients[1]), daemon = False)
    newGame.start()
    waitingClients.pop()
    waitingClients.pop()
    return


def testThread(player1, player2):
    print(player1)
    print(player2)
    


# First start, I am using the code from part 2, exmp 6 from the socket lectures.

# A boolean to use to know if the connection is left or right. 
LeftPaddle:int = 0
NumClients:int = 0

def UseDataFromClient(addr, data):
    # We can add logic to use the data the server gets.
    return


# /*
HOST = "127.0.0.1"
PORT = 5000

# create TCP server socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen()

# list of sockets to monitor for reading
inputs = [server_socket]

print(f"Server listening on {HOST}:{PORT}")

while True:
    readable, _, _ = select.select(inputs, [], [], 1)
    for s in readable:
        if s is server_socket:
            # new client
            conn, addr = server_socket.accept()
            print(f"[NEW CONNECTION] {addr}")
            inputs.append(conn)

            # Assign Left or Right paddle
            if NumClients%2 == 0:      # Mod 2 so that if we have multiple clients we can use this for another game. 
                PaddleSide = "left"
            else:
                PaddleSide = "right"

            NumClients+= 1 # Updating Variable.

            # Send required info for playgame function in pongClient.py
            conn.send(f"800,600,{PaddleSide}".encode()) # Hard Coded. 

        else:
            # message from existing client
            data = s.recv(1024)
            if not data:
                # This will happen if the connection breaks.
                # Will need a reconnection function if it happens often
                print("[DISCONNECTED]")
                inputs.remove(s)
                s.close()

                NumClients -= 1 #Update Variable
            else:
                print("Received:", data.decode())

                # Ths is an empty function that can be updated later. 
                UseDataFromClient(s.getpeername(), data.decode())
                s.send(b"Echo: " + data)


# */


