import unittest
import mock
import Network
import json
class MyTestCase(unittest.TestCase):

    def test_something(self):
        pass

    def test_receiving_file(self):
        pass

    def test_receiving_msg(self):
        chat = Network.Network('name')
        mock_sock = mock.Mock()
        message = chat._create_message('message')
        chat.extract_messages(message, mock_sock)
        self.assertEqual(chat.messages_from_users.get(), json.loads(message))
        chat.receiving_socket.close()

    def test_receiving_known_contacts(self):
        pass

    def test_receiving_unknown_contacts(self):
        chat = Network.Network('name')
        mock_socket = mock.Mock()
        new_connections = [['host1', 'username1'], ['host2', 'username2']]
        message = chat.create_data(
            connections=new_connections,
            host='host',
            user='user',
        )
        chat.extract_messages(message, mock_socket)
        connections = {x: y for x, y in new_connections}
        connections['host'] = 'user'
        connections[chat.host] = chat.name
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

    @mock.patch('Network.os')
    @mock.patch('Network.os.path')
    @mock.patch('Network.open')
    def test_download_file(self, mock_open, mock_os_path, mock_os):
        # chat = Network.Network('name')
        # mock_os.getcwd.return_value = 'o'
        # mock_os_path.exist.return_value = False
        # mock_os_path.join.return_value = r'path\patj=g'
        # mock_open.return_value = None
        # msg = Network.Network.create_file_data(
        #     action='',
        #     file_name='file',
        #     file='file',
        #     file_location='file_location'
        # )
        # chat._download_file(msg)
        # mock_os_path.assert_called_once()
        # mock_open.assert_called_once()
        # chat.receiving_socket.close()
        pass

if __name__ == '__main__':
    unittest.main()
