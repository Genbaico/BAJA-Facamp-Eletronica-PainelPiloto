import sys
import json
import serial
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont
import random

##ser = serial.Serial('/dev/ttyUSB0', 115200)

class Tela(QWidget):
    def _init_(self):
        super()._init_()

        self.setWindowTitle("Dashboard")
        self.setStyleSheet("background-color: black;")

        self.layout = QVBoxLayout()

        self.label_rpm = QLabel("RPM: 0")
        self.label_rpm.setFont(QFont("Arial", 40))
        self.label_rpm.setStyleSheet("color: lime;")

        self.layout.addWidget(self.label_rpm)

        self.setLayout(self.layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.atualizar)
        self.timer.start(100)  # atualiza a cada 100ms

    # def atualizar(self):
    #     try:
    #         linha = ser.readline().decode().strip()
    #         dados = json.loads(linha)

    #         rpm = dados["rpm"]
    #         self.label_rpm.setText(f"RPM: {rpm}")

    #     except:
    #         pass

    def atualizar(self):
        rpm_fake = random.randint(800, 6000)
        self.label_rpm.setText(f"RPM: {rpm_fake}")

app = QApplication(sys.argv)
tela = Tela()
tela.show()
sys.exit(app.exec_())