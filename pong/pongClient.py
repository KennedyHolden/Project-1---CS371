# =================================================================================================
# Contributing Authors:     Chenxiang Jiang, Holden Kennedy, Omar Ellala
# Email Addresses:          cji233@uky.edu, hlke229@uky.edu, Omar.Ellala@uky.edo
# Date:                     11/8/2026
# Purpose:                  Implemented client-server communication for passing player inputs
#                           in the multiplayer Pong game. Sends paddle positions and movement
#                           commands (UP, DOWN, NOP) using TCP sockets and JSON. Also handles
#                           receiving, parsing, and storing game information to support
#                           synchronization between players.
# Misc:                     Used threading and message buffering to prevent network operations
#                           from interrupting gameplay.
# =================================================================================================


from xmlrpc import client
import pygame
import tkinter as tk
import sys
import socket
import json
import threading
import queue

from assets.code.helperCode import *


# PaddleMovement = "" # HK: Global variable for replacing "paddel.moving" DEPRECATED
WinningValue:int = 2 # HK: Replaces the magic value. How many points is needed to win. 
BonusSync:int = 5 # HK: A value that is added to sync to help for changing who is in charge. 


# This is the main game loop.  For the most part, you will not need to modify this.  The sections
# where you should add to the code are marked.  Feel free to change any part of this project
# to suit your needs.
def playGame(screenWidth:int, screenHeight:int, playerPaddle:str, client:socket.socket) -> None:
    
    # Pygame inits
    pygame.mixer.pre_init(44100, -16, 2, 2048)
    pygame.init()

    # Constants
    WHITE = (255,255,255)
    clock = pygame.time.Clock()
    scoreFont = pygame.font.Font("./assets/fonts/pong-score.ttf", 32)
    winFont = pygame.font.Font("./assets/fonts/visitor.ttf", 48)
    pointSound = pygame.mixer.Sound("./assets/sounds/point.wav")
    bounceSound = pygame.mixer.Sound("./assets/sounds/bounce.wav")

    # Display objects
    screen = pygame.display.set_mode((screenWidth, screenHeight))
    winMessage = pygame.Rect(0,0,0,0)
    topWall = pygame.Rect(-10,0,screenWidth+20, 10)
    bottomWall = pygame.Rect(-10, screenHeight-10, screenWidth+20, 10)
    centerLine = []
    for i in range(0, screenHeight, 10):
        centerLine.append(pygame.Rect((screenWidth/2)-5,i,5,5))

    # Paddle properties and init
    paddleHeight = 50
    paddleWidth = 10
    paddleStartPosY = (screenHeight/2)-(paddleHeight/2)
    leftPaddle = Paddle(pygame.Rect(10,paddleStartPosY, paddleWidth, paddleHeight))
    rightPaddle = Paddle(pygame.Rect(screenWidth-20, paddleStartPosY, paddleWidth, paddleHeight))

    ball = Ball(pygame.Rect(screenWidth/2, screenHeight/2, 5, 5), -5, 0)

    if playerPaddle == "left":
        opponentPaddleObj = rightPaddle
        playerPaddleObj = leftPaddle
    else:
        opponentPaddleObj = leftPaddle
        playerPaddleObj = rightPaddle

    lScore:int = 0
    rScore:int = 0

    sync:int = 0

    # Variable to keep track of Rematch Requests
    RematchRequestVar:int = 0

    # CJ: Queues outgoing messages so networking does not interrupt gameplay
    send_queue = queue.Queue(maxsize=10)
    #OE: Create an event so that the client can handle disconnections properly
    disconnect_event = threading.Event()

    # CJ: Converts queued messages into JSON and sends them to the server over TCP.
    def network_sender():
        while not disconnect_event.is_set():
            try:
                message = send_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if disconnect_event.is_set():
                break

            try:
                data = json.dumps(message) + "\n" # converts python dictionary into a JSON string. 
                client.sendall(data.encode("utf-8")) # sends the JSON string (converted into bytes) to the server through TCP.
            except OSError as e:
                if not disconnect_event.is_set():
                    print("Network error:", e)
                break

    # CJ: Runs the sender in a background thread to keep gameplay responsive.
    sender_thread = threading.Thread(
        target=network_sender, 
        daemon=True
    )
    sender_thread.start()

    # CJ: Stores received server messages for processing by the game loop.
    incoming_messages = queue.Queue()

    # CJ: Receives TCP data and reconstructs complete JSON messages using newline delimiters.
    def network_receiver():
        buffer = "" 

        while True:
            try:
                data = client.recv(4096) # recv() waits until data arrives or the connection closes. 

                if not data:
                    print("Server disconnected")
                    disconnect_event.set()
                    break

                buffer += data.decode("utf-8")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1) # splits the buffer at the first newline character

                    if line: # checks if the line is not empty, true when it has, false when it doesn't.
                        if line == "DISCONNECT":
                            print("Opponent disconnected; ending game")
                            disconnect_event.set()
                            return

                        message = json.loads(line)
                        incoming_messages.put(message)

            except (OSError, ValueError) as e:
                print("Receive error:", e)
                disconnect_event.set()
                break

    # CJ: Runs the receiver in a background thread to avoid blocking gameplay.
    threading.Thread(
        target=network_receiver,
        daemon=True
    ).start()



    while not disconnect_event.is_set():
        # Wiping the screen
        screen.fill((0,0,0))

        # Getting keypress events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_DOWN:
                    playerPaddleObj.moving = "DOWN"
                    #print("Pressed Down") DEBUG
                    #   Uses the network sender funcion by Chen.
                    send_queue.put_nowait({"action": "DOWN"})

                elif event.key == pygame.K_UP:
                    playerPaddleObj.moving = "UP"
                    #print("Pressed Up") DEBUG
                    #   Uses the network sender funcion by Chen.
                    send_queue.put_nowait({"action": "UP"})

                    # Only possible after game is over
                elif event.key == pygame.K_p and (lScore > WinningValue or rScore > WinningValue):
                    print("Pressed P - asking for a Rematch") 
                    send_queue.put_nowait({"action": "Rematch", "side": playerPaddle})
                    


            elif event.type == pygame.KEYUP:
                playerPaddleObj.moving = ""
                #   Uses the network sender funcion by Chen.
                #send_queue.put_nowait({"action": ""})


        # latest State initalized to None. Error: "cannot access local variable 'latest_state' where it is not associated with a value"
        latest_state = None

        # CJ: Processes queued server updates without blocking the game loop. 
        # Omar - reusing it to make the player and opponent paddle position themselves based on the latest input  
        while not incoming_messages.empty():
            try:
                latest_state = incoming_messages.get_nowait()
                if latest_state and latest_state.get("type") == "paddles":


                    # HK: An if so that the openent cannot change your positoin whith their delay info. 
                    if playerPaddle == "right":
                        leftPaddle.rect.y = latest_state.get("left_y", leftPaddle.rect.y)
                    else:
                        rightPaddle.rect.y = latest_state.get("right_y", rightPaddle.rect.y)

                    # HK: Uses the sync variable to decide who has the "True" Ball position and score.
                    server_sync = latest_state.get("sync", 0)
                    if server_sync > sync:
                        sync = server_sync
                        ball.rect.x = latest_state.get("ball_x", ball.rect.x)
                        ball.rect.y = latest_state.get("ball_y", ball.rect.y)
                        ball.xVel = latest_state.get("ball_vx", ball.xVel)
                        ball.yVel = latest_state.get("ball_vy", ball.yVel)
                        lScore = latest_state.get("lScore", lScore)
                        rScore = latest_state.get("rScore", rScore)

                    # left_input = latest_state.get("left_input", "NOP") DEBUG
                    # right_input = latest_state.get("right_input", "NOP") DEBUG
                    # print("Left player input:", left_input) DEBUG
                    # print("Right player input:", right_input) DEBUG

                #HK: Resets the vales when players agree to restart
                if "RematchRequestVar" in latest_state:
                    RematchRequestVar = latest_state["RematchRequestVar"]

                # Resets all values back to initial state
                if latest_state.get("restart"):
                    lScore = 0
                    rScore = 0
                    sync = 0
                    RematchRequestVar = 0
                    leftPaddle.rect.y = paddleStartPosY
                    rightPaddle.rect.y = paddleStartPosY
                    ball.reset(nowGoing="left")


            except queue.Empty:
                break
                
        #if latest_state:
        #   print("Server says:", latest_state) #Debug


        pass
        

        # PaddleMovement is a variable that I added (HK) to replace the playerPaddleObj.moving variable.   
        # This seperates the clients inputs from there game. We can change this so that it uses the server's inputts as this variable.  

        # Update the player paddle and opponent paddle's location on the screen
        for paddle in [playerPaddleObj, opponentPaddleObj]:
             if playerPaddleObj.moving == "DOWN":
              if playerPaddleObj.rect.bottom < screenHeight - 10:
                playerPaddleObj.rect.y += playerPaddleObj.speed

             elif playerPaddleObj.moving == "UP":
              if playerPaddleObj.rect.top > 10:
                   playerPaddleObj.rect.y -= playerPaddleObj.speed


        # If the game is over, display the win message
        if lScore > WinningValue or rScore > WinningValue:
            winText = "Player 1 Wins! " if lScore > WinningValue else "Player 2 Wins! "
            textSurface = winFont.render(winText, False, WHITE, (0,0,0))
            textRect = textSurface.get_rect()
            textRect.center = ((screenWidth/2), screenHeight/2)
            winMessage = screen.blit(textSurface, textRect)

            # HK: For rematches, copied the style from the win message

            if RematchRequestVar == 1: # If someone requests rematch or no one has yet

                    # If string is too long. It will cut off by the screen. Using "\n" will overlap the win message.
                rematchText = "1 player ready for rematch"
            else:
                rematchText = "Press P for a rematch"

            rematchSurface = winFont.render(rematchText, False, WHITE, (0,0,0))
            rematchRect = rematchSurface.get_rect()
            rematchRect.center = ((screenWidth/2), (screenHeight/2) + 50)
            screen.blit(rematchSurface, rematchRect)


    
        else:

            # ==== Ball Logic =====================================================================
            ball.updatePos()

            # If the ball makes it past the edge of the screen, update score, etc.
            if ball.rect.x > screenWidth:
                lScore += 1
                pointSound.play()
                ball.reset(nowGoing="left")
            elif ball.rect.x < 0:
                rScore += 1
                pointSound.play()
                ball.reset(nowGoing="right")
                
            # If the ball hits a paddle
            if ball.rect.colliderect(playerPaddleObj.rect):

                # HK: Only count a hit if the ball is moving towards the players paddle.
                #   If ball is moving left and player = left or vice versa
                if (playerPaddle == "left" and ball.xVel < 0) or( playerPaddle == "right" and ball.xVel > 0):
                    bounceSound.play()
                    ball.hitPaddle(playerPaddleObj.rect.center[1])

                    # This is done so that the player who just hit the ball should have the advangage on updating the score and ball positoin.
                    sync += BonusSync 
            
            elif ball.rect.colliderect(opponentPaddleObj.rect):
                # HK: Only count a hit if the ball is moving towards the players paddle.
                #   If ball is moving right and player = left or vice versa
                if (playerPaddle == "left" and ball.xVel < 0) or( playerPaddle == "right" and ball.xVel > 0):
                    bounceSound.play()
                    ball.hitPaddle(opponentPaddleObj.rect.center[1])
                
            # If the ball hits a wall
            if ball.rect.colliderect(topWall) or ball.rect.colliderect(bottomWall):
                bounceSound.play()
                ball.hitWall()
            
            pygame.draw.rect(screen, WHITE, ball.rect)
            
            # ==== End Ball Logic =================================================================

        # Drawing the dotted line in the center
        for i in centerLine:
            pygame.draw.rect(screen, WHITE, i)
        
        # Drawing the player's new location
        for paddle in [playerPaddleObj, opponentPaddleObj]:
            pygame.draw.rect(screen, WHITE, paddle)

        pygame.draw.rect(screen, WHITE, topWall)
        pygame.draw.rect(screen, WHITE, bottomWall)
        scoreRect = updateScore(lScore, rScore, screen, WHITE, scoreFont)
        pygame.display.update()
        clock.tick(60)
        
        # This number should be synchronized between you and your opponent.  If your number is larger
        # then you are ahead of them in time, if theirs is larger, they are ahead of you, and you need to
        # catch up (use their info)
        sync += 1 

        # CJ: Sends periodic paddle and game-state updates to keep both clients synchronized.
        if sync % 2 == 0: 
            message = {
                "type": "paddle",
                "side": playerPaddle,
                "paddle_y": playerPaddleObj.rect.y,
                "input": playerPaddleObj.moving or "NOP",
                "sync": sync,

                # Ball postion + Score
                "ball_x": ball.rect.x,
                "ball_y": ball.rect.y,
                "ball_vx": ball.xVel,
                "ball_vy": ball.yVel,
                "lScore": lScore,
                "rScore": rScore
            }
            # CJ: Skips an outgoing update when the queue is full to prevent blocking.
            try: 
                send_queue.put_nowait(message)
            except queue.Full:
                pass

    disconnect_event.set()
    sender_thread.join(timeout=1)
    client.close()
    pygame.quit()
    return



# This is where you will connect to the server to get the info required to call the game loop.  Mainly
# the screen width, height and player paddle (either "left" or "right")
# If you want to hard code the screen's dimensions into the code, that's fine, but you will need to know
# which client is which
def joinServer(ip:str, port:str, errorLabel:tk.Label, app:tk.Tk) -> None:
    # Purpose:      This method is fired when the join button is clicked
    # Arguments:
    # ip            A string holding the IP address of the server
    # port          A string holding the port the server is using
    # errorLabel    A tk label widget, modify it's text to display messages to the user (example below)
    # app           The tk window object, needed to kill the window
    
    # Create a socket and connect to the server
    # You don't have to use SOCK_STREAM, use what you think is best
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Connect to the server. 
    client.connect((ip, int(port)))
    
    # Get the required information from your server (screen width, height & player paddle, "left or "right)

    DataInFormat = client.recv(4096).decode() 
    #Parses the data for the hight, width and player paddle.
    ScreenWidth, ScreenHeight, playerPaddle = DataInFormat.split(",")

    # Got errors on these being strings, converting to int fixes this. 
    IntScreenWidth = int(ScreenWidth) 
    IntScreenHeight = int(ScreenHeight) 

    # If you have messages you'd like to show the user use the errorLabel widget like so
    errorLabel.config(text=f"It Works!: Paddle: {playerPaddle} IP: {ip}, Port: {port}")

    #errorLabel.config(text=f"Some update text. You input: IP: {ip}, Port: {port}")
    # You may or may not need to call this, depending on how many times you update the label
    errorLabel.update()     

    # Close this window and start the game with the info passed to you from the server
    app.withdraw()     # Hides the window (we'll kill it later)


    # Updated to pass the plauer paddle variable. 
    while True:
        print("Test 1")
        PlayerCountInfo = client.recv(1024).decode()
        print("Received", PlayerCountInfo)
        NumPlayers:int = int(PlayerCountInfo)
        print(f"NumPlayers: {NumPlayers}")
        if (NumPlayers%2 == 0):
            playGame(IntScreenWidth, IntScreenHeight, playerPaddle, client)  # User will be either left or right paddle
            app.quit()
            return
        else:
            errorLabel.config(text=f"Waiting for another player to join...")
            errorLabel.update()
            print(f"Test 1")

# This displays the opening screen, you don't need to edit this (but may if you like)
def startScreen():
    app = tk.Tk()
    app.title("Server Info")

    image = tk.PhotoImage(file="./assets/images/logo.png")

    titleLabel = tk.Label(image=image)
    titleLabel.grid(column=0, row=0, columnspan=2)

    # For inputting IP & Port of the server
    ipLabel = tk.Label(text="Server IP:")
    ipLabel.grid(column=0, row=1, sticky="W", padx=8)

    ipEntry = tk.Entry(app)
    ipEntry.grid(column=1, row=1)

    portLabel = tk.Label(text="Server Port:")
    portLabel.grid(column=0, row=2, sticky="W", padx=8)

    portEntry = tk.Entry(app)
    portEntry.grid(column=1, row=2)

    errorLabel = tk.Label(text="")
    errorLabel.grid(column=0, row=4, columnspan=2)

    joinButton = tk.Button(text="Join", command=lambda: joinServer(ipEntry.get(), portEntry.get(), errorLabel, app))
    joinButton.grid(column=0, row=3, columnspan=2)

    app.mainloop()

if __name__ == "__main__":
    startScreen()
    
    # Uncomment the line below if you want to play the game without a server to see how it should work
    # the startScreen() function should call playGame with the arguments given to it by the server this is
    # here for demo purposes only
    #playGame(640, 480,"left",socket.socket(socket.AF_INET, socket.SOCK_STREAM))