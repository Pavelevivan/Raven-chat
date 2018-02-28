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

R_REG = re.compile("<REG>(.*?)<REG>")
R_EX = re.compile("<EX>(.*?)<EX>")


class GUIChat(QMainWindow):
    def __init__(self, server, exit_condition):
        super().__init__()
        self.exit_condition = exit_condition
        self.server = server
        self.timer = QTimer()
        self.timer.timeout.connect(self.show_message)
        self.timer.start(500)
        self.online_connections = {}

        self.setWindowIcon(QIcon(r"pictures\raven.jpg"))
        self.setWindowTitle("RavenChat")
        self.main_widget = QWidget()
        self.main_widget.grid = QGridLayout()

        self.user_id = QLabel('Your ip address: {}'.format(self.server.server_ip), self)
        self.user_port = QLabel("Your port: {}".format(self.server.server_port), self)
        self.user_name = QLabel("Your nickname: {}".format(self.server.name), self)
        self.online_lable = QLabel("Users online", self)

        qsb = QScrollBar()
        qsb.setTracking(False)
        qsb.setSliderPosition(qsb.maximum())

        self.users_online = QTextEdit()
        self.users_online.setReadOnly(True)
        self.users_online.setHorizontalScrollBar(qsb)
        self.users_online.setMaximumSize(150, 200)

        self.chat_window = QTextEdit()
        self.chat_window.setReadOnly(True)
        self.chat_window.setHorizontalScrollBar(qsb)

        self.sending_button = QPushButton("Send", self)
        self.send_line = QLineEdit()
        self.sending_button.clicked.connect(self.send_message)

        self.change_nickname_button = QPushButton("Change nickname", self)
        self.change_nickname_button.clicked.connect(self.change_nickname)

        self.create_connection_button = QPushButton("Create new connection", self)
        self.create_connection_button.clicked.connect(self.create_connection)

        self.main_widget.grid.addWidget(self.online_lable, 2, 1)
        self.main_widget.grid.addWidget(self.user_id, 1, 2)
        self.main_widget.grid.addWidget(self.user_port, 1, 3)
        self.main_widget.grid.addWidget(self.user_name, 1, 4)

        self.main_widget.grid.addWidget(self.create_connection_button,2, 2)
        self.main_widget.grid.addWidget(self.change_nickname_button, 2, 4)

        self.main_widget.grid.addWidget(self.users_online, 3, 1)
        self.main_widget.grid.addWidget(self.chat_window, 3, 2, 1, 1)
        self.main_widget.grid.addWidget(self.sending_button, 4, 3)
        self.main_widget.grid.addWidget(self.send_line, 4, 2)
        self.main_widget.setLayout(self.main_widget.grid)
        self.setCentralWidget(self.main_widget)
        self.main_widget.setGeometry(300, 300, 300, 300)

    def change_nickname(self):
        name, ok_name = QInputDialog.getText(QInputDialog(), "Changing nickname", "Write your new nickname")
        if name and ok_name:
            self.server.name = name
            self.user_name.setText("Your nickname: {}".format(name))

    def show_message(self):

        while not self.server.messages_from_users.empty():
            msg = self.server.messages_from_users.get()
            print('show message')
            print(msg)
            new_conn = R_REG.match(msg)
            if new_conn:
                name, address = new_conn.group(1).split(':')
                self.change_online_connections(name, address, 'update')
            elif R_EX.match(msg):
                address = R_EX.match(msg).group(1)
                print('exit')
                self.change_online_connections(None, address, 'delete')
            else:
                self.chat_window.append("{}".format(msg))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        if event.key() == Qt.Key_Enter:
            self.send_message()
        else:
            print(event.key())
            event.ignore()

    def send_file(self):
        pass

    def send_message(self):
        message = self.server.name + ": " + self.send_line.text()
        self.server.messages_to_users.put(message)
        self.chat_window.append(message)
        self.send_line.clear()

    def closeEvent(self, event):
        reply = QMessageBox.question(QMessageBox(), "Warning", "Are you sure to quit",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.exit_condition.set()
        else:
            event.ignore()

    def change_online_connections(self, name, address, mode):
        '''
        :param address: Обновляет значение словаря online_connections адресс/имя в зависимости от mode
        адресс подключенного сокета
        :param mode: Обновление словаря контактов
        :param name: Обновлённое имя пользователя
        :return:
        '''
        print('change online connections name:{}, address:{}'.format(name, address))
        if mode == "update":
            self.online_connections[address] = name
        if mode == "delete" \
                and address in self.online_connections:
                self.online_connections.pop(address)
        self.users_online.clear()
        for adr, name in self.online_connections.items():
            self.users_online.append(name + adr)

    def create_connection(self):
        ip, ok_ip = QInputDialog.getText(QInputDialog(), "Creating connection", "Input ip address")
        ip = GUIChat.check_ip(ip)
        if ok_ip and ip:
            port, ok_port = QInputDialog.getText(QInputDialog(), "Creating connection", "Input port address")
            port = GUIChat.check_port(port)
            if ok_port and port:
                try:
                    # Создание нового подключения через новый сокет
                    sock = socket.create_connection((ip, int(port)))
                    self.server.incoming_connections.put(sock)
                    msg = QMessageBox.information(QMessageBox(), "Notification", "The connection is established")
                except OSError as e:
                    print(e.strerror, e.errno)
                    msg = QMessageBox.information(QMessageBox(),
                                                  "Warning", "Sorry, you didn't connected to this user,"
                                                             " check ip, port and try again")
                except Exception as e:
                    print(e.args)
            else:
                msg = QMessageBox.information(QMessageBox(),
                                              "Warning", "Wrong port number, check and try again")
        else:
            msg = QMessageBox.information(QMessageBox(),
                                          "Warning", "Ip address was incorrect, check and try again")

    @staticmethod
    def check_port(port):
        if not port:
            return None
        port = re.match(r'\d{4,5}', port)
        return port.group(0) if port else None

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
    server_thread = threading.Thread(target=server.server_handler, args=(exit_condition,))
    ex = GUIChat(server, exit_condition)
    server_thread.start()
    ex.show()
    sys.exit(app.exec_())