import socket
import select
import random
import re
import base64
import threading
import os
from queue import Queue
import json

MESSAGE_SIZE = 64 * 1024 * 1024
R_MSG = re.compile("({.*?})")


class Network:
    def __init__(self, name):
        self.messages_from_users = Queue()
        self.messages_to_users = Queue()
        self.incoming_connections = Queue()
        self.lock = threading.RLock()
        self.exit_condition = threading.Event()
        self.server_ip = None
        self.server_port = None
        self.name = name
        self.name_changed = False
        self._files_to_send = {}
        self.receiving_socket = None
        self._create_receiving_socket()
        self.host = self.server_ip + ', ' + str(self.server_port)
        self.host_connections = {self.host: self.name}  # dict key: host, value: username
        self._socket_connections = {}  # Key: socket, Value: (ip, port)

    def _create_receiving_socket(self):
        established = False
        while not established:
            try:
                self.server_ip = socket.gethostbyname(socket.getfqdn())
                self.server_port = random.randint(49152, 65535)
                self.receiving_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.receiving_socket.bind((self.server_ip, self.server_port))
                self.receiving_socket.settimeout(1)
                self.receiving_socket.listen(socket.SOMAXCONN)
                established = True
            except OSError:
                pass

    @staticmethod
    def _get_ip():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(('8.8.8.8', 80))
            ip = sock.getsockname()[0]
        except OSError:
            ip = '127.0.0.1'
        finally:
            sock.close()
        return ip

    def extract_messages(self, messages, sock):
        messages = [json.loads(x) for x in R_MSG.findall(messages.decode('utf-8'))]
        for msg in messages:
            # adding host of the new user or updating name
            if msg['host'] not in self.host_connections or \
                            self.host_connections[msg['host']] != msg['user']:
                with self.lock:
                    self.host_connections[msg['host']] = msg['user']
            if msg['type'] == 'file':
                if msg['action'] == 'offer':
                    pass
                elif msg['action'] == 'get' \
                        and msg['address'] == self.host:
                    # got request on file
                    self._files_to_send[sock] = (msg['file_location'], msg['file_name'])
                elif msg['action'] == 'send':
                    self._download_file(msg)
                    msg['file'] = ''
            else:
                if msg['action'] == 'disconnect':
                    # removing host of the outgoing user
                    with self.lock:
                        self.host_connections.pop(msg['host'])
                if msg['connections'] is not None:
                    # appending unknown users
                    new_connections = {x: y for x, y in msg['connections'] if x not in self.host_connections}
                    msg['connections'] = new_connections
                    if new_connections:
                        with self.lock:
                            self.host_connections.update(new_connections)
            self.messages_from_users.put(msg)

    @staticmethod
    def _download_file(msg):
        path = os.path.join(os.getcwd(), 'Downloads', msg['file_name'])
        n = 1
        while os.path.exists(path):
            path = os.path.join(os.getcwd(), 'Downloads', '({})'.format(n) + msg['file_name'])
            n = n + 1
        with open(path, 'wb') as file:
            file.write(base64.b64decode(msg['file']))

    def _introduction_message(self):
        '''
        Sending known contacts and user's nickname to the new user
        :param sock:
        :return:
        '''
        connections = [[x, y] for x, y in self.host_connections.items() if x != self.host]
        msg = self.create_data(host=self.host,
                               connections=connections, user=self.name)
        return msg
        
    def _disconnect(self, sock):
        msg = self.create_data(action='disconnect', user=self.name,
                               host=self.host,)
        try:
            sock.send(msg)
        except OSError:
            pass
        finally:
            sock.close()
            del self._socket_connections[sock]

    def _connections_handler(self):
        read_sockets, wr_sock, error = select.select(
            list(self._socket_connections), list(self._socket_connections), [])
        for sock in read_sockets:
            if sock == self.receiving_socket:
                conn, adr = sock.accept()
                self._socket_connections[conn] = adr
                try:
                    conn.send(self._introduction_message())
                except OSError:
                    self._disconnect(conn)
            else:
                try:
                    data = sock.recv(MESSAGE_SIZE)
                    if data:
                        self.extract_messages(data, sock)
                    else:
                        self._disconnect(sock)
                except OSError:
                    self._disconnect(sock)

        while not self.messages_to_users.empty() or self.name_changed or self._files_to_send:
            if not self.messages_to_users.empty():
                message = self.messages_to_users.get()
            else:
                message = self._create_message(message='')
            for sock in list(self._socket_connections):
                    if sock == self.receiving_socket:
                        continue
                    try:
                        sock.send(message)
                        if sock in self._files_to_send:
                            self._send_file(sock)
                    except OSError:
                        self._disconnect(sock)
            self.name_changed = False

    def _send_file(self, sock):
        buffer = b''
        path = self._files_to_send[sock][0]
        file_name = self._files_to_send[sock][1]
        with open(path, 'rb') as f:
            buffer = base64.b64encode(f.read()).decode('utf-8')

        message = self.create_file_data(
            file=buffer,
            action='send',
            user=self.name,
            host=self.host,
            file_name=file_name
        )
        try:
            sock.send(message)
        except OSError:
            self._disconnect(sock)
        self._files_to_send.pop(sock)

    def _create_message(self, message):
        return self.create_data(
            host=self.host,
            msg=message,
            user=self.name
        )
    
    @staticmethod
    def create_file_data(file=None, action='', host='',
                         user='', file_name='', file_location='', address=''):
        data = {
            'address': address,
            'type': 'file',
            'file': file,
            'action': action,
            'host': host,
            'user': user,
            'file_location': file_location,
            'file_name': file_name
        }
        return json.dumps(data).encode('utf-8')
    
    @staticmethod
    def create_data(user='', host='', msg='',
                    action='connect', connections=None, address=''):
        data = {
            'address': address,
            'type': 'msg',
            'msg': msg,
            'user': user,
            'action': action,
            'host': host,
            'connections': connections
        }
        return json.dumps(data).encode('utf-8')

    def _check_connections(self):
        # removing closed sockets
        for sock in list(self._socket_connections):
            if sock.fileno() == -1:
                self._disconnect(sock)

    def server_handler(self):
        self._socket_connections[self.receiving_socket] = self.receiving_socket.getsockname()
        while True:
            if len(self._socket_connections) > 1:
                self._connections_handler()
            else:
                try:
                    new_sock, adr = self.receiving_socket.accept()
                    self.incoming_connections.put(new_sock)
                except OSError:
                    # waiting time exceeded
                    pass

            if not self.incoming_connections.empty():
                # appending new connections
                new_sock = self.incoming_connections.get()
                adr = new_sock.getpeername()
                self._socket_connections[new_sock] = adr
                try:
                    new_sock.send(self._introduction_message())
                except OSError:
                    self._disconnect(new_sock)

            if self.exit_condition.is_set():
                # closing all sockets and breaking while loop
                for conn in list(self._socket_connections):
                    self._disconnect(conn)
                break

            self._check_connections()
