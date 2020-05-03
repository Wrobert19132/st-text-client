import socket
import json
import threading
import os
import datetime
import msvcrt

HOST = '81.153.76.207'  # The server's hostname or IP address
PORT = 65431  # The port used by the server

USERNAME = ""
CHATROOM = 0

"""
Created By: Will

Info: 
First try at messaging client, uses some sexy things like:

• Multi Threading
• Sockets (Including my own Sock Handler for receiving and writing data)
• client-server interaction
• A ton of object oriented stuff

• Me not using globals stupidly (Thx Alys)
• Some constants that are actually useful and make sense

• msvcrt module to get individual characters when they're written
"""


# Manages reading data from Sock buffer
class SockHandler:
    CAP = 1024  # Don't change this, buffer size

    def __init__(self, sock):
        self.sock = sock

    def send(self, data):
        encoded = json.dumps(data).encode()  # Change all the data into encoded string format
        size = len(encoded)

        self.sock.send((json.dumps(size) + "#").encode())  # Size of the data is sent first

        while len(encoded) > 0:  # Then the rest
            self.sock.send(encoded[:self.CAP])
            encoded = encoded[self.CAP:]

    def receive(self):
        size = ""
        while len(size) == 0 or size[-1] != "#":
            size += self.sock.recv(1).decode()
        size = json.loads(size[:-1])  # This here basically grabs the size that was written in send

        transmission = ""

        while len(transmission) != size:  # This loops until the data read matches the size it should be
            transmission += self.sock.recv(min(size - len(transmission), self.CAP)).decode()

        transmission = json.loads(transmission)  # Loaded up out of string format into actually useful stuff

        return transmission


# Handles you pressing keys and sending messages when you press enter
class MessageSender(threading.Thread):
    def __init__(self, receiver):
        super().__init__()

        self.typed = ""

        self.receiver = receiver

    def run(self):
        while True:
            self.handle_keys()

    def handle_keys(self):
        try:
            letter = msvcrt.getch().decode()  # Wait for a letter single letter to be typed.

        except UnicodeDecodeError:  # If the key is weird, pretend they typed nothing.
            letter = ""

        if letter == "\r":  # If the letter is enter:
            self.on_enter()
        else:
            if letter == "\x08":
                self.on_backspace()
            else:
                print(letter, end="", flush=True)  # Writes what you wrote to console, so you can see what your typing
                self.typed += letter

    def on_enter(self):
        self.receiver.sock.send(["send", self.receiver.group, self.typed])  # Sends what you wrote to the server.
        self.typed = ""  # Resets your message. For shenanigans change this to something but don't actually.

    def on_backspace(self):
        if len(self.typed) > 0:
            print("\x08", end="", flush=True)  # Moves back a character on the line
            print(" ", end="", flush=True)  # Types a blank space, replacing prev character
            print("\x08", end="", flush=True)  # Moves back a character again

            self.typed = self.typed[:-1]  # Delete


# Main bulk of the program. The UI and data.
class MessageReceiver(threading.Thread):

    @staticmethod
    def establish_connection():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((HOST, PORT))
        return s

    def __init__(self):
        super().__init__()

        # Caches - as to not kill my internet, stuff is only grabbed once from the server then stored locally here

        self.author_cache = {}  # All the members you've seen
        self.message_cache = {}  # The messages
        self.group_cache = {}

        self.id = 0  # This will change pretty quickly.
        self.group = -1

        self.sock = SockHandler(self.establish_connection())

        self.sender = MessageSender(self)

        self.start()

    def run(self):

        self.login()

        self.sock.send(["get", self.group])  # Download *all* the messages for a channel so far.
        self.message_cache[self.group] = self.sock.receive()

        self.sender.start()

        while True:
            self.draw_ui()
            self.await_message()

    def login(self):
        os.system("CLS")

        global USERNAME

        if not USERNAME:
            USERNAME = input("Enter a username: ")

        self.sock.send(["login", {"name": USERNAME}])  # "Create an account" with the server

        self.id = self.sock.receive()  # Pretty much discord user id's

        print("Login successful!\n")

        self.sock.send(["count", "group"])
        count = self.sock.receive()

        print("Available groups:")
        for i in range(count):
            g = self.get_group(i)
            print(str(i) + ") " + g["name"])

        valid = False
        while not valid:
            inp = input("\nEnter the number of the group to join: ")
            if inp.isnumeric():
                inp = int(inp)
                if inp >= 0:
                    if inp < count:
                        valid = True
                    else:
                        print("That number is too high!")
                else:
                    print("That number is too low!")
            else:
                print("That's... not a number?")

        self.group = inp

        self.sock.send(["join", self.group])  # "join" a room if your not already a member in it

    def get_author(self, author_id):
        if author_id not in self.author_cache.keys():  # If the author info isn't saved locally in our cache yet
            self.sock.send(["info", "author", author_id])
            self.author_cache[author_id] = self.sock.receive()  # Save's the author info locally
        return self.author_cache[author_id]

    def get_group(self, group_id):
        if group_id not in self.group_cache.keys():  # If the group info isn't saved locally yet
            self.sock.send(["info", "group", group_id])
            self.group_cache[group_id] = self.sock.receive()  # Save's the group info locally
        return self.group_cache[group_id]

    def draw_ui(self):
        os.system("CLS")  # Clears the screen

        print(self.get_group(self.group)["name"])  # prints the name of the group your in

        for message in self.message_cache[self.group][-20:]:  # Write the last 15 messages to the screen
            author_name = self.get_author(message["author"])["name"]
            message_content = message["content"]
            time = datetime.datetime(*message["time"])

            print("> " + author_name[:15].ljust(15) + " : " + message_content)

        print("".join(["-" for i in range(30)]))  # A blank line.

        print(self.get_author(self.id)["name"] + ": " + self.sender.typed, end="", flush=True)  # What you've typed.

    def await_message(self):
        self.sock.send(["listening"])  # Unlock thread lock to let server know to send us events

        data = self.sock.receive()  # Wait for the server to send us something

        if data[0] == "message":  # If that something is a message.....
            self.new_message(data[1], data[2])

    def new_message(self, group_id, message):  # Called when a message is sent
        l = self.message_cache.get(group_id, [])
        l.append(message)
        self.message_cache[group_id] = l
        # TODO: Alert object?


if __name__ == "__main__":
    MessageReceiver()
