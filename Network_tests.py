import unittest
from unittest import mock
import Network
import json
import base64
import os


class MyTestCase(unittest.TestCase):

    def test_receiving_get_request(self):
        chat = Network.Network('name')
        mock_socket = mock.Mock()
        msg = chat.create_file_data(file_location='local', file_name='name',
                                    action='get', address=chat.host)
        chat.extract_messages(msg, mock_socket)
        self.assertEqual(chat._files_to_send, {mock_socket:('local', 'name')})
        chat.receiving_socket.close()

    def test_accepting_new_connection(self):
        chat = Network.Network('name')
        chat.exit_condition.set()
        mock_recv_socket = mock.Mock()
        mock_new_sock = mock.Mock()
        mock_new_sock.getpeername.return_value = 'address'
        chat.receiving_socket.close()
        chat.receiving_socket = mock_recv_socket
        mock_recv_socket.accept.return_value = (mock_new_sock, 'address')
        chat.server_handler()
        mock_recv_socket.accept.assert_called_once()
        mock_new_sock.getpeername.assert_called_once()

    def test_sending_file(self):
        chat = Network.Network('name')
        mock_sock = mock.Mock()
        mock_sock.send.return_value = None
        chat._files_to_send[mock_sock] = (os.path.join(os.getcwd(), 'file'), 'file')
        with open('file', 'wb') as f:
            f.write(b'abc')
        chat._send_file(mock_sock)
        self.assertEqual(chat._files_to_send, {})
        mock_sock.send.assert_called_once()
        chat.receiving_socket.close()
        os.remove(os.path.join(os.getcwd(), 'file'))


    def test_server_has_connections(self):
        chat = Network.Network('name')
        chat.exit_condition.set()
        mock_sock = mock.Mock()
        chat._socket_connections[mock_sock] = 'address'
        mock_handler = mock.Mock()
        mock_handler.return_value = None
        chat._connections_handler = mock_handler
        chat.server_handler()
        mock_handler.assert_called_once()

    def test_removing_closed_sockets(self):
        chat = Network.Network('name')
        mock_sock1 = mock.Mock()
        mock_sock2 = mock.Mock()
        mock_sock1.fileno.return_value = -1
        mock_sock2.fileno.return_value = 1
        chat._socket_connections[mock_sock1] = None
        chat._socket_connections[mock_sock2] = None
        chat._check_connections()
        self.assertEqual(chat._socket_connections, {mock_sock2: None})
        chat.receiving_socket.close()

    def test_receiving_msg(self):
        chat = Network.Network('name')
        mock_sock = mock.Mock()
        message = chat._create_message('message')
        chat.extract_messages(message, mock_sock)
        self.assertEqual(chat.messages_from_users.get(), json.loads(message))
        chat.receiving_socket.close()

    def test_receiving_unknown_contacts(self):
        chat = Network.Network('name')
        mock_socket = mock.Mock()
        new_connections = [['host1', 'username1'], ['host2', 'username2']]
        message = chat.create_data(
            connections=new_connections,
            host='host2',
            user='username2',
        )
        chat.extract_messages(message, mock_socket)
        connections = {x: y for x, y in new_connections}
        chat.host_connections.pop(chat.host)
        self.assertEqual(connections, chat.host_connections)
        chat.receiving_socket.close()

    def test_disconnect(self):
        chat = Network.Network('name')
        mock_socket = mock.Mock()
        mock_socket.send = mock.Mock()
        mock_socket.close = mock.Mock()
        chat._socket_connections[mock_socket] = ''
        chat._disconnect(mock_socket)
        chat.receiving_socket.close()

        mock_socket.send.assert_called_once()
        mock_socket.close.assert_called_once()
        self.assertEqual(chat._socket_connections, {})

    def test_download_file(self):
        if not os.path.exists('Downloads'):
            os.mkdir('Downloads')
        file_data = base64.b64encode(b'abc').decode('utf-8')
        msg = json.loads(Network.Network.create_file_data(file=file_data, file_name='file_name'))
        Network.Network._download_file(msg)
        with open(r'Downloads\file_name') as f:
            text = f.read()
        self.assertTrue(os.path.exists(os.path.join(os.getcwd(), 'Downloads', 'file_name')))
        self.assertTrue(text == 'abc')
        os.remove(os.path.join(os.getcwd(), 'Downloads', 'file_name'))

if __name__ == '__main__':
    unittest.main()
