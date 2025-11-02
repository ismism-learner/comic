import sys
import json
import base64
import io
from rembg import remove

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QToolBar, QMenuBar,
    QVBoxLayout, QPushButton, QLineEdit, QListWidget,
    QColorDialog, QDockWidget, QListWidgetItem,
    QInputDialog, QMessageBox, QFileDialog
)
from PyQt6.QtGui import (
    QAction, QPainter, QPen, QBrush, QCursor,
    QPixmap, QColor, QFontMetrics
)
from PyQt6.QtCore import (
    Qt, QPoint, QRect, QUrl, QBuffer,
    QByteArray, QIODevice
)


class CharacterManager(QWidget):
    """
    A widget for managing characters and their associated colors.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.characters = {}  # {name: QColor}
        self.current_character = None
        self.selected_color = QColor(Qt.GlobalColor.black)

        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.char_list = QListWidget()
        self.char_list.itemClicked.connect(self.select_character)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Character Name")

        self.color_button = QPushButton("Choose Color")
        self.color_button.clicked.connect(self.choose_color)

        self.add_button = QPushButton("Add Character")
        self.add_button.clicked.connect(self.add_character)

        self.layout.addWidget(self.char_list)
        self.layout.addWidget(self.name_input)
        self.layout.addWidget(self.color_button)
        self.layout.addWidget(self.add_button)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_color = color
            self.color_button.setStyleSheet(f"background-color: {color.name()}")

    def add_character(self):
        name = self.name_input.text()
        if name and name not in self.characters:
            self.characters[name] = self.selected_color
            list_item = QListWidgetItem(name)
            list_item.setForeground(QBrush(self.selected_color))
            self.char_list.addItem(list_item)
            self.name_input.clear()

    def select_character(self, item):
        self.current_character = item.text()

    def get_current_character_color(self):
        if self.current_character:
            return self.characters.get(self.current_character, QColor(Qt.GlobalColor.black))
        return QColor(Qt.GlobalColor.black)

    def clear_characters(self):
        self.characters = {}
        self.char_list.clear()
        self.current_character = None

    def load_characters(self, characters_data):
        self.clear_characters()
        for name, color_hex in characters_data.items():
            color = QColor(color_hex)
            self.characters[name] = color
            item = QListWidgetItem(name)
            item.setForeground(QBrush(color))
            self.char_list.addItem(item)


class Canvas(QWidget):
    """
    The main canvas for drawing comic panels and text.
    Handles all user interactions like drawing, moving, resizing, and drag/drop.
    """
    def __init__(self, parent=None, character_manager=None):
        super().__init__(parent)
        self.character_manager = character_manager

        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        self.items = []  # Unified list for panels and text
        self.current_rect_for_drawing = None
        self.start_point = None
        self.selected_item_index = -1

        self.canvas_mode = "panel"      # "panel" or "text"
        self.interaction_mode = "none"  # "none", "draw", "move", "resize"
        self.resize_handle = None
        self.move_offset = QPoint()

    def clear_canvas(self):
        self.items = []
        self.selected_item_index = -1
        self.update()

    def load_items(self, items_data):
        self.clear_canvas()
        for item_data in items_data:
            rect = QRect(*item_data['rect'])
            item = {'type': item_data['type'], 'rect': rect}

            if item['type'] == 'panel':
                item['image'] = None
                if item_data.get('image_base64'):
                    ba = QByteArray(base64.b64decode(item_data['image_base64']))
                    pixmap = QPixmap()
                    pixmap.loadFromData(ba, "PNG")
                    item['image'] = pixmap
            elif item['type'] == 'text':
                item['text'] = item_data['text']
                item['color'] = QColor(*item_data['color'])

            self.items.append(item)
        self.update()

    # --- Event Handlers ---

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            file_path = event.mimeData().urls()[0].toLocalFile()
            item_index = self.find_item(event.position().toPoint())

            if item_index != -1 and self.items[item_index]['type'] == 'panel':
                pixmap = QPixmap(file_path)
                self.items[item_index]['image'] = pixmap
                self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.canvas_mode == "text":
            self.add_text_item(event.pos())
            return

        handle = self.get_handle_at_pos(event.pos())
        item_index = self.find_item(event.pos())

        if handle:
            self.interaction_mode = "resize"
            self.resize_handle = handle
        elif item_index != -1:
            self.interaction_mode = "move"
            self.selected_item_index = item_index
            self.move_offset = event.pos() - self.items[item_index]['rect'].topLeft()
        else:
            self.interaction_mode = "draw"
            self.selected_item_index = -1
            self.start_point = event.pos()
            self.current_rect_for_drawing = QRect(self.start_point, event.pos())

        self.update()

    def mouseMoveEvent(self, event):
        if self.interaction_mode == "resize":
            self._handle_resize(event)
        elif self.interaction_mode == "move":
            self._handle_move(event)
        elif self.interaction_mode == "draw":
            self._handle_draw(event)
        else:  # "none"
            self._update_cursor(event)

        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.interaction_mode == "draw" and self.current_rect_for_drawing:
            new_panel = {'type': 'panel', 'rect': self.current_rect_for_drawing, 'image': None}
            self.items.append(new_panel)
            self.selected_item_index = len(self.items) - 1

        if self.interaction_mode == "draw" and self.start_point == event.pos() and self.find_item(event.pos()) == -1:
            self.selected_item_index = -1

        self.interaction_mode = "none"
        self.current_rect_for_drawing = None
        self.start_point = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for i, item in enumerate(self.items):
            if item['type'] == 'panel':
                self._draw_panel(painter, item)
            elif item['type'] == 'text':
                self._draw_text(painter, item)

            if i == self.selected_item_index:
                self._draw_selection_handles(painter, item)

        if self.current_rect_for_drawing:
            self._draw_drawing_rect(painter)

    # --- Helper Methods ---

    def _handle_resize(self, event):
        item_rect = self.items[self.selected_item_index]['rect']
        if self.resize_handle == "topLeft":
            item_rect.setTopLeft(event.pos())
        elif self.resize_handle == "topRight":
            item_rect.setTopRight(event.pos())
        elif self.resize_handle == "bottomLeft":
            item_rect.setBottomLeft(event.pos())
        elif self.resize_handle == "bottomRight":
            item_rect.setBottomRight(event.pos())
        self.items[self.selected_item_index]['rect'] = item_rect.normalized()

    def _handle_move(self, event):
        self.items[self.selected_item_index]['rect'].moveTopLeft(event.pos() - self.move_offset)

    def _handle_draw(self, event):
        self.current_rect_for_drawing = QRect(self.start_point, event.pos()).normalized()

    def _update_cursor(self, event):
        handle = self.get_handle_at_pos(event.pos())
        if handle:
            if handle in ["topLeft", "bottomRight"]:
                self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.SizeBDiagCursor))
        elif self.find_item(event.pos()) != -1:
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def _draw_panel(self, painter, item):
        item_rect = item['rect']
        painter.setPen(QPen(Qt.GlobalColor.black, 2, Qt.PenStyle.SolidLine))
        painter.setBrush(QBrush(Qt.GlobalColor.white))
        painter.drawRect(item_rect)

        if item['image']:
            pixmap = item['image']
            scaled = pixmap.scaled(item_rect.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            x = item_rect.x() + (item_rect.width() - scaled.width()) / 2
            y = item_rect.y() + (item_rect.height() - scaled.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)

    def _draw_text(self, painter, item):
        painter.setPen(QPen(item['color']))
        painter.drawText(item['rect'], Qt.TextFlag.TextWordWrap, item['text'])

    def _draw_selection_handles(self, painter, item):
        item_rect = item['rect']
        painter.setPen(QPen(Qt.GlobalColor.blue, 3, Qt.PenStyle.SolidLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(item_rect)

        handles = self.get_resize_handles(item_rect)
        painter.setBrush(QBrush(Qt.GlobalColor.blue))
        for handle in handles.values():
            painter.drawRect(handle)

    def _draw_drawing_rect(self, painter):
        painter.setPen(QPen(Qt.GlobalColor.red, 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.current_rect_for_drawing)

    def find_item(self, point):
        for i in range(len(self.items) - 1, -1, -1):
            if self.items[i]['rect'].contains(point):
                return i
        return -1

    def get_resize_handles(self, rect):
        handles = {}
        handles["topLeft"] = QRect(rect.topLeft().x() - 4, rect.topLeft().y() - 4, 8, 8)
        handles["topRight"] = QRect(rect.topRight().x() - 4, rect.topRight().y() - 4, 8, 8)
        handles["bottomLeft"] = QRect(rect.bottomLeft().x() - 4, rect.bottomLeft().y() - 4, 8, 8)
        handles["bottomRight"] = QRect(rect.bottomRight().x() - 4, rect.bottomRight().y() - 4, 8, 8)
        return handles

    def get_handle_at_pos(self, pos):
        if self.selected_item_index != -1:
            handles = self.get_resize_handles(self.items[self.selected_item_index]['rect'])
            for handle, rect in handles.items():
                if rect.contains(pos):
                    return handle
        return None

    def add_text_item(self, pos):
        text, ok = QInputDialog.getText(self, 'Add Text', 'Enter your text:')
        if ok and text:
            color = self.character_manager.get_current_character_color()
            font_metrics = QFontMetrics(self.font())
            text_rect = font_metrics.boundingRect(text)
            text_rect.moveTopLeft(pos)

            new_text = {'type': 'text', 'rect': text_rect, 'text': text, 'color': color}
            self.items.append(new_text)
            self.selected_item_index = len(self.items) - 1
            self.update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Comic Creator")
        self.setGeometry(100, 100, 1000, 700)

        self.character_manager = CharacterManager(self)
        self.canvas = Canvas(self, self.character_manager)
        self.setCentralWidget(self.canvas)

        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(self.toolbar)
        self._create_toolbar()

        self.menu_bar = self.menuBar()
        self._create_menu_bar()

        self._create_character_dock()

    def _create_character_dock(self):
        self.character_dock = QDockWidget("Characters", self)
        self.character_dock.setWidget(self.character_manager)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.character_dock)

    def _create_toolbar(self):
        panel_mode_action = QAction("Panel Mode", self, checkable=True)
        panel_mode_action.setChecked(True)
        panel_mode_action.triggered.connect(lambda: self.set_canvas_mode("panel"))

        text_mode_action = QAction("Text Mode", self, checkable=True)
        text_mode_action.triggered.connect(lambda: self.set_canvas_mode("text"))

        self.toolbar.addAction(panel_mode_action)
        self.toolbar.addAction(text_mode_action)
        self.toolbar.addSeparator()

        remove_bg_action = QAction("Remove Background", self)
        remove_bg_action.triggered.connect(self.remove_background)
        self.toolbar.addAction(remove_bg_action)

        self.mode_actions = [panel_mode_action, text_mode_action]

    def set_canvas_mode(self, mode):
        self.canvas.canvas_mode = mode
        sender = self.sender()
        for action in self.mode_actions:
            if action != sender:
                action.setChecked(False)
        sender.setChecked(True)

    def remove_background(self):
        if self.canvas.selected_item_index != -1:
            item = self.canvas.items[self.canvas.selected_item_index]
            if item['type'] == 'panel' and item['image']:
                pixmap = item['image']
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.ReadWrite)
                pixmap.save(buffer, "PNG")

                input_bytes = buffer.data().data()
                output_bytes = remove(input_bytes)

                new_pixmap = QPixmap()
                new_pixmap.loadFromData(output_bytes)
                item['image'] = new_pixmap
                self.canvas.update()

    def _create_menu_bar(self):
        file_menu = self.menu_bar.addMenu("&File")

        actions = {
            "New": self.new_project,
            "Open...": self.open_project,
            "Save As...": self.save_project,
            "Export As...": self.export_comic,
            "Exit": self.close
        }

        file_menu.addAction(QAction("New", self, triggered=actions["New"]))
        file_menu.addAction(QAction("Open...", self, triggered=actions["Open..."]))
        file_menu.addAction(QAction("Save As...", self, triggered=actions["Save As..."]))
        file_menu.addSeparator()
        file_menu.addAction(QAction("Export As...", self, triggered=actions["Export As..."]))
        file_menu.addSeparator()
        file_menu.addAction(QAction("Exit", self, triggered=actions["Exit"]))

    def new_project(self):
        self.canvas.clear_canvas()
        self.character_manager.clear_characters()

    def save_project(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Comic Project", "", "Comic Project Files (*.comicproj)")
        if not file_path:
            return

        project_data = {'characters': {}, 'items': []}

        for name, color in self.character_manager.characters.items():
            project_data['characters'][name] = color.name()

        for item in self.canvas.items:
            item_rect = item['rect']
            item_data = {
                'type': item['type'],
                'rect': (item_rect.x(), item_rect.y(), item_rect.width(), item_rect.height())
            }

            if item['type'] == 'panel' and item.get('image'):
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                item['image'].save(buffer, "PNG")
                image_bytes = buffer.data().data()
                item_data['image_base64'] = base64.b64encode(image_bytes).decode('utf-8')

            elif item['type'] == 'text':
                item_data['text'] = item['text']
                color = item['color']
                item_data['color'] = (color.red(), color.green(), color.blue(), color.alpha())

            project_data['items'].append(item_data)

        with open(file_path, 'w') as f:
            json.dump(project_data, f, indent=4)

    def open_project(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Comic Project", "", "Comic Project Files (*.comicproj)")
        if not file_path:
            return

        with open(file_path, 'r') as f:
            project_data = json.load(f)

        self.character_manager.load_characters(project_data.get('characters', {}))
        self.canvas.load_items(project_data.get('items', []))

    def export_comic(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Comic", "", "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg)")
        if not file_path:
            return

        pixmap = QPixmap(self.canvas.size())
        pixmap.fill(Qt.GlobalColor.white)
        self.canvas.render(pixmap)

        if not pixmap.save(file_path):
            QMessageBox.warning(self, "Export Error", "Failed to save the comic.")
        else:
            QMessageBox.information(self, "Export Successful", f"Comic successfully exported to:\n{file_path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())
