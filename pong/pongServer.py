# =================================================================================================
# Contributing Authors:     Chenxiang Jiang (CJ), Holden Kennedy (HK), Omar Ellala
# Email Addresses:          cji233@uky.edu, hlke229@uky.edu, Omar.Ellala@uky.edu     ?
# Date:                     11/24/2026

# Purpose:                  Implemented client-server communication for passing player inputs
#                           in the multiplayer Pong game. Sends paddle positions and movement
#                           commands (UP, DOWN, NOP) using TCP sockets and JSON. Also handles
#                           receiving, parsing, and storing game information to support
#                           synchronization between players.

# Concept Overview:         The Server acts as a middle man for all data. The players have their
#                           imputs severed from their own game so that no player directly 
#                           interacts with their screen. The inputs are instead sent to the server
#                           which collects inputs from both and then sends both players inputs to 
#                           each other. The server also collects information regarding their sync 
#                           value, ball location, etc and uses that to constantly tweak the games
#                           for both parties. The core concept is that whatever you see on your 
#                           screen is representative of what the server sent to both parties, there
#                           is not a sync issue between what your screen displays and what the 
#                           oppenents displays under decent conditions due to the forced delay.
             
# Misc:                     Used threading and message buffering to prevent network operations
#                           from interrupting gameplay. Uses code from socket programming 
#                           lectures early in this project as a starting place and some code
#                           elements remain, particularly example 6. Some comments that were
#                           given as guidence from the project assignemtn have remained. Debugging
#                           and information providng code such as print statements containing 
#                           positions etc has been left aswell.
# =================================================================================================


import socket
import threading
import select #HK: added for select.select() used in programming example
import json
import time # HK: Used to add a delay between the join sever information and sending the num clients. 
from turtle import left

# Use this file to write your server logic
# You will need to support at least two clients
# You will need to keep track of where on the screen (x,y coordinates) each paddle is, the score 
# for each player and where the ball is, and relay that to each client
# I suggest you use the sync variable in pongClient.py to determine how out of sync your two
# clients are and take actions to resync the games

# HK: constant for the screen width and height
screenWidth:int = 800
screenHeight:int = 600


# OE: Pull the IP address and port number from the user from the other function
#   Push it into a queue
#   When the queue has two items, pop them and start a new thread for each client
#   Assume socket is using AF_INET (IPv4) and SOCK_STREAM (TCP)
#   Once the two clients are connected, they will be pushed into 
#   a new thread that will handle the game logic for those two clients
waitingClients = []
def handleMultiple(cliConn, addr):
    waitingClients.append([cliConn, addr])
    if len(waitingClients) < 2:
        print( "Waiting for another client to connect...")
        cliConn.send(1)
        return
    newGame = threading.Thread(target = testThread, args = (waitingClients[0], waitingClients[1]), daemon = False)
    newGame.start()
    waitingClients.pop()
    waitingClients.pop()
    return


def testThread(player1, player2):
    print(player1)
    print(player2)
    


# HK: Variables to use to know if the number of clients 
NumClients:int = 0

# ?: Initialize the paddle positions, player inputs, and ball position
paddle_positions = {
    "left": 300,
    "right": 300
}
player_inputs = {
    "left": "NOP",
    "right": "NOP"
}
ball_position:float = [screenWidth // 2, screenHeight // 2]


# HK: Dictionary for the ball and score, uses the same format as the inputs
game_state = {
    "sync": 0,
    "ball_x": 400,
    "ball_y": 300,
    "ball_vx": -5,
    "ball_vy": 0,
    "lScore": 0,
    "rScore": 0
}


# HK: A variable to decide if players agree to a rematch. 
RematchRequestVar = set()


# HK: I created this function as empty
# CJ: 
def UseDataFromClient(addr, data):
    try:
        message = json.loads(data)
    except json.JSONDecodeError:
        print("Could not parse message:", repr(data))
        return

    if message.get("type") == "paddle":
        side = message.get("side")
        paddle_y = message.get("paddle_y")
        input_command = message.get("input", "NOP")

        # HK: Updates the ball position. Does this by use the paddle with a higher sync as the true position. 
        #   This works due to the sync variable manipulation. When a paddle hits the ball "it's" sync value is increased by 5.
        #   This causes the "true" ball position to be from the player who has the most interaction with teh ball. 
        client_sync = message.get("sync", 0)
        if client_sync > game_state["sync"]:
            game_state["sync"] = client_sync
            game_state["ball_x"] = message.get("ball_x", game_state["ball_x"])
            game_state["ball_y"] = message.get("ball_y", game_state["ball_y"])
            game_state["ball_vx"] = message.get("ball_vx", game_state["ball_vx"])
            game_state["ball_vy"] = message.get("ball_vy", game_state["ball_vy"])
            game_state["lScore"] = message.get("lScore", game_state["lScore"])
            game_state["rScore"] = message.get("rScore", game_state["rScore"])

        if side in player_inputs:
            if input_command in ("UP", "DOWN", "NOP"):
                player_inputs[side] = input_command

            if isinstance(paddle_y, int):
                paddle_positions[side] = max(0, min(550, paddle_y))

            #print("Combined player inputs:", player_inputs)
            #print("Combined paddle positions:", paddle_positions)


    # HK: An alternative "if" branch for deciding a rematch. Uses the input system for the paddle movement. p = "Rematch"
    elif message.get("action") == "Rematch":
        side = message.get("side")

        # HK: Both sides have to agree.
        if side in ("left", "right"):
            RematchRequestVar.add(side)

            print(f"Rematch requested by {side}. Total: {len(RematchRequestVar)}") #Prints info on the decision

            if len(RematchRequestVar) >= 2:
                RematchRequestVar.clear() # HK: Reset for next game

                # HK: After testing reseting sync to 0 can cause a race condition where one game is reset but the
                #      other sends an update with a higher sync and causes the already reset game to gain the old values.
                #      by adding to the sync value and sending both the new variable the one that clears first will have  
                #      the higher sync. This should fix the issue, change 100 to a higher value is problem persists.
                IncreasedSync:int = game_state["sync"] + 100


                #HK: By reseting all values the game is effectively reset. This resets all except sync for the reason 
                #   listed above
                game_state.update({
                    "sync": IncreasedSync,
                    "ball_x": 400,
                    "ball_y": 300,
                    "ball_vx": -5,
                    "ball_vy": 0,
                    "lScore": 0,
                    "rScore": 0
                })

                return True # HK: Both players agree

    return False



# HK: My inital work started using code from the Socket Programming lectures. Particularly Example 6.

HOST = "0.0.0.0" # "127.0.0.1" # HK: All 0 = Local network.
PORT = 5000

# Lecture: create TCP server socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen()

# Lecture: list of sockets to monitor for reading
inputs = [server_socket]
buffers = {}

print(f"Server listening on {HOST}:{PORT}")

while True:
    readable, _, _ = select.select(inputs, [], [], 1)
    for s in readable:
        if s is server_socket:
            # new client
            conn, addr = server_socket.accept()
            print(f"[NEW CONNECTION] {addr}")
            inputs.append(conn)
            buffers[conn] = ""

            # HK: Assign Left or Right paddle
            if NumClients%2 == 0:      # HK: Mod 2 so that if we have multiple clients we can use this for another game. 
                PaddleSide = "left"
            else:
                PaddleSide = "right"

            NumClients+= 1 # HK: Updating Variable.

            # HK: Send required info for playgame function in pongClient.py, values are hard coded when possible
            conn.send(f"{screenWidth},{screenHeight},{PaddleSide}".encode()) # Hard Coded. 

            # HK: Unsure if this is needed, it should help sync the games, splits the starting the playgame function and drawing/starting the game.
            time.sleep(1/120) #HK: Half a frame. Not noticable. 

            # HK,OE,CJ: Loops through all connectsion in the array and sends the number of clients. 
            #   Must be done since the server connects using the same port and then reassigns the clients. Looping is easiest.
            for connection in inputs[1:]:
                try:
                    connection.sendall(f"{NumClients}".encode())
                #For connection Failures. 
                except OSError as e:
                    print("Error sending update:", e)
            #conn.send(f"{NumClients}".encode())

        
        else:
            # ?: message from existing client
            data = s.recv(1024)

            if not data:
                print("[DISCONNECTED]")
                inputs.remove(s)
                buffers.pop(s, None)
                s.close()

                NumClients -= 1

            else:
                buffers[s] += data.decode("utf-8")

                while "\n" in buffers[s]:
                    message, buffers[s] = buffers[s].split("\n", 1)

                    # HK: Gets the packet from the client when they press "p"
                    if message: 
                        # HK: Changed to an if so it doesn't constantly change the RestartGam Boolean
                        if UseDataFromClient(s.getpeername(), message):
                            RestartGame = True 

                #HK: While looking through the server code I realized this if statment is in the while loop.
                #   Since the while loop can go infinetly if it gets a bunch of messages I split them. I 
                #   Will undo if it doesn't fix the current desync problem when testing.
                if message:
                    #print("Received:", message) #Debug
                    
                    # ?: This is the parsed data assigned to variables. 
                    update = {
                        "type": "paddles",
                        "left_y": paddle_positions["left"],
                        "right_y": paddle_positions["right"],
                        "left_input": player_inputs["left"],
                        "right_input": player_inputs["right"],
                        "RematchRequestVar": len(RematchRequestVar), #HK: The rematch information must be shared aswell.
                        "restart": RestartGame,
                        **game_state  #HK: Add game state into this update message. 
                    }

                    outgoing = (json.dumps(update) + "\n").encode("utf-8")

                    for connection in inputs[1:]:
                        try:
                            connection.sendall(outgoing)
                        except OSError as e:
                            print("Error sending update:", e)

                    #print("SENT PADDLES:", update) #Debug




