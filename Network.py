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

class ServerChat:
    def __init__(self, name):
        self.messages_from_users = Queue()
        self.messages_to_users = Queue()
        self.incoming_connections = Queue()
        self.lock = threading.RLock()
        self.exit_condition = threading.Event()
        self.is_server = False
        self.server_ip = None
        self.server_port = None
        self.name = name
        self.name_changed = False
        self.server_socket = None
        self._create_receiving_socket()
        self.host = self.server_ip + ', ' + str(self.server_port)
        self.host_connections = {self.host: self.name}  # dict key: host, value: user
        self.socket_connections = {}  # Key: socket, Value: (ip, port)

    def _create_receiving_socket(self):
        established = False
        while not established:
            try:
                self.server_ip = socket.gethostbyname(socket.getfqdn())
                self.server_port = random.randint(49151, 65535)
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.bind((self.server_ip, self.server_port))
                self.server_socket.settimeout(1)
                self.server_socket.listen(socket.SOMAXCONN)
                established = True
            except OSError:
                pass

    def extract_messages(self, messages):
        print('extracting ' + messages.decode())
        messages = [loads(x) for x in R_MSG.findall(messages.decode('utf-8'))]
        for msg in messages:
            if msg['file'] != '':
                pass
            if msg['action'] == 'connect':
                # adding host of the new user
                if msg['host'] not in self.host_connections or\
                                self.host_connections[msg['host']] != msg['user']:
                    with self.lock:
                        self.host_connections[msg['host']] = msg['user']
            if msg['action'] == 'disconnect':
                # removing host of the outgoing user
                with self.lock:
                    self.host_connections.pop(msg['host'])
            if msg['connections'] is not None:
                # finding unknown users
                new_connections = {x: y for x, y in msg['connections'] if x not in self.host_connections}
                msg['connections'] = new_connections
                if new_connections:
                    with self.lock:
                        self.host_connections.update(new_connections)
            self.messages_from_users.put(msg)

    def _introduction_message(self, sock):
        '''
        Sending known contacts and user's nickname to the new user
        :param sock:
        :return:
        '''
        connections = [[x, y] for x, y in self.host_connections.items() if x != self.host]
        msg = self.create_message(action='connect', host=self.host,
                                  connections=connections)
        try:
            sock.send(msg)
        except OSError:
            self._disconnect(sock)
        
    def _disconnect(self, sock):
        msg = self.create_message(action='disconnect')
        try:
            sock.send(msg)
        except OSError:
            pass
        finally:
            sock.close()
            del self.socket_connections[sock]

    def server_connections_handler(self):
        read_sockets, wr_sock, error = select.select(
            list(self.socket_connections), list(self.socket_connections), [])
        for sock in read_sockets:
            if sock == self.server_socket:
                conn, adr = sock.accept()
                self.socket_connections[conn] = adr
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
                        sock.send(message)
                    except OSError:
                        self._disconnect(sock)

    def send_message(self, message):
        return self.create_message(
            action='connect',
            msg=message,
        )

    def create_message(self, msg='', file='',
                        action='', connections=None, host=''):
        host = self.host
        user = self.name
        data = {
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

    def server_handler(self):
        self.socket_connections[self.server_socket] = self.server_socket.getsockname()
        while True:
            if len(self.socket_connections) > 1:
                self.server_connections_handler()
            else:
                try:
                    new_sock, adr = self.server_socket.accept()
                    self.socket_connections[new_sock] = adr
                    self._introduction_message(new_sock)
                except OSError:
                    pass

            if not self.incoming_connections.empty():
                    new_sock = self.incoming_connections.get()
                    adr = new_sock.getpeername()
                    self.socket_connections[new_sock] = adr
                    self._introduction_message(new_sock)

            if self.exit_condition.is_set():
                for conn in list(self.socket_connections):
                    self._disconnect(conn)
                break

            self._check_connections()
