# =================================================================================================
# Contributing Authors:	    <Anyone who touched the code>
# Email Addresses:          <Your uky.edu email addresses>
# Date:                     <The date the file was last edited>
# Purpose:                  <How this file contributes to the project>
# Misc:                     <Not Required.  Anything else you might want to include>
# =================================================================================================

import socket
import threading

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
    