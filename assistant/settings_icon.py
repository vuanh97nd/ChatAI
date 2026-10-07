"""Vector settings button; animate only on clicks, preserving native keyboard access."""
import math
from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPushButton
from .themes import recolor


class SettingsButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('settingsGear')
        self.setFixedSize(38, 38)
        self.setStyleSheet('QPushButton#settingsGear {border-radius:19px;padding:0;}')
        self.setAccessibleName('Cài đặt Chat AI')
        self.setToolTip('Cài đặt Chat AI')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self._angle = 0.0
        self._theme = 'dark'
        self._outline = self._gear_path()
        self._animation = QPropertyAnimation(self, b'angle', self)
        self._animation.setDuration(350)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.finished.connect(self._normalize_angle)
        self.clicked.connect(self.spin)

    @staticmethod
    def _gear_path():
        path = QPainterPath()
        for tooth in range(8):
            for offset, radius in ((3, 7.0), (9, 7.0), (13, 9.2),
                                   (32, 9.2), (36, 7.0), (42, 7.0)):
                angle = math.radians(tooth * 45 + offset)
                x, y = radius * math.cos(angle), radius * math.sin(angle)
                if tooth == 0 and offset == 3:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
        path.closeSubpath()
        return path

    def _get_angle(self):
        return self._angle

    def _set_angle(self, value):
        self._angle = float(value)
        self.update()

    angle = Property(float, _get_angle, _set_angle)

    def spin(self, checked=False):
        self._animation.stop()
        self._animation.setStartValue(self._angle)
        self._animation.setEndValue(self._angle + 180.0)
        self._animation.start()

    def _normalize_angle(self):
        self._set_angle(self._angle % 360.0)

    def set_theme(self, theme):
        recolor('', theme)  # Validate without adding a Qt dependency to palette helpers.
        self._theme = theme
        self.update()

    def paintEvent(self, event):
        # Qt paints the static circular background, hover, pressed and focus states.
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._angle)
        base = '#a8c7fa' if self.isChecked() or self.underMouse() or self.hasFocus() else '#9aa0a6'
        if not self.isEnabled():
            base = '#70757a'
        pen = QPen(QColor(recolor(base, self._theme)), 1.6)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._outline)
        painter.drawEllipse(QRectF(-3.0, -3.0, 6.0, 6.0))
        painter.end()
