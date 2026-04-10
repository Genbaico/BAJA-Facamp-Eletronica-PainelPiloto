import sys
import random
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPainter, QColor, QFont

class Dashboard(QWidget):
    def _init_(self):
        super()._init_()
        self.setWindowTitle("FT Style Dashboard")
        self.setGeometry(100, 100, 800, 480)

        self.rpm = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_rpm)
        self.timer.start(100)

    def update_rpm(self):
        self.rpm = random.randint(800, 8000)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        # Fundo preto
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        # ===== TEXTO RPM GRANDE =====
        painter.setPen(QColor(0, 255, 0))
        painter.setFont(QFont("Arial", 60, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, str(self.rpm))

        # ===== TEXTO "RPM" =====
        painter.setFont(QFont("Arial", 20))
        painter.drawText(350, 300, "RPM")

        # ===== BARRA ESTILO SHIFT LIGHT =====
        bar_width = 600
        bar_height = 30
        x = 100
        y = 350

        max_rpm = 8000
        filled = int((self.rpm / max_rpm) * bar_width)

        for i in range(0, bar_width, 10):
            if i < filled:
                if self.rpm < 4000:
                    color = QColor(0, 255, 0)   # verde
                elif self.rpm < 6500:
                    color = QColor(255, 255, 0) # amarelo
                else:
                    color = QColor(255, 0, 0)   # vermelho
            else:
                color = QColor(50, 50, 50)

            painter.fillRect(x + i, y, 8, bar_height, color)

        # ===== REDLINE INDICADOR =====
        painter.setPen(QColor(255, 0, 0))
        painter.setFont(QFont("Arial", 15))
        painter.drawText(100, 400, "REDLINE")

app = QApplication(sys.argv)
window = Dashboard()
window.show()
sys.exit(app.exec_())