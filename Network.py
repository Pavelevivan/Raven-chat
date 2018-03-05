import socket
import select
import random
import re
import threading
import logging
from queue import Queue
from json import loads, dumps
MESSAGE_SIZE = 64 * 1024
DATABASE = dict()  # (ip,addr):name
RE_CON = re.compile("<CON>(.*?)<CON>")
R_REG = re.compile("<REG>(.*?)<REG>")

R_MSG = re.compile("({.*?})")

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
    def disconnect(data):
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
        self._create_receiving_socket()
        self.host = self.server_ip + ', ' + str(self.server_port)
        self.host_connections = []  # List of tuples (host, user)
        self.socket_connections = {}  # Key: socket, Value: (ip, port)

    def _create_receiving_socket(self):
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

    def extract_messages(self, messages):
        print(messages.decode())
        messages = [loads(x) for x in R_MSG.findall(messages.decode('utf-8'))]
        for msg in messages:
            if msg['file'] != '':
                pass
            if msg['action'] == 'connect':
                # adding host of the new user
                self.host_connections.append((msg['host'], msg['user']))
            if msg['action'] == 'disconnect':
                # removing host of the outgoing user
                self.host_connections.remove((msg['host'], msg['user']))
            if msg['connections'] is not None:
                new_connections = [(x, y) for x, y in msg['connections'] if (x, y) not in self.host_connections]
                if new_connections:
                    self.host_connections.extend(new_connections)
                    msg['connections'] = new_connections
                    self.messages_from_users.put(msg)
            if msg['msg'] != '':
                self.messages_from_users.put(msg)

    def _introduction_message(self, sock):
        '''
        Sending known contacts and user's nickname to the new user
        :param sock:
        :return:
        '''
        sock.send(self._create_message(
            user=self.name,
            action='connect',
            host=self.host,
            connections=self.host_connections
        ))
        
    def _disconnect(self, sock):
        '''msg_ex = Message.disconnect(self.socket_connections[sock])
        sock.close()
        self.messages_from_users.put(msg_ex)'''
        pass

    def server_connections_handler(self):
        read_sockets, wr_sock, error = select.select(
            list(self.socket_connections), list(self.socket_connections), [])
        for sock in read_sockets:
            try:
                data = sock.recv(MESSAGE_SIZE)
                if data:
                    self.extract_messages(data)
                else:
                    self._disconnect(sock)
            except OSError:
                self._disconnect(sock)

        while wr_sock and not self.messages_to_users.empty():
            message = self.send_message(self.messages_to_users.get())
            for sock in list(self.socket_connections):
                    if sock == self.server_socket:
                        continue
                    try:
                        print(message)
                        sock.send(message)
                    except OSError:
                        self._disconnect(sock)

    def send_message(self, message):
        return self._create_message(
            user=self.name,
            msg=message,
            host=self.host
        )

    def _create_message(self, msg='', user='', file='',
                        action='', host='', connections=None):
        host = str(self.server_socket.getsockname()) if not host else host
        data = \
        {
            'msg': msg,
            'user': user,
            'file': file,
            'action': action,
            'host': host,
            'connections': connections
        }
        return dumps(data).encode('utf-8')

    def _check_connections(self):
        for sock in list(self.socket_connections):
            if sock.fileno() == -1:
                self._disconnect(sock)

    def server_handler(self, disconnect_condition):
        self.socket_connections[self.server_socket] = self.server_socket.getsockname()
        while True:
            if len(self.socket_connections) > 1:
                self.server_connections_handler()

            if not self.incoming_connections.empty():
                    new_sock = self.incoming_connections.get()
                    adr = new_sock.getpeername()
                    self.socket_connections[new_sock] = adr
                    self._introduction_message(new_sock)

            try:
                new_sock, adr = self.server_socket.accept()
                self.socket_connections[new_sock] = adr
                self._introduction_message(new_sock)
            except OSError:
                pass

            self._check_connections()

            if disconnect_condition.is_set():
                break
