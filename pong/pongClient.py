# =================================================================================================
# Contributing Authors:     Chenxiang Jiang
# Email Addresses:          cji233@uky.edu
# Date:                     11/8/2026
# Purpose:                  Implemented client-server communication for passing player inputs
#                           in the multiplayer Pong game. Sends paddle positions and movement
#                           commands (UP, DOWN, NOP) using TCP sockets and JSON. Also handles
#                           receiving, parsing, and storing game information to support
#                           synchronization between players.
# Misc:                     Used threading and message buffering to prevent network operations
#                           from interrupting gameplay.
# =================================================================================================

# =================================================================================================
# Contributing Authors:	    Holden Kennedy  ,
# Email Addresses:          hlke229@uky.edu ,
# Date:                     11/7/2026
# Purpose:                  This is the client code. It will handle all client responsibilities including sending and receiving data.
# Misc:                     <Not Required.  Anything else you might want to include>
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

    lScore = 0
    rScore = 0

    sync = 0

    
    send_queue = queue.Queue(maxsize=1)

    def network_sender():
        while True:
            message = send_queue.get()

            try:
                data = json.dumps(message) + "\n"
                client.sendall(data.encode("utf-8"))
            except OSError as e:
                print("Network error:", e)
                break

    threading.Thread(
        target=network_sender,
        daemon=True
    ).start()
    
    incoming_messages = queue.Queue()

    def network_receiver():
        buffer = ""

        while True:
            try:
                data = client.recv(4096)

                if not data:
                    print("Server disconnected")
                    break

                buffer += data.decode("utf-8")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)

                    if line:
                        message = json.loads(line)
                        incoming_messages.put(message)

            except (OSError, ValueError) as e:
                print("Receive error:", e)
                break

    threading.Thread(
        target=network_receiver,
        daemon=True
    ).start()



    while True:
        # Wiping the screen
        screen.fill((0,0,0))

        # Getting keypress events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_DOWN:
                    playerPaddleObj.moving = "down"

                elif event.key == pygame.K_UP:
                    playerPaddleObj.moving = "up"

            elif event.type == pygame.KEYUP:
                playerPaddleObj.moving = ""

        # =========================================================================================
        # Your code here to send an update to the server on your paddle's information,
        # where the ball is and the current score.
        # Feel free to change when the score is updated to suit your needs/requirements
        
        
        # =========================================================================================

        # Update the player paddle and opponent paddle's location on the screen
        for paddle in [playerPaddleObj, opponentPaddleObj]:
            if paddle.moving == "down":
                if paddle.rect.bottomleft[1] < screenHeight-10:
                    paddle.rect.y += paddle.speed # increases because the top left is (0,0)
            elif paddle.moving == "up":
                if paddle.rect.topleft[1] > 10:
                    paddle.rect.y -= paddle.speed

        # If the game is over, display the win message
        if lScore > 4 or rScore > 4:
            winText = "Player 1 Wins! " if lScore > 4 else "Player 2 Wins! "
            textSurface = winFont.render(winText, False, WHITE, (0,0,0))
            textRect = textSurface.get_rect()
            textRect.center = ((screenWidth/2), screenHeight/2)
            winMessage = screen.blit(textSurface, textRect)
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
                bounceSound.play()
                ball.hitPaddle(playerPaddleObj.rect.center[1])
            elif ball.rect.colliderect(opponentPaddleObj.rect):
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
       
        if sync % 6 == 0:
            message = {
                "type": "paddle",
                "side": playerPaddle,
                "paddle_y": playerPaddleObj.rect.y,
                "input": playerPaddleObj.moving or "NOP",
                "sync": sync
            }

            try:
                send_queue.put_nowait(message)
            except queue.Full:
                pass


        


        # =========================================================================================
        # Send your server update here at the end of the game loop to sync your game with your
        # opponent's game

        # =========================================================================================




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

    DataInFormat = client.recv(1024).decode() 
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

    PlayerCountInfo = client.recv(1024).decode()
    NumPlayers:int = int(PlayerCountInfo)

    # Updated to pass the plauer paddle variable. 
    while True:
        if (NumPlayers == 2):
            playGame(IntScreenWidth, IntScreenHeight, playerPaddle, client)  # User will be either left or right paddle
            return
        else:
            errorLabel.config(text=f"Waiting for another player to join...")
            errorLabel.update()

    app.quit()         # Kills the window


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