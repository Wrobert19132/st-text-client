import json


class SockHandler:
    CAP = 1024

    def __init__(self, sock):
        self.sock = sock

    def send(self, data):
        encoded = json.dumps(data).encode()
        size = len(encoded)

        self.sock.send((json.dumps(size) + "#").encode())

        while len(encoded) > 0:
            self.sock.send(encoded[:self.CAP])
            encoded = encoded[self.CAP:]

    def receive(self):
        size = ""
        while len(size) == 0 or size[-1] != "#":
            size += self.sock.recv(1).decode()
        size = json.loads(size[:-1])

        transmission = ""

        while len(transmission) != size:
            transmission += self.sock.recv(min(size - len(transmission), self.CAP)).decode()

        transmission = json.loads(transmission)

        return transmission
