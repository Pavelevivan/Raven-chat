import sys
import re
import socket
import threading
import os
import Network

try:
    from PyQt5.QtWidgets import QApplication, QWidget,\
        QPushButton, QMessageBox, QMainWindow, QInputDialog,\
        QLabel, QTextEdit, QGridLayout, QAction, QLineEdit, QScrollBar, QFileDialog
    from PyQt5.QtGui import QIcon
    from PyQt5.QtCore import pyqtSlot, QTimer, Qt
except ImportError:
    sys.exit("PyQt5 not found")

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

        self.setWindowIcon(QIcon(os.path.join('pictures', 'raven.jpg')))
        self.setWindowTitle("RavenChat")

        # creating main labels
        self.user_host = QLabel('Your host: ({}, {})'.format(self.server.server_ip, self.server.server_port), self)
        self.user_name = QLabel("Your name: {}".format(self.server.name), self)
        self.online_label = QLabel("Users online", self)
        
        # creating scroll bar
        qsb = QScrollBar()
        qsb.setTracking(False)
        qsb.setSliderPosition(qsb.maximum())
        
        # creating window to show users online
        self.users_online = QTextEdit()
        self.users_online.setReadOnly(True)
        self.users_online.setHorizontalScrollBar(qsb)
        self.users_online.setMaximumWidth(170)
        self.users_online.setMinimumWidth(170)

        # creating window to show chat messages
        self.chat_window = QTextEdit()
        self.chat_window.setReadOnly(True)
        self.chat_window.setHorizontalScrollBar(qsb)

        # creating button to send messages
        self.sending_button = QPushButton(self)
        self.sending_button.setIcon(QIcon(os.path.join('pictures', 'feather.png')))
        self.sending_button.setMaximumSize(100, 50)
        self.sending_button.clicked.connect(self.send_message)

        # creating menu
        self.create_connection_action = QAction("Create connection")
        self.create_connection_action.triggered.connect(self.create_connection)
        self.change_name_action = QAction("Change name")
        self.change_name_action.triggered.connect(self.change_name)
        bar = self.menuBar()
        self.bar = bar.addMenu('Settings')
        self.bar.addAction(self.create_connection_action)
        self.bar.addAction(self.change_name_action)

        # creating line to write messages
        self.send_line = QLineEdit()

        # creating button to send files
        self.file_sending_button = QPushButton(self)
        self.file_sending_button.setIcon(QIcon(os.path.join('pictures', 'file.png')))
        self.file_sending_button.setMaximumSize(70, 50)
        self.file_sending_button.clicked.connect(self.offer_file)

        self.main_widget = QWidget()
        self.main_widget.grid = QGridLayout()

        # adding labels, windows and buttons in grid
        self.main_widget.grid.addWidget(self.user_host, 1, 1, 1, 2)
        self.main_widget.grid.addWidget(self.user_name, 2, 1, 1, 2)
        self.main_widget.grid.addWidget(self.online_label, 3, 1, 1, 2)
        self.main_widget.grid.addWidget(self.users_online, 4, 1, 1, 2)

        self.main_widget.grid.addWidget(self.chat_window, 1, 3, 4, 1)
        self.main_widget.grid.addWidget(self.send_line, 5, 3)
        self.main_widget.grid.addWidget(self.sending_button, 5, 2)
        self.main_widget.grid.addWidget(self.file_sending_button, 5, 1)
        self.main_widget.setLayout(self.main_widget.grid)
        self.setCentralWidget(self.main_widget)
        self.main_widget.setGeometry(300, 300, 300, 300)
        self.update_online_connections()
        self.create_downloads_folder()

    @staticmethod
    def create_downloads_folder():
        if not os.path.exists(os.path.join(os.getcwd(), 'Downloads')):
            os.mkdir(os.path.join(os.getcwd(), 'Downloads'))

    def change_name(self):
        name, ok_name = QInputDialog.getText(QInputDialog(), "Changing name", "Write your new name")
        if name and ok_name:
            self.server.name = name
            self.server.name_changed = True
            self.user_name.setText("Your name: {}".format(name))
            self.server.host_connections[self.server.host] = name
            self.update_online_connections()

    def show_message(self):
        while not self.server.messages_from_users.empty():
            msg = self.server.messages_from_users.get()
            if msg['type'] == 'file':
                if msg['action'] == 'offer':
                    self.notify_about_offered_file(msg)
                if msg['action'] == 'send':
                    self.notify_about_download(msg)
            else:
                if msg['connections'] is not None:
                    self.notify_about_new_users(msg['connections'])
                if msg['action'] == 'connect' or msg['action'] == 'disconnect':
                    self.update_online_connections()
                if msg['msg'] != '':
                    self.chat_window.append(msg['user'] + ': ' + msg['msg'])

    def notify_about_download(self, msg):
        inf = QMessageBox.information(self, 'Notification', 'You have received a file: {}, from: {}'
                                      .format(msg['file_name'], msg['user']))

    def notify_about_offered_file(self, msg):
        answer = QMessageBox.question(self, "Notification", "{} offered you a file {}. Do you want to receive it?"
                                      .format(msg['user'], msg['file_name']), QMessageBox.Yes, QMessageBox.No)
        if answer == QMessageBox.Yes:
            message = Network.Network.create_file_data(
                file_name=msg['file_name'],
                file_location=msg['file_location'],
                user=self.server.name,
                action='get',
                host=self.server.host,
                address=msg['host']
            )
            self.server.messages_to_users.put(message)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        if event.key() == Qt.Key_Enter:
            self.send_message()
        else:
            event.ignore()
        
    def offer_file(self):
        name = QFileDialog.getOpenFileName(self, 'Open file', os.getcwd())
        if name[0] == '':
            return

        r_fname = re.compile(r'(([a-zA-Z0-9._])*)$')
        file_name = r_fname.search(name[0]).group()
        file_location = os.path.normpath(name[0])
        msg = QMessageBox.question(self, '', 'Do you want to send file {}?'.format(file_name),
                                   QMessageBox.Yes | QMessageBox.No)
        if msg == QMessageBox.No:
            return
        message = Network.Network.create_file_data(
            file=None,
            action='offer',
            host=self.server.host,
            user=self.server.name,
            file_location=file_location,
            file_name=file_name
        )
        self.server.messages_to_users.put(message)

    def send_message(self):
        text = self.send_line.text()
        if not text:
            return
        message = Network.Network.create_data(
            user=self.server.name,
            host=self.server.host,
            msg=text
        )
        self.server.messages_to_users.put(message)
        self.chat_window.append(self.server.name + ': ' + text)
        self.send_line.clear()

    def closeEvent(self, event):
        reply = QMessageBox.question(QMessageBox(), "Warning", "Are you sure to quit",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.server.exit_condition.set()
        else:
            event.ignore()

    def update_online_connections(self):
        self.users_online.clear()
        with self.server.lock:
            for host, name in self.server.host_connections.items():
                self.users_online.append(name + ': ' + '(' + host + ')')

    def notify_about_new_users(self, connections):
        for new_connection in connections:
            answer = QMessageBox.information(self, 'Detected new users', str(new_connection))
            ip, port = new_connection.split(', ')
            port = int(port)
            try:
                sock = socket.create_connection((ip, port))
                self.server.incoming_connections.put(sock)
            except OSError:
                msg = QMessageBox.information(QInputDialog(), "Warning", "Sorry, you didn't connect to this user {}{}"
                                              .format(ip, str(port), new_connection[1]))

    def create_connection(self):
        ip, ok_ip = QInputDialog.getText(QInputDialog(),
                                         "Creating connection", "Input ip address",)
        if not ok_ip:
            return
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
    server = Network.Network("User")
    server_thread = threading.Thread(target=server.server_handler, args=())
    ex = GUIChat(server)
    server_thread.start()
    ex.show()
    sys.exit(app.exec_())