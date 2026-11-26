# =================================================================================================
# Contributing Authors:     Chenxiang Jiang (CJ), Holden Kennedy (HK), Omar Ellala (OE)
# Email Addresses:          cji233@uky.edu, hlke229@uky.edu, Omar.Ellala@uky.edu
# Date:                     11/26/2026

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
from typing import Tuple # For being able to typehint multiple return variables 

# HK: constant for the screen width and height
screenWidth:int = 800
screenHeight:int = 600

# create TCP server socket and initial server state
HOST:str = "127.0.0.1"
PORT:int = 5000
buffers:dict = {}
server_socket:socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen()
print(f"Server listening on {HOST}:{PORT}")

# Author: Chenxiang Jiang, Holden Kennedy 
# Purpose: Parses incoming JSON messages and updates the corresponding player data. 
# Pre: A game has already started between two clients and the incoming message is a valid set of bytes and that include the 
#   paddle_positions, player_inputs, the current game state, and the set of players that are requesting a rematch
# Post: Returns both player's paddle positions, their inputs, and the overall game_state, if the game has ended, it will also return a list of players who
#   are asking for a rematch and if anyone is asking for a rematch
def UseDataFromClient(data:bytes, paddle_positions:dict[str, int], player_inputs:dict[str, str], game_state:dict[str, int], RematchRequestVar:set['str']) -> Tuple[dict[str, int], dict[str,str], dict[str, int], set['str'], bool]:
    try:
        message = json.loads(data)
    except json.JSONDecodeError:
        print("Could not parse message:", repr(data))
        return paddle_positions, player_inputs, game_state, RematchRequestVar, False

    side:str = message.get("side")
    if message.get("type") == "paddle":
        paddle_y:int = message.get("paddle_y")
        input_command:str = message.get("input", "NOP")

        if side in player_inputs and input_command in ("UP", "DOWN", "NOP"):
            player_inputs[side] = input_command
            # print("PLAYER INPUTS:", player_inputs) DEBUG
            # print(f"Player {side} input command: {input_command}") DEBUG

        # HK: Updates the ball position. Does this by use the paddle with a higher sync as the true position. 
        #   This works due to the sync variable manipulation. When a paddle hits the ball "it's" sync value is increased by 5.
        #   This causes the "true" ball position to be from the player who has the most interaction with teh ball. 
        client_sync:int = message.get("sync", 0)
        if client_sync > game_state["sync"]:
            game_state["sync"] = client_sync
            game_state["ball_x"] = message.get("ball_x", game_state["ball_x"])
            game_state["ball_y"] = message.get("ball_y", game_state["ball_y"])
            game_state["ball_vx"] = message.get("ball_vx", game_state["ball_vx"])
            game_state["ball_vy"] = message.get("ball_vy", game_state["ball_vy"])
            game_state["lScore"] = message.get("lScore", game_state["lScore"])
            game_state["rScore"] = message.get("rScore", game_state["rScore"])

        # CJ: Validates and stores each player's movement input and paddle position.
        if side in player_inputs:
            if input_command in ("UP", "DOWN", "NOP"):
                player_inputs[side] = input_command

            if isinstance(paddle_y, int):
                paddle_positions[side] = max(0, min(550, paddle_y))

            #print("Combined player inputs:", player_inputs)
            #print("Combined paddle positions:", paddle_positions)


    # HK: An alternative "if" branch for deciding a rematch. Uses the input system for the paddle movement. p = "Rematch"
    elif message.get("action") == "Rematch":

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

                return paddle_positions, player_inputs, game_state, RematchRequestVar, True # HK: Both players agree

    return paddle_positions, player_inputs, game_state, RematchRequestVar, False

# Author: Chenxiang Jiang, Holden Kennedy, Omar Ellala 
# Purpose: Pull the IP address and port number an incoming connection and push it into a waitingClients queu
# Pre: Assume socket is using AF_INET (IPv4) and SOCK_STREAM (TCP)
# Post: When the queue has two items, pop them and start a new thread with both that will start the main game logic 
def handleConnections() -> None:
    waitingClients:list[socket.socket] = [] 

    while(True):

        while len(waitingClients) < 2:
            print( "Waiting for another client to connect...")
            
            # new client
            conn, addr = server_socket.accept()
            print(f"[NEW CONNECTION] {addr}")
            waitingClients.append(conn)
            buffers[conn] = ""

            # Assign Left or Right paddle
            PaddleSide = "left" if len(waitingClients) == 1 else "right"

            conn.send(f"{screenWidth},{screenHeight},{PaddleSide}".encode()) # Hard Coded. 
            time.sleep(1/120)
            print("number of waiting clients:", len(waitingClients))

        player_count:bytes = str(len(waitingClients)).encode()    
        # Send player_count to both sides to let them know they can start the game 
        for connection in waitingClients:
            connection.send(player_count)
        # Start a new thread with the two clients that will handle game logic
        newGame:threading.Thread = threading.Thread(target = playGame, args = (waitingClients[0], waitingClients[1]), daemon = False)
        newGame.start()
        # Remove clients from queue
        waitingClients.pop()
        waitingClients.pop()



# MAIN GAME LOOP
# Author: Chenxiang Jiang, Holden Kennedy, Omar Ellala 
# Purpose: This is the main game loop where all of the information related to the game state will be stored, processed, and passed back to both clients  
# Pre: Both sockets of both players are received from the handleConnections function
# Post: Both players receive updated game state that they use to update their own GUI
def playGame(player1:socket.socket, player2:socket.socket) -> None:
    
    # Initial game state variables
    RestartGame:bool = False
    # CJ: Stores both players' paddle positions and movement inputs for synchronization.
    paddle_positions:dict[str, int] = {
        "left": 300,
        "right": 300
    }
    player_inputs:dict[str, str] = {
        "left": "NOP",
        "right": "NOP"
    }
    # HK: Dictionary for the ball and score, uses the same format as the inputs
    game_state:dict[str, int] = {
        "sync": 0,
        "ball_x": 400,
        "ball_y": 300,
        "ball_vx": -5,
        "ball_vy": 0,
        "lScore": 0,
        "rScore": 0
    }
    # HK: A variable to decide if players agree to a rematch. 
    RematchRequestVar:set['str'] = set()


    print("Starting a game with client", player1, "and", player2)
    inputs:list[socket.socket] = [server_socket]
    inputs.append(player1)
    inputs.append(player2)
    gameEnd:bool = False

    while (not gameEnd): # Main game loop
        readable, _, _ = select.select([player1, player2], [], [], 1)
        for s in readable:
            try:
                data = s.recv(1024)
            except (ConnectionResetError, OSError):
                data = None
        
            if not data: # If there's no data in the message
                print("[DISCONNECTED], ending game")
                inputs.remove(player1)
                inputs.remove(player2)
                buffers.pop(player1, None)
                buffers.pop(player2, None)
                for connection in (player1, player2):
                    try:
                        connection.sendall(b"DISCONNECT\n")
                    except OSError as e:
                        print("Error sending disconnect:", e)
                    finally:
                        connection.close()
                gameEnd = True
                break


            else: # If there is data in the socket
                buffers[s] += data.decode("utf-8")

                while "\n" in buffers[s]:
                    message, buffers[s] = buffers[s].split("\n", 1)

                    if message:
                        print("Received:", message)
                        
                        # HK: Gets the packet from the client when they press "p"
                        paddle_positions, player_inputs, game_state, RematchRequestVar, RestartGame = UseDataFromClient(message, paddle_positions, player_inputs, game_state, RematchRequestVar)

                        update = {
                            "type": "paddles",
                            "left_y": paddle_positions["left"],
                            "right_y": paddle_positions["right"],
                            "left_input": player_inputs["left"],
                            "right_input": player_inputs["right"],
                            "RematchRequestVar": len(RematchRequestVar),
                            "restart": RestartGame,
                            **game_state  #HK: Add game state into this update message. 
                        }

                        outgoing:bytes = (json.dumps(update) + "\n").encode("utf-8")

                        for connection in inputs[1:]:
                            try:
                                connection.send(outgoing)
                            except OSError as e:
                                print("Error sending update:", e)

                        print("SENT PADDLES:", update)

# Begin main program loop
handleConnections()
