import socket
import datetime

import threading

from utils import SockHandler


class UserHandler:
    def __init__(self):
        self.connected_clients = {}
        self.users = {}
        self.lowest_user_id = -1

        self.make_user("Deleted User")  # In the -1 slot for if someone who doesn't exist anymore sends a message
        self.make_user("Server")  # For "whoever" has joined messages

        self.groups = {}
        self.lowest_group_id = 0

    def make_group(self, name):
        self.groups[self.lowest_group_id] = (ChatRoom(name, self))

    def get_group(self, id):
        return self.groups[id]

    def make_user(self, name):
        self.users[self.lowest_user_id] = {
            "alive": True,
            "name": name,
            "id": self.lowest_user_id,
        }

        self.lowest_user_id += 1

        return self.lowest_user_id - 1

    def connect(self, user_id, conn):
        self.connected_clients[user_id] = conn

    def disconnect(self, user_id):
        del self.connected_clients[user_id]

    def get_user(self, user_id):
        return self.users.get(user_id, self.users[-1])

    def get_client(self, user_id):
        return self.connected_clients.get(user_id, None)

    def remove_client(self, user_id):
        del self.connected_clients[user_id]


class ChatRoom:
    def __init__(self, name, main):
        self.main = main

        self.name = name
        self.messages = []
        self.members = [0]

    def create_message(self, author, contents):
        message = {"author": author,
                   "content": contents,
                   "time": datetime.datetime.today().timetuple()[:5]
                   }  # TODO: Should probably be an object actually....

        self.messages.append(message)

        for member in self.get_members():
            client = self.main.get_client(member)
            if client:
                client.event(["message", message])

    def get_messages(self):
        return self.messages

    def get_message(self, message_id):
        return self.messages[message_id]

    def add_member(self, member_id):
        self.members.append(member_id)

    def kick_member(self, member_id):
        self.members.remove(member_id)

    def get_members(self):
        return self.members

    def on_leave(self, user_id):
        self.create_message(0, self.main.get_user(user_id)["name"]+" is now offline.")

    def on_join(self, user_id):
        self.create_message(0, self.main.get_user(user_id)["name"]+" is now online!")


class ClientConnection(threading.Thread):
    def __init__(self, sock, address, main):
        super().__init__()

        self.main = main

        self.sock = SockHandler(sock)
        self.addr = address

        self.busy = threading.Lock()
        self.busy.acquire()

        self.id = -1
        self.start()

    def event(self, data):
        if not self.busy.locked():
            self.busy.acquire()
            self.sock.send(data)

    def run(self):
        try:
            while 1:
                data = self.sock.receive()

                if data[0] == "login":
                    self.id = self.main.make_user(data[1]["name"])
                    self.main.connect(self.id, self)
                    self.sock.send(self.id)

                elif data[0] == "join":
                    chat = self.main.get_group(data[1])
                    chat.add_member(self.id)
                    chat.on_join(self.id)

                elif data[0] == "get":
                    self.sock.send(self.main.get_group(data[1]).get_messages())

                elif data[0] == "info":
                    if data[1] == "author":
                        self.sock.send(self.main.get_user(data[2]))
                    elif data[1] == "group":
                        self.sock.send(self.main.get_group(data[2]))

                elif data[0] == "send":
                    self.main.get_group(data[1]).create_message(self.id, data[2])

                elif data[0] == "listening":
                    self.busy.release()

        except ConnectionResetError:
            self.main.remove_client(self.id)

            for group_id in self.main.groups:
                group = self.main.get_group(group_id)
                if self.id in group.get_members():
                    group.on_leave(self.id)

#           for client in clients:
#                send(client.sock, ["left", self.id])
# make_message(userdata[self.id]["name"] + " is now offline.", -1)


def start():
    HOST = '0.0.0.0'  # My IP.
    PORT = 65431  # Port to listen on (non-privileged ports are > 1023)

    serversock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    serversock.bind((HOST, PORT))

    main = UserHandler()
    main.make_group("The Spleen Team")

    while True:
        serversock.listen()

        conn, addr = serversock.accept()  # conn is the socket between "us" and the client, address is the client IP

        ClientConnection(conn, addr, main)


if __name__ == "__main__":
    start()
