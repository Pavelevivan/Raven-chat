import sys
import re
import socket
import threading
import queue
from multiprocessing import Process, Pipe
from PyQt5.QtWidgets import QApplication, QWidget,\
    QPushButton, QMessageBox, QMainWindow, QInputDialog,\
    QLabel, QTextEdit, QGridLayout, QScrollArea, QLineEdit, QScrollBar, QKeyEventTransition
import queue
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot, QTimer, Qt
import Network

received_file_message = ('User sent you a file. Do you want to save it?'
'(Yes\\No)')


class GUIChat(QMainWindow):
    def __init__(self, server):
        super().__init__()
        self.exit_condition = exit_condition
        self.server = server
        self.timer = QTimer()
        self.timer.timeout.connect(self.show_message)
        self.timer.start(500)

        # setting title and icon
        self.setWindowIcon(QIcon(r"pictures\raven.jpg"))
        self.setWindowTitle("RavenChat")

        # creating main labels
        self.user_id = QLabel('Your ip address: {}'.format(self.server.server_ip), self)
        self.user_port = QLabel("Your port: {}".format(self.server.server_port), self)
        self.user_name = QLabel("Your nickname: {}".format(self.server.name), self)
        self.online_label = QLabel("Users online", self)
        
        # creating scroll bar
        qsb = QScrollBar()
        qsb.setTracking(False)
        qsb.setSliderPosition(qsb.maximum())
        
        # creating window to show users online
        self.users_online = QTextEdit()
        self.users_online.setReadOnly(True)
        self.users_online.setHorizontalScrollBar(qsb)
        self.users_online.setMaximumSize(150, 200)

        # creating window to show chat messages
        self.chat_window = QTextEdit()
        self.chat_window.setReadOnly(True)
        self.chat_window.setHorizontalScrollBar(qsb)

        # creating button to send messages
        self.sending_button = QPushButton(self)
        self.sending_button.setIcon(QIcon(r"pictures\feather.png"))
        self.sending_button.setMaximumSize(200, 100)
        self.sending_button.clicked.connect(self.send_message)

        # creating line to write messages
        self.send_line = QLineEdit()

        # creating button to send files
        self.file_sending_button = QPushButton(self)
        self.file_sending_button.setIcon(QIcon(r'pictures\file.png'))
        self.file_sending_button.setMaximumSize(30, 50)

        # creating button to change username
        self.change_username_button = QPushButton("Change nickname", self)
        self.change_username_button.clicked.connect(self.change_username)

        # creating button to create connections
        self.create_connection_button = QPushButton("Create new connection", self)
        self.create_connection_button.clicked.connect(self.create_connection)

        self.main_widget = QWidget()
        self.main_widget.grid = QGridLayout()

        # adding labels, windows and buttons in grid
        self.main_widget.grid.addWidget(self.online_label, 2, 1)
        self.main_widget.grid.addWidget(self.user_id, 1, 2)
        self.main_widget.grid.addWidget(self.user_port, 1, 3)
        self.main_widget.grid.addWidget(self.user_name, 1, 4)

        self.main_widget.grid.addWidget(self.create_connection_button,2, 2)
        self.main_widget.grid.addWidget(self.change_username_button, 2, 4)

        self.main_widget.grid.addWidget(self.users_online, 3, 1)
        self.main_widget.grid.addWidget(self.chat_window, 3, 2, 1, 1)
        self.main_widget.grid.addWidget(self.send_line, 4, 2)
        self.main_widget.grid.addWidget(self.sending_button, 4, 3)
        self.main_widget.grid.addWidget(self.file_sending_button, 4, 4)
        self.main_widget.setLayout(self.main_widget.grid)
        self.setCentralWidget(self.main_widget)
        self.main_widget.setGeometry(300, 300, 300, 300)

    def change_username(self):
        name, ok_name = QInputDialog.getText(QInputDialog(), "Changing nickname", "Write your new nickname")
        if name and ok_name:
            with self.server.lock:
                self.server.name = name
                self.user_name.setText("Your nickname: {}".format(name))
                self.server.host_connections[self.server.host] = name
                self.update_online_connections()

    def show_message(self):
        while not self.server.messages_from_users.empty():
            msg = self.server.messages_from_users.get()
            print('show message', msg)
            if msg['connections']:
                self.inform_about_new_users(msg['connections'])
            if msg['action'] == 'connect' or msg['action'] == 'disconnect':
                self.update_online_connections()
            if msg['msg'] != '':
                self.chat_window.append(msg['user'] + ': ' + msg['msg'])

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        if event.key() == Qt.Key_Enter:
            self.send_message()
        else:
            event.ignore()

    def send_file(self):
        pass

    def send_message(self):
        message = self.send_line.text()
        if not message:
            return
        self.server.messages_to_users.put(message)
        self.chat_window.append(self.server.name + ':' + message)
        self.send_line.clear()

    def closeEvent(self, event):
        reply = QMessageBox.question(QMessageBox(), "Warning", "Are you sure to quit",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.server.exit_condition.set()
        else:
            event.ignore()

    def update_online_connections(self):
        '''
        :param address: Обновляет значение словаря online_connections адресс/имя в зависимости от mode
        адресс подключенного сокета
        :param mode: Обновление словаря контактов
        :param name: Обновлённое имя пользователя
        :return:
        '''
        print('updating')
        self.users_online.clear()
        with self.server.lock:
            for host, name in self.server.host_connections.items():
                self.users_online.append(name + ': ' + host)

    def inform_about_new_users(self, connections):
        for new_connection in connections:
            answer = QMessageBox.question(self, 'Detected new users', "Do you want to connect to these users \n" +
                                          str(new_connection),
                                          QMessageBox.Yes | QMessageBox.No)
            if answer == QMessageBox.Yes:
                ip, port = new_connection.split(', ')
                port = int(port)
                try:
                    sock = socket.create_connection((ip, port))
                    self.server.incoming_connections.put(sock)
                except OSError:
                    msg = QMessageBox.information(self, "Warning", "Sorry, you didn't connect to this user {}{}"
                                                  .format(str(ip, port), new_connection[1]))

    def create_connection(self):
        ip, ok_ip = QInputDialog.getText(self,
                                         "Creating connection", "Input ip address",)
        ip = GUIChat.check_ip(ip)
        if ok_ip and ip:
            port, ok_port = QInputDialog.getInt(self,
                                                "Creating connection", "Input port address")
            if ok_port and port:
                try:
                    # Creating new connection with input ip and port
                    sock = socket.create_connection((ip, int(port)), timeout=3)
                    self.server.incoming_connections.put(sock)
                    msg = QMessageBox.information(self,
                                                  "Notification", "The connection is established",)
                except OSError as e:
                    msg = QMessageBox.information(self,
                                                  "Warning", "Sorry, you didn't connect to this user,"
                                                             " check ip, port and try again")
            else:
                msg = QMessageBox.information(self,
                                              "Warning", "Wrong port number, check and try again")
        else:
            msg = QMessageBox.information(self,
                                          "Warning", "Ip address was incorrect, check and try again")

    @staticmethod
    def check_ip(ip):
        ip_range = "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\." \
                   "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\." \
                   "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\." \
                   "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
        if not ip:
            return None
        pattern = re.compile(ip_range)
        found = pattern.match(ip)
        if found:
            return found.group(0)
        else:
            return None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    exit_condition = threading.Event()
    server = Network.ServerChat("Nickname")
    server_thread = threading.Thread(target=server.server_handler, args=())
    ex = GUIChat(server)
    server_thread.start()
    ex.show()
    sys.exit(app.exec_())