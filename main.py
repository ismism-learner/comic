import sys
import json
import base64
import io
import os
from rembg import remove

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QToolBar, QMenuBar,
    QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QListWidget, QListWidgetItem,
    QColorDialog, QDockWidget, QInputDialog, QMessageBox, QFileDialog,
    QAbstractItemView, QLabel, QFrame
)
from PyQt6.QtGui import (
    QAction, QPainter, QPen, QBrush, QCursor,
    QPixmap, QColor, QFontMetrics, QIcon, QDrag, QPainterPath
)
from PyQt6.QtCore import (
    Qt, QPoint, QRect, QUrl, QBuffer,
    QByteArray, QIODevice, QThread, pyqtSignal, QMimeData, QRectF
)

# ... All other classes are unchanged ...
class CharacterManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.characters = {}; self.current_character = None; self.selected_color = QColor(Qt.GlobalColor.black); self._setup_ui()
    def _setup_ui(self):
        self.layout = QVBoxLayout(self); self.char_list = QListWidget(); self.char_list.itemClicked.connect(self.select_character); self.name_input = QLineEdit(); self.name_input.setPlaceholderText("Character Name"); self.color_button = QPushButton("Choose Color"); self.color_button.clicked.connect(self.choose_color); self.add_button = QPushButton("Add Character"); self.add_button.clicked.connect(self.add_character); self.layout.addWidget(self.char_list); self.layout.addWidget(self.name_input); self.layout.addWidget(self.color_button); self.layout.addWidget(self.add_button)
    def choose_color(self):
        color = QColorDialog.getColor();
        if color.isValid(): self.selected_color = color; self.color_button.setStyleSheet(f"background-color: {color.name()}")
    def add_character(self):
        name = self.name_input.text()
        if name and name not in self.characters: self.characters[name] = self.selected_color; list_item = QListWidgetItem(name); list_item.setForeground(QBrush(self.selected_color)); self.char_list.addItem(list_item); self.name_input.clear()
    def select_character(self, item): self.current_character = item.text()
    def get_current_character_color(self):
        if self.current_character: return self.characters.get(self.current_character, QColor(Qt.GlobalColor.black))
        return QColor(Qt.GlobalColor.black)
    def clear_characters(self): self.characters = {}; self.char_list.clear(); self.current_character = None
    def load_characters(self, characters_data):
        self.clear_characters()
        for name, color_hex in characters_data.items(): color = QColor(color_hex); self.characters[name] = color; item = QListWidgetItem(name); item.setForeground(QBrush(color)); self.char_list.addItem(item)
class RembgThread(QThread):
    finished = pyqtSignal(bytes)
    def __init__(self, input_bytes): super().__init__(); self.input_bytes = input_bytes
    def run(self): self.finished.emit(remove(self.input_bytes))
class BackgroundRemover(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.processed_pixmap = None; self.rembg_thread = None; self.drag_start_position = None; self.layout = QVBoxLayout(self); self.drop_area = QLabel("Drag image here to remove background"); self.drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter); self.drop_area.setFrameShape(QFrame.Shape.StyledPanel); self.drop_area.setMinimumHeight(150); self.drop_area.setAcceptDrops(True); self.layout.addWidget(self.drop_area); self.drop_area.dragEnterEvent = self.dragEnterEvent; self.drop_area.dropEvent = self.dropEvent; self.drop_area.mousePressEvent = self.mousePressEvent; self.drop_area.mouseMoveEvent = self.mouseMoveEvent
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            try:
                with open(event.mimeData().urls()[0].toLocalFile(), 'rb') as f: self.drop_area.setText("Processing..."); self.rembg_thread = RembgThread(f.read()); self.rembg_thread.finished.connect(self.on_rembg_finished); self.rembg_thread.start()
            except Exception as e: self.drop_area.setText("Error loading file."); print(f"Error: {e}")
    def on_rembg_finished(self, output_bytes):
        self.processed_pixmap = QPixmap(); self.processed_pixmap.loadFromData(output_bytes); preview = self.processed_pixmap.scaled(self.drop_area.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation); self.drop_area.setPixmap(preview); self.drop_area.setText("")
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.processed_pixmap: self.drag_start_position = event.pos()
    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton): return
        if not self.processed_pixmap: return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance(): return
        drag = QDrag(self); mime_data = QMimeData(); byte_array = QByteArray(); buffer = QBuffer(byte_array); buffer.open(QIODevice.OpenModeFlag.WriteOnly); self.processed_pixmap.save(buffer, "PNG"); mime_data.setData("application/x-comic-creator-image", byte_array); drag.setMimeData(mime_data); drag.setPixmap(self.processed_pixmap.scaledToWidth(64)); drag.exec(Qt.DropAction.CopyAction)
class PageManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = None  # To be set later by MainWindow
        self.layout = QVBoxLayout(self)
        self.page_list = QListWidget()

        button_layout = QHBoxLayout()
        self.add_page_button = QPushButton("New Page")
        self.delete_page_button = QPushButton("Delete Page")
        button_layout.addWidget(self.add_page_button)
        button_layout.addWidget(self.delete_page_button)

        self.layout.addWidget(self.page_list)
        self.layout.addLayout(button_layout)

    def set_canvas(self, canvas):
        """Establish connections after canvas is created."""
        self.canvas = canvas
        self.page_list.currentRowChanged.connect(self.canvas.set_current_page)
        self.add_page_button.clicked.connect(self.canvas.add_page)
        self.delete_page_button.clicked.connect(self.canvas.delete_current_page)

    def update_page_list(self):
        if not self.canvas: return
        self.page_list.blockSignals(True)
        self.page_list.clear()
        for i in range(len(self.canvas.pages)):
            self.page_list.addItem(f"Page {i + 1}")
        self.page_list.setCurrentRow(self.canvas.current_page_index)
        self.page_list.blockSignals(False)
class LayerManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = None # To be set later
        self.layout = QVBoxLayout(self)
        self.layer_list = QListWidget()
        self.layer_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.layer_list.model().rowsMoved.connect(self.on_layer_moved)
        self.layout.addWidget(self.layer_list)

    def set_canvas(self, canvas):
        self.canvas = canvas

    def on_layer_moved(self):
        if not self.canvas: return
        new_items_order = [self.layer_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.layer_list.count() - 1, -1, -1)]
        for item in self.canvas.get_current_page_items():
            if item['type'] == 'panel': new_items_order.append(item)
        self.canvas.get_current_page()['items'] = new_items_order
        self.canvas.update()
    def update_layers(self, page_items):
        self.layer_list.clear()
        content_items = [item for item in page_items if item['type'] in ('image', 'text')]
        for item_obj in reversed(content_items):
            if item_obj['type'] == 'image': list_item = QListWidgetItem("Image Layer"); list_item.setIcon(QIcon(item_obj['pixmap'].scaledToWidth(64)))
            elif item_obj['type'] == 'text': list_item = QListWidgetItem(f"Text: '{item_obj['text'][:10]}...'")
            list_item.setData(Qt.ItemDataRole.UserRole, item_obj); self.layer_list.addItem(list_item)

class Canvas(QWidget):
    # ... Canvas is mostly unchanged, save/load is handled by MainWindow ...
    MIME_TYPE = "application/x-comic-creator-image"
    def __init__(self, parent=None, character_manager=None, layer_manager=None, page_manager=None):
        super().__init__(parent); self.character_manager = character_manager; self.layer_manager = layer_manager; self.page_manager = page_manager; self.setMouseTracking(True); self.setAcceptDrops(True); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus); self.pages = [{'items': []}]; self.current_page_index = 0; self.current_rect_for_drawing = None; self.start_point = None; self.selected_item_index = -1; self.interaction_mode = "none"; self.resize_handle = None; self.move_offset = QPoint()
    def get_current_page(self): return self.pages[self.current_page_index]
    def get_current_page_items(self): return self.get_current_page()['items']
    def add_page(self): self.pages.append({'items': []}); self.set_current_page(len(self.pages) - 1)
    def delete_current_page(self):
        if len(self.pages) > 1: self.pages.pop(self.current_page_index); self.set_current_page(max(0, self.current_page_index - 1))
    def set_current_page(self, index): self.current_page_index = index; self.selected_item_index = -1; self._update_layer_view(); self.page_manager.update_page_list(); self.update()
    def _update_layer_view(self): self.layer_manager.update_layers(self.get_current_page_items())
    def find_item(self, point):
        for i in range(len(self.get_current_page_items()) - 1, -1, -1):
            if self.get_current_page_items()[i]['rect'].contains(point): return i
        return -1
    def dropEvent(self, event):
        pixmap = None
        if event.mimeData().hasFormat(self.MIME_TYPE): pixmap = QPixmap(); pixmap.loadFromData(event.mimeData().data(self.MIME_TYPE))
        elif event.mimeData().hasUrls(): pixmap = QPixmap(event.mimeData().urls()[0].toLocalFile())
        if pixmap and not pixmap.isNull(): new_rect = QRect(event.position().toPoint(), pixmap.size()); new_image_item = {'type': 'image', 'rect': new_rect, 'pixmap': pixmap}; self.get_current_page_items().append(new_image_item); self.selected_item_index = len(self.get_current_page_items()) - 1; self.update(); self._update_layer_view()
    def add_text_item(self, pos):
        text, ok = QInputDialog.getText(self, 'Add Text', 'Enter your text:')
        if ok and text: new_text_item = {'type': 'text', 'rect': QFontMetrics(self.font()).boundingRect(text).translated(pos), 'text': text, 'color': self.character_manager.get_current_character_color()}; self.get_current_page_items().append(new_text_item); self.selected_item_index = len(self.get_current_page_items()) - 1; self.update(); self._update_layer_view()
    def delete_selected_item(self):
        if self.selected_item_index != -1: del self.get_current_page_items()[self.selected_item_index]; self.selected_item_index = -1; self.update(); self._update_layer_view()
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        items = self.get_current_page_items()
        content_items = [item for item in items if item['type'] in ('image', 'text')]
        mask_items = [item for item in items if item['type'] == 'panel']

        # 1. Draw a white background for the entire page
        painter.fillRect(self.rect(), Qt.GlobalColor.white)

        # 2. Draw all content items
        for item in content_items:
            if item['type'] == 'image':
                self._draw_image(painter, item)
            elif item['type'] == 'text':
                self._draw_text(painter, item)

        # 3. Create the mask path
        # Start with a path covering the whole canvas...
        mask_path = QPainterPath()
        mask_path.addRect(QRectF(self.rect()))
        # ...then subtract the "holes" for each panel.
        for item in mask_items:
            mask_path.addRect(QRectF(item['rect']))

        # Use EvenOddFill to make the inner rectangles (holes) transparent
        mask_path.setFillRule(Qt.FillRule.OddEvenFill)

        # 4. Draw the white mask layer with holes
        painter.fillPath(mask_path, QBrush(Qt.GlobalColor.white))

        # 5. Draw selection handles on top of everything
        if self.selected_item_index != -1:
            self._draw_selection_handles(painter, items[self.selected_item_index])

        if self.current_rect_for_drawing:
            self._draw_drawing_rect(painter)
    def get_handle_at_pos(self, pos):
        if self.selected_item_index != -1:
            h = self.get_resize_handles(self.get_current_page_items()[self.selected_item_index]['rect'])
            for handle, rect in h.items():
                if rect.contains(pos): return handle
        return None
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton: return
        handle = self.get_handle_at_pos(event.pos()); item_index = self.find_item(event.pos())
        if handle: self.interaction_mode = "resize"; self.resize_handle = handle
        elif item_index != -1: self.interaction_mode = "move"; self.selected_item_index = item_index; self.move_offset = event.pos() - self.get_current_page_items()[item_index]['rect'].topLeft()
        else: self.interaction_mode = "draw"; self.selected_item_index = -1; self.start_point = event.pos(); self.current_rect_for_drawing = QRect(self.start_point, event.pos())
        self.update()
    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton: return
        if self.interaction_mode == "draw" and self.current_rect_for_drawing: self.get_current_page_items().append({'type': 'panel', 'rect': self.current_rect_for_drawing}); self.selected_item_index = len(self.get_current_page_items()) - 1
        if self.interaction_mode == "draw" and self.start_point == event.pos() and self.find_item(event.pos()) == -1: self.selected_item_index = -1
        self.interaction_mode = "none"; self.current_rect_for_drawing = None; self.start_point = None
        self.update(); self._update_layer_view()
    def clear_canvas(self): self.pages = [{'items': []}]; self.set_current_page(0)
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace: self.delete_selected_item()
        else: super().keyPressEvent(event)
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasFormat(self.MIME_TYPE): event.acceptProposedAction()
    def mouseMoveEvent(self, event):
        if self.interaction_mode == "resize": self._handle_resize(event)
        elif self.interaction_mode == "move": self._handle_move(event)
        elif self.interaction_mode == "draw": self._handle_draw(event)
        else: self._update_cursor(event)
        self.update()
    def _handle_resize(self, event):
        item_rect = self.get_current_page_items()[self.selected_item_index]['rect']
        if self.resize_handle == "topLeft": item_rect.setTopLeft(event.pos())
        elif self.resize_handle == "topRight": item_rect.setTopRight(event.pos())
        elif self.resize_handle == "bottomLeft": item_rect.setBottomLeft(event.pos())
        elif self.resize_handle == "bottomRight": item_rect.setBottomRight(event.pos())
        self.get_current_page_items()[self.selected_item_index]['rect'] = item_rect.normalized()
    def _handle_move(self, event): self.get_current_page_items()[self.selected_item_index]['rect'].moveTopLeft(event.pos() - self.move_offset)
    def _handle_draw(self, event): self.current_rect_for_drawing = QRect(self.start_point, event.pos()).normalized()
    def _update_cursor(self, event):
        handle = self.get_handle_at_pos(event.pos())
        if handle: self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor if handle in ["topLeft", "bottomRight"] else Qt.CursorShape.SizeBDiagCursor))
        elif self.find_item(event.pos()) != -1: self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        else: self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
    def _draw_image(self, painter, item):
        """Draws an image item."""
        painter.drawPixmap(item['rect'], item['pixmap'])

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

    def get_resize_handles(self, rect):
        h = {}
        h["topLeft"] = QRect(rect.topLeft().x() - 4, rect.topLeft().y() - 4, 8, 8)
        h["topRight"] = QRect(rect.topRight().x() - 4, rect.topRight().y() - 4, 8, 8)
        h["bottomLeft"] = QRect(rect.bottomLeft().x() - 4, rect.bottomLeft().y() - 4, 8, 8)
        h["bottomRight"] = QRect(rect.bottomRight().x() - 4, rect.bottomRight().y() - 4, 8, 8)
        return h

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Comic Creator v2.2")
        self.setGeometry(100, 100, 1400, 900)

        # Create all manager widgets first
        self.character_manager = CharacterManager(self)
        self.layer_manager = LayerManager(self)
        self.bg_remover = BackgroundRemover(self)
        self.page_manager = PageManager(self)

        # Create the central canvas widget
        self.canvas = Canvas(self, self.character_manager, self.layer_manager, self.page_manager)
        self.setCentralWidget(self.canvas)

        # Now that all widgets exist, set the cross-references
        self.layer_manager.set_canvas(self.canvas)
        self.page_manager.set_canvas(self.canvas)

        # Setup UI
        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(self.toolbar)
        self._create_toolbar()

        self.menu_bar = self.menuBar()
        self._create_menu_bar()
        self._create_docks()

        # Initial UI updates
        self.page_manager.update_page_list()
    def _create_docks(self):
        self.page_dock = QDockWidget("Pages", self); self.page_dock.setWidget(self.page_manager); self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.page_dock)
        self.bg_remover_dock = QDockWidget("Background Remover", self); self.bg_remover_dock.setWidget(self.bg_remover); self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.bg_remover_dock)
        self.character_dock = QDockWidget("Characters", self); self.character_dock.setWidget(self.character_manager); self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.character_dock)
        self.layer_dock = QDockWidget("Layers", self); self.layer_dock.setWidget(self.layer_manager); self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.layer_dock)
    def _create_toolbar(self):
        add_panel_action = QAction("Add Panel (Hole)", self); self.toolbar.addAction(add_panel_action)
        add_text_action = QAction("Add Text", self); add_text_action.triggered.connect(lambda: self.canvas.add_text_item(self.canvas.rect().center())); self.toolbar.addAction(add_text_action)
        self.toolbar.addSeparator(); delete_action = QAction("Delete", self); delete_action.triggered.connect(self.canvas.delete_selected_item); self.toolbar.addAction(delete_action)
    def _create_menu_bar(self):
        file_menu = self.menu_bar.addMenu("&File"); actions = {"New": self.new_project, "Open...": self.open_project, "Save As...": self.save_project, "Export As...": self.export_comic, "Exit": self.close}; file_menu.addAction(QAction("New", self, triggered=actions["New"])); file_menu.addAction(QAction("Open...", self, triggered=actions["Open..."])); file_menu.addAction(QAction("Save As...", self, triggered=actions["Save As..."])); file_menu.addSeparator(); file_menu.addAction(QAction("Export As...", self, triggered=actions["Export As..."])); file_menu.addSeparator(); file_menu.addAction(QAction("Exit", self, triggered=actions["Exit"]))
    def new_project(self): self.canvas.clear_canvas(); self.character_manager.clear_characters()

    def project_data_to_dict(self):
        project_data = {'characters': {}, 'pages': []}
        for name, color in self.character_manager.characters.items(): project_data['characters'][name] = color.name()
        for page in self.canvas.pages:
            page_data = {'items': []}
            for item in page['items']:
                item_rect = item['rect']; item_data = {'type': item['type'], 'rect': (item_rect.x(), item_rect.y(), item_rect.width(), item_rect.height())}
                if item['type'] == 'image':
                    buffer = QBuffer(); buffer.open(QIODevice.OpenModeFlag.WriteOnly); item['pixmap'].save(buffer, "PNG"); image_bytes = buffer.data().data(); item_data['pixmap_base64'] = base64.b64encode(image_bytes).decode('utf-8')
                elif item['type'] == 'text': item_data['text'] = item['text']; color = item['color']; item_data['color'] = (color.red(), color.green(), color.blue(), color.alpha())
                page_data['items'].append(item_data)
            project_data['pages'].append(page_data)
        return project_data

    def load_project_from_data(self, project_data):
        self.character_manager.load_characters(project_data.get('characters', {}))
        self.canvas.pages = []
        for page_data in project_data.get('pages', [{'items': []}]):
            new_page = {'items': []}
            for item_data in page_data['items']:
                rect = QRect(*item_data['rect']); item = {'type': item_data['type'], 'rect': rect}
                if item_data['type'] == 'image': item['pixmap'] = QPixmap(); item['pixmap'].loadFromData(QByteArray(base64.b64decode(item_data['pixmap_base64'])), "PNG")
                elif item_data['type'] == 'text': item['text'] = item_data['text']; item['color'] = QColor(*item_data['color'])
                new_page['items'].append(item)
            self.canvas.pages.append(new_page)
        self.canvas.set_current_page(0)

    def save_project(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Comic Project", "", "Comic Project Files (*.comicproj)")
        if not file_path: return
        try:
            with open(file_path, 'w') as f: json.dump(self.project_data_to_dict(), f, indent=4)
        except Exception as e: QMessageBox.critical(self, "Error", f"Failed to save project: {e}")

    def open_project(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Comic Project", "", "Comic Project Files (*.comicproj)")
        if not file_path: return
        try:
            with open(file_path, 'r') as f: self.load_project_from_data(json.load(f))
        except Exception as e: QMessageBox.critical(self, "Error", f"Failed to open project: {e}")

    def export_comic(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Comic", "", "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg)")
        if not file_path: return

        reply = QMessageBox.question(self, 'Export Options', 'Export all pages?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Cancel: return

        original_page = self.canvas.current_page_index
        if reply == QMessageBox.StandardButton.Yes:
            base_path, ext = os.path.splitext(file_path)
            for i in range(len(self.canvas.pages)):
                self.canvas.set_current_page(i)
                QApplication.processEvents() # Allow UI to update
                pixmap = QPixmap(self.canvas.size()); self.canvas.render(pixmap)
                page_file_path = f"{base_path}_page_{i+1}{ext}"
                if not pixmap.save(page_file_path): QMessageBox.warning(self, "Export Error", f"Failed to save page {i+1}."); break
            else: QMessageBox.information(self, "Export Successful", f"All pages exported successfully.")
        else: # Export current page only
            pixmap = QPixmap(self.canvas.size()); self.canvas.render(pixmap)
            if not pixmap.save(file_path): QMessageBox.warning(self, "Export Error", "Failed to save the comic.")
            else: QMessageBox.information(self, "Export Successful", f"Current page exported to:\n{file_path}")
        self.canvas.set_current_page(original_page)

if __name__ == "__main__":
    app = QApplication(sys.argv); main_win = MainWindow(); main_win.show(); sys.exit(app.exec())
