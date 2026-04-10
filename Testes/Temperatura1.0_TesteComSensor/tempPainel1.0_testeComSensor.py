import sys
import serial
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPainter, QColor, QFont

# Ajusta a porta se necessário
ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)

class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Temp Monitor")
        self.setGeometry(100, 100, 800, 480)

        self.temp = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(200)

    def update_data(self):
        try:
            linha = ser.readline().decode().strip()

            if linha:
                self.temp = float(linha)
                self.update()

        except:
            pass

    def paintEvent(self, event):
        painter = QPainter(self)

        # Fundo preto
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        # ===== COR BASEADA NA TEMP =====
        if self.temp < 30:
            cor = QColor(0, 200, 255)   # azul
            status = "FRIO"
        elif self.temp < 35:
            cor = QColor(255, 200, 0)   # amarelo
            status = "NORMAL"
        else:
            cor = QColor(255, 0, 0)     # vermelho
            status = "QUENTE"

        # ===== TEMPERATURA GRANDE =====
        painter.setPen(cor)
        painter.setFont(QFont("Arial", 80, QFont.Bold))
        painter.drawText(200, 250, f"{int(self.temp)}°C")

        # ===== TEXTO STATUS =====
        painter.setFont(QFont("Arial", 25))
        painter.drawText(300, 320, status)

        # ===== BARRA VISUAL =====
        max_temp = 120
        bar_width = 600
        filled = int((self.temp / max_temp) * bar_width)

        for i in range(0, bar_width, 10):
            if i < filled:
                painter.fillRect(100 + i, 380, 8, 30, cor)
            else:
                painter.fillRect(100 + i, 380, 8, 30, QColor(50, 50, 50))

app = QApplication(sys.argv)
window = Dashboard()
window.show()
sys.exit(app.exec_())
