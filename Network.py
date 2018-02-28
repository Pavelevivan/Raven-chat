import socket
import select
import random
import re
import sys
from threading import Lock
from queue import Queue
from  json import loads, dumps
MESSAGE_SIZE = 64 * 1024
DATABASE = dict()  # (ip,addr):name

RE_MSG = re.compile("<MSG>(.*?)<MSG>")
RE_CON = re.compile("<CON>(.*?)<CON>")

class Message:
    @staticmethod
    def send_message(data):
        msg = "<MSG>{}<MSG>".format(data).encode('utf-8')
        return msg

    @staticmethod
    def registration(data):
        msg = "<REG>{}<REG>".format(data)
        return msg

    @staticmethod
    def send_contacts(data):
        msg = "<CON>{}<CON>".format(data).encode('utf-8')
        return msg

    @staticmethod
    def exit(data):
        msg = "<EX>{}<EX>".format(data)
        return msg


class Client:
    def __init__(self, name, ip, port):
        self.name = name
        self.port = port
        self.ip = ip


class ServerChat:
    def __init__(self, name):
        self.messages_from_users = Queue()
        self.messages_to_users = Queue()
        self.incoming_connections = Queue()
        q = Queue()
        self.is_server = False
        self.server_ip = None
        self.server_port = None
        self.name = name
        self.name_changed = False
        self.server_socket = None
        self.create_server_socket()
        self.ip_connections = []
        self.socket_connections = {}  # Key:socket, Value: (ip, port)

    def create_server_socket(self):
        established = False
        while not established:
            try:
                self.server_ip = socket.gethostbyname(socket.getfqdn())
                self.server_port = random.randint(49151, 65535)
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.bind((self.server_ip, self.server_port))
                self.server_socket.settimeout(2)
                self.server_socket.listen(socket.SOMAXCONN)
                established = True
            except OSError:
                pass

    def extract_message(self, messages):
        new_contacts = RE_CON.findall(messages)
        for contact in new_contacts:
            print(loads(contact))
        msgs = RE_MSG.findall(messages)
        for msg in msgs:
            self.messages_from_users.put(msg)

    def user_introduction(self, sock):
        '''
        Sending known contacts and user's nickname to the new contact
        :param sock:
        :return:
        '''
        msg_reg = Message.send_message(
            Message.registration(self.name + ':'
                                 + str(self.server_socket.getsockname())))
        print(list(self.socket_connections.values()))
        msg_contacts = Message.send_contacts(
            dumps(list(self.socket_connections.values())))
        try:
            sock.send(msg_reg)
            sock.send(msg_contacts)
        except OSError:
            self.exit(sock)

    def exit(self, sock):
        msg_ex = Message.send_message(Message.exit(self.socket_connections[sock]))
        sock.close()
        ip = self.socket_connections.pop(sock)[0]
        self.ip_connections.remove(ip)
        self.messages_from_users.put(msg_ex)

    def server_connections_handler(self):
        read_sockets, write_sockets, error_sockets = select.select(
            list(self.socket_connections), list(self.socket_connections), [])
        for sock in read_sockets:
            try:
                data = sock.recv(MESSAGE_SIZE).decode()
                if data:
                    self.extract_message(data)
            except OSError:
                self.exit(sock)

        while write_sockets and not self.messages_to_users.empty():
            message = self.messages_to_users.get()
            for sock in write_sockets:
                try:
                    if self.name_changed:
                        self.user_introduction(sock)
                    message_to_send = Message.send_message(message)
                    sock.send(message_to_send)
                except OSError:
                    self.exit(sock)

            self.name_changed = False

    def server_handler(self, exit_condition):
        self.socket_connections[self.server_socket] = self.server_socket.getsockname()
        while True:
            if len(self.socket_connections) > 1:
                self.server_connections_handler()

            if not self.incoming_connections.empty():
                    new_sock = self.incoming_connections.get()
                    adr = new_sock.getpeername()
                    self.socket_connections[new_sock] = adr
                    self.ip_connections.append(adr[0])
                    self.user_introduction(new_sock)

            try:
                new_sock, adr = self.server_socket.accept()
                self.socket_connections[new_sock] = adr
                self.ip_connections.append(adr[0])
                self.user_introduction(new_sock)
            except OSError:
                pass

            if exit_condition.is_set():
                break
