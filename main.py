import sys
import json
import base64
import io
import os
import uuid # For unique item IDs
from rembg import remove
import pyclipper

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QToolBar, QMenuBar,
    QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QListWidget, QListWidgetItem,
    QColorDialog, QDockWidget, QInputDialog, QMessageBox, QFileDialog,
    QAbstractItemView, QLabel, QFrame, QFontComboBox, QSpinBox, QCheckBox, QSlider, QGroupBox,
    QGraphicsBlurEffect, QGraphicsScene, QGraphicsTextItem
)
from PyQt6.QtGui import (
    QAction, QPainter, QPen, QBrush, QCursor,
    QPixmap, QColor, QFontMetrics, QIcon, QDrag, QPainterPath, QFont, QPolygon, QPolygonF
)
from PyQt6.QtCore import (
    Qt, QPoint, QRect, QUrl, QBuffer,
    QByteArray, QIODevice, QThread, pyqtSignal, QMimeData, QRectF, QPointF, QSize
)

class TextToolsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = None
        self.layout = QVBoxLayout(self)

        self.add_text_button = QPushButton("Add New Text")
        self.layout.addWidget(self.add_text_button)

        self.font_combo = QFontComboBox()
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(1, 200)
        self.bold_button = QPushButton("Bold")
        self.bold_button.setCheckable(True)
        self.italic_button = QPushButton("Italic")
        self.italic_button.setCheckable(True)

        style_layout = QHBoxLayout()
        style_layout.addWidget(self.bold_button)
        style_layout.addWidget(self.italic_button)

        self.layout.addWidget(QLabel("Font:"))
        self.layout.addWidget(self.font_combo)
        self.layout.addWidget(QLabel("Size:"))
        self.layout.addWidget(self.font_size_spinbox)
        self.layout.addLayout(style_layout)

        # --- Glow FX UI ---
        glow_group = QGroupBox("Glow FX")
        glow_layout = QVBoxLayout()

        self.glow_enable_checkbox = QCheckBox("Enable Glow")
        glow_layout.addWidget(self.glow_enable_checkbox)

        self.glow_color_button = QPushButton("Glow Color")
        glow_layout.addWidget(self.glow_color_button)

        glow_layout.addWidget(QLabel("Glow Size:"))
        self.glow_size_spinbox = QSpinBox()
        self.glow_size_spinbox.setRange(1, 100)
        glow_layout.addWidget(self.glow_size_spinbox)

        glow_layout.addWidget(QLabel("Glow Opacity:"))
        self.glow_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.glow_opacity_slider.setRange(0, 100)
        glow_layout.addWidget(self.glow_opacity_slider)

        glow_group.setLayout(glow_layout)
        self.layout.addWidget(glow_group)
        # --------------------

        self.layout.addStretch()
        self.disable_controls()

    def set_canvas(self, canvas):
        self.canvas = canvas
        self.add_text_button.clicked.connect(lambda: self.canvas.add_text_item(self.canvas.rect().center()))
        # Font properties
        self.font_combo.currentFontChanged.connect(self.on_font_property_changed)
        self.font_size_spinbox.valueChanged.connect(self.on_font_property_changed)
        self.bold_button.clicked.connect(self.on_font_property_changed)
        self.italic_button.clicked.connect(self.on_font_property_changed)
        # Glow properties
        self.glow_enable_checkbox.clicked.connect(self.on_glow_property_changed)
        self.glow_color_button.clicked.connect(self.on_glow_color_changed)
        self.glow_size_spinbox.valueChanged.connect(self.on_glow_property_changed)
        self.glow_opacity_slider.valueChanged.connect(self.on_glow_property_changed)

    def on_glow_color_changed(self):
        if not self.canvas or not self.canvas.selected_item_id: return
        color = QColorDialog.getColor()
        if color.isValid():
            self.glow_color_button.setStyleSheet(f"background-color: {color.name()}")
            self.on_glow_property_changed()

    def on_font_property_changed(self):
        if not self.canvas or not self.canvas.selected_item_id:
            return
        selected_item = self.canvas.get_item_by_id(self.canvas.selected_item_id)
        if not selected_item or selected_item['type'] != 'text':
            return

        font = QFont(self.font_combo.currentFont())
        font.setPointSize(self.font_size_spinbox.value())
        font.setBold(self.bold_button.isChecked())
        font.setItalic(self.italic_button.isChecked())

        self.canvas.update_selected_text_item_font(font)

    def on_glow_property_changed(self):
        if not self.canvas or not self.canvas.selected_item_id:
            return
        selected_item = self.canvas.get_item_by_id(self.canvas.selected_item_id)
        if not selected_item or selected_item['type'] != 'text':
            return

        glow_fx_data = {
            'enabled': self.glow_enable_checkbox.isChecked(),
            'color': self.get_color_from_button(self.glow_color_button),
            'size': self.glow_size_spinbox.value(),
            'opacity': self.glow_opacity_slider.value() / 100.0
        }
        self.canvas.update_selected_text_item_glow(glow_fx_data)

    def get_color_from_button(self, button):
        # A bit of a hack to get the QColor from the stylesheet
        style = button.styleSheet()
        if "background-color" in style:
            color_name = style.split(":")[-1].strip()
            return QColor(color_name)
        return QColor(255, 255, 0) # Default if not set

    def update_controls(self, item):
        if item and item['type'] == 'text':
            self.enable_controls()
            font = item.get('font', QFont()) # Use default QFont if not set

            # Block signals to prevent feedback loops
            self.font_combo.blockSignals(True)
            self.font_size_spinbox.blockSignals(True)
            self.bold_button.blockSignals(True)
            self.italic_button.blockSignals(True)
            self.glow_enable_checkbox.blockSignals(True)
            self.glow_color_button.blockSignals(True)
            self.glow_size_spinbox.blockSignals(True)
            self.glow_opacity_slider.blockSignals(True)

            self.font_combo.setCurrentFont(font)
            self.font_size_spinbox.setValue(font.pointSize() if font.pointSize() > 0 else 12)
            self.bold_button.setChecked(font.bold())
            self.italic_button.setChecked(font.italic())

            glow_fx = item.get('glow_fx', {})
            self.glow_enable_checkbox.setChecked(glow_fx.get('enabled', False))
            glow_color = glow_fx.get('color', QColor(255,255,0))
            self.glow_color_button.setStyleSheet(f"background-color: {glow_color.name()}")
            self.glow_size_spinbox.setValue(glow_fx.get('size', 10))
            self.glow_opacity_slider.setValue(int(glow_fx.get('opacity', 1.0) * 100))

            self.font_combo.blockSignals(False)
            self.font_size_spinbox.blockSignals(False)
            self.bold_button.blockSignals(False)
            self.italic_button.blockSignals(False)
            self.glow_enable_checkbox.blockSignals(False)
            self.glow_color_button.blockSignals(False)
            self.glow_size_spinbox.blockSignals(False)
            self.glow_opacity_slider.blockSignals(False)
        else:
            self.disable_controls()

    def enable_controls(self):
        controls = [
            self.font_combo, self.font_size_spinbox, self.bold_button, self.italic_button,
            self.glow_enable_checkbox, self.glow_color_button, self.glow_size_spinbox, self.glow_opacity_slider
        ]
        for w in controls:
            w.setEnabled(True)

    def disable_controls(self):
        controls = [
            self.font_combo, self.font_size_spinbox, self.bold_button, self.italic_button,
            self.glow_enable_checkbox, self.glow_color_button, self.glow_size_spinbox, self.glow_opacity_slider
        ]
        for w in controls:
            w.setEnabled(False)

class CharacterManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = None
        self.characters = {}
        self.current_character = None
        self.selected_color = QColor(Qt.GlobalColor.black)
        self._setup_ui()

    def set_canvas(self, canvas):
        self.canvas = canvas
        self.dialogue_edit.textChanged.connect(self.on_dialogue_changed)

    def on_dialogue_changed(self, text):
        if self.canvas:
            self.canvas.update_selected_text_item_content(text)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.char_list = QListWidget()
        self.char_list.itemClicked.connect(self.select_character)
        self.layout.addWidget(self.char_list)

        # Dialogue editing section
        self.dialogue_label = QLabel("Dialogue:")
        self.dialogue_edit = QLineEdit()
        self.layout.addWidget(self.dialogue_label)
        self.layout.addWidget(self.dialogue_edit)
        self.dialogue_label.hide()
        self.dialogue_edit.hide()

        # Character creation section
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Character Name")
        self.color_button = QPushButton("Choose Color")
        self.color_button.clicked.connect(self.choose_color)
        self.add_button = QPushButton("Add Character")
        self.add_button.clicked.connect(self.add_character)

        self.layout.addWidget(self.name_input)
        self.layout.addWidget(self.color_button)
        self.layout.addWidget(self.add_button)
        self.layout.addStretch()

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

    def update_dialogue_editor(self, selected_item):
        # Block signals to prevent feedback loops when setting text
        self.dialogue_edit.blockSignals(True)
        if selected_item and selected_item['type'] == 'text':
            self.dialogue_label.show()
            self.dialogue_edit.show()
            self.dialogue_edit.setText(selected_item['text'])
        else:
            self.dialogue_label.hide()
            self.dialogue_edit.hide()
            self.dialogue_edit.clear()
        self.dialogue_edit.blockSignals(False)

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
        super().__init__(parent); self.canvas = None; self.layout = QVBoxLayout(self); self.page_list = QListWidget(); button_layout = QHBoxLayout(); self.add_page_button = QPushButton("New Page"); self.delete_page_button = QPushButton("Delete Page"); button_layout.addWidget(self.add_page_button); button_layout.addWidget(self.delete_page_button); self.layout.addWidget(self.page_list); self.layout.addLayout(button_layout)
    def set_canvas(self, canvas): self.canvas = canvas; self.page_list.currentRowChanged.connect(self.canvas.set_current_page); self.add_page_button.clicked.connect(self.canvas.add_page); self.delete_page_button.clicked.connect(self.canvas.delete_current_page)
    def update_page_list(self):
        if not self.canvas: return
        self.page_list.blockSignals(True); self.page_list.clear()
        for i in range(len(self.canvas.pages)): self.page_list.addItem(f"Page {i + 1}")
        self.page_list.setCurrentRow(self.canvas.current_page_index); self.page_list.blockSignals(False)
class LayerListWidget(QListWidget):
    def __init__(self, layer_manager, parent=None):
        super().__init__(parent)
        self.layer_manager = layer_manager
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def dropEvent(self, event):
        target_item = self.itemAt(event.position().toPoint())
        selected_items = self.selectedItems()
        if not selected_items:
            event.ignore(); return

        dragged_item_data = selected_items[0].data(Qt.ItemDataRole.UserRole)
        if not dragged_item_data:
            event.ignore(); return

        new_parent_id = None
        if target_item:
            target_item_data = target_item.data(Qt.ItemDataRole.UserRole)
            if target_item_data: new_parent_id = target_item_data['id']

        if self.layer_manager.canvas.reparent_item(dragged_item_data['id'], new_parent_id):
            event.accept()
        else:
            self.layer_manager.canvas._update_layer_view()
            event.ignore()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            if self.layer_manager.canvas: self.layer_manager.canvas.delete_selected_item()
        else:
            super().keyPressEvent(event)

class LayerManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = None
        self.layout = QVBoxLayout(self)
        self.layer_list = LayerListWidget(self, self)
        self.layer_list.itemClicked.connect(self.on_item_clicked)
        self.layout.addWidget(self.layer_list)

    def set_canvas(self, canvas):
        self.canvas = canvas

    def get_z_ordered_ids(self):
        return [self.layer_list.item(i).data(Qt.ItemDataRole.UserRole)['id'] for i in range(self.layer_list.count()) if self.layer_list.item(i)]

    def on_item_clicked(self, list_item):
        if self.canvas and list_item:
            item_data = list_item.data(Qt.ItemDataRole.UserRole)
            if item_data: self.canvas.set_selected_item_id(item_data['id'])

    def update_layers(self, items_dict, selected_item_id=None):
        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        item_tree = {}
        top_level_items = []

        for item_id, item in items_dict.items():
            item_tree[item_id] = {'item': item, 'children': []}
        for item_id, node in item_tree.items():
            parent_id = node['item'].get('parent')
            if parent_id in item_tree:
                item_tree[parent_id]['children'].append(node)
            else:
                top_level_items.append(node)

        def populate_widget(nodes, indent=0):
            for node in reversed(nodes):
                item_data = node['item']
                prefix = "    " * indent
                if item_data['type'] == 'panel':
                    list_item = QListWidgetItem(f"{prefix}🖼️ Panel/Container")
                elif item_data['type'] == 'image':
                    list_item = QListWidgetItem(f"{prefix}📷 Image Layer")
                elif item_data['type'] == 'text':
                    list_item = QListWidgetItem(f"{prefix}✍️ Text: '{item_data['text'][:10]}...'")
                list_item.setData(Qt.ItemDataRole.UserRole, item_data)
                self.layer_list.addItem(list_item)
                populate_widget(node['children'], indent + 1)
        populate_widget(top_level_items)

        # After populating, find and select the item
        for i in range(self.layer_list.count()):
            list_item = self.layer_list.item(i)
            item_data = list_item.data(Qt.ItemDataRole.UserRole)
            if item_data and item_data['id'] == selected_item_id:
                self.layer_list.setCurrentItem(list_item)
                break
        self.layer_list.blockSignals(False)

class Canvas(QWidget):
    selectionChanged = pyqtSignal(object) # Signal to emit when selection changes
    MIME_TYPE = "application/x-comic-creator-image"
    def __init__(self, parent=None, character_manager=None, layer_manager=None, page_manager=None, text_tools=None):
        super().__init__(parent)
        self.character_manager = character_manager
        self.layer_manager = layer_manager
        self.page_manager = page_manager
        self.text_tools = text_tools
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.pages = [{'items': {}}]
        self.current_page_index = 0
        self.current_rect_for_drawing = None
        self.start_point = None
        self.selected_item_id = None
        self.interaction_mode = "none"
        self.resize_handle = None
        self.move_offset = QPoint()
        self.edit_mode_parent_id = None
        self.double_click_flag = False
        self.text_editor = None # Add a member for the floating text editor
        self.split_line_points = [] # For the new split mode

        # For V5.0 Frame Vector Editing
        self.hovered_vertex_index = -1
        self.hovered_edge_index = -1
        self.dragged_vertex_index = -1
        self.dragged_edge_index = -1

    def get_vertex_at_pos(self, pos, item):
        if not item or 'polygon_points' not in item:
            return -1
        threshold = 8 # pixels
        for i, p in enumerate(item['polygon_points']):
            if (p - pos).manhattanLength() < threshold:
                return i
        return -1

    def get_edge_at_pos(self, pos, item):
        if not item or 'polygon_points' not in item:
            return -1

        points = item['polygon_points']
        threshold = 8 # pixels
        for i in range(len(points)):
            p1 = points[i]
            p2 = points[(i + 1) % len(points)]

            rect = QRect(p1, p2).normalized()
            if not rect.adjusted(-threshold, -threshold, threshold, threshold).contains(pos):
                continue

            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            if dx == 0 and dy == 0: continue

            t = ((pos.x() - p1.x()) * dx + (pos.y() - p1.y()) * dy) / (dx*dx + dy*dy)

            if 0 <= t <= 1:
                closest_point = QPointF(p1) + t * QPointF(dx, dy)
            elif t < 0:
                closest_point = QPointF(p1)
            else: # t > 1
                closest_point = QPointF(p2)

            dist = (QPointF(pos) - closest_point).manhattanLength()
            if dist < threshold:
                return i
        return -1

    def split_polygon(self, item_id, p1, p2):
        item_to_split = self.get_item_by_id(item_id)
        if not item_to_split or 'polygon_points' not in item_to_split:
            return

        subject_poly = [(p.x(), p.y()) for p in item_to_split['polygon_points']]
        line_vec = p2 - p1
        if line_vec.manhattanLength() == 0: return

        normal = QPoint(line_vec.y(), -line_vec.x())
        huge_dist = 2 * max(self.width(), self.height())

        clip_p1 = p1 + normal * huge_dist
        clip_p2 = p2 + normal * huge_dist
        clip_p3 = p2
        clip_p4 = p1
        clipper_poly1 = [(p.x(), p.y()) for p in [clip_p1, clip_p2, clip_p3, clip_p4]]

        pc_intersect = pyclipper.Pyclipper()
        pc_intersect.AddPath(subject_poly, pyclipper.PT_SUBJECT, True)
        pc_intersect.AddPath(clipper_poly1, pyclipper.PT_CLIP, True)
        solution_intersect = pc_intersect.Execute(pyclipper.CT_INTERSECTION, pyclipper.PFT_EVENODD, pyclipper.PFT_EVENODD)

        pc_diff = pyclipper.Pyclipper()
        pc_diff.AddPath(subject_poly, pyclipper.PT_SUBJECT, True)
        pc_diff.AddPath(clipper_poly1, pyclipper.PT_CLIP, True)
        solution_diff = pc_diff.Execute(pyclipper.CT_DIFFERENCE, pyclipper.PFT_EVENODD, pyclipper.PFT_EVENODD)

        # Before deleting, check if we have valid results
        if not solution_intersect or not solution_diff:
            print("Split resulted in one or zero new shapes. Aborting.")
            return

        # It's safe to delete the original item now
        self.get_current_page_items().pop(item_id, None)

        for poly_solution in [solution_intersect, solution_diff]:
            for path in poly_solution:
                new_poly_pts = [QPoint(int(x), int(y)) for x, y in path]
                if len(new_poly_pts) < 3: continue

                new_rect = QPolygon(new_poly_pts).boundingRect()
                if new_rect.width() < 5 or new_rect.height() < 5: continue # Avoid tiny slivers

                new_item_id, new_item = self._create_item('panel', new_rect)
                new_item['polygon_points'] = new_poly_pts
                self.update_item_bounding_rect(new_item_id)

        self._update_layer_view()
        self.update()

    def update_item_bounding_rect(self, item_id):
        item = self.get_item_by_id(item_id)
        if not item or 'polygon_points' not in item:
            return
        points = item['polygon_points']
        if not points:
            item['rect'] = QRect()
            return
        min_x = min(p.x() for p in points)
        min_y = min(p.y() for p in points)
        max_x = max(p.x() for p in points)
        max_y = max(p.y() for p in points)
        item['rect'] = QRect(min_x, min_y, max_x - min_x, max_y - min_y)

    def enter_split_mode(self):
        self.interaction_mode = "split"
        self.set_selected_item_id(None)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def exit_split_mode(self):
        self.interaction_mode = "none"
        self.split_line_points = []
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def enter_edit_frame_mode(self):
        self.interaction_mode = "edit_frame"
        self.setCursor(Qt.CursorShape.CrossCursor) # A cross cursor is good for precision editing
        self.update()

    def exit_edit_frame_mode(self):
        self.interaction_mode = "none"
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def get_current_page(self): return self.pages[self.current_page_index]
    def get_current_page_items(self): return self.get_current_page()['items']
    def get_item_by_id(self, item_id): return self.get_current_page_items().get(item_id)
    def _create_item(self, item_type, rect, data=None):
        item_id = str(uuid.uuid4())
        item = {'id': item_id, 'type': item_type, 'rect': rect, 'parent': None}
        if item_type == 'panel':
            item['children'] = []
            # Store the panel shape as a list of QPoint objects
            item['polygon_points'] = [rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft()]
        if data:
            item.update(data)
        self.get_current_page_items()[item_id] = item
        return item_id, item
    def add_page(self): self.pages.append({'items': {}}); self.set_current_page(len(self.pages) - 1)
    def delete_current_page(self):
        if len(self.pages) > 1: self.pages.pop(self.current_page_index); self.set_current_page(max(0, self.current_page_index - 1))
    def set_current_page(self, index):
        if 0 <= index < len(self.pages): self.current_page_index = index; self.set_selected_item_id(None); self.edit_mode_parent_id = None; self.page_manager.update_page_list(); self.update()

    def set_selected_item_id(self, item_id):
        if self.selected_item_id == item_id: # Avoid redundant signals
            return
        self.selected_item_id = item_id
        selected_item = self.get_item_by_id(item_id)
        if self.text_tools:
            self.text_tools.update_controls(selected_item)
        self._update_layer_view()
        self.update()
        self.selectionChanged.emit(selected_item) # Emit the signal

    def update_selected_text_item_font(self, font):
        if not self.selected_item_id: return
        item = self.get_item_by_id(self.selected_item_id)
        if not item or item['type'] != 'text': return
        item['font'] = font
        # Recalculate bounding rect based on new font
        metrics = QFontMetrics(font)
        item['rect'] = metrics.boundingRect(item['rect'], Qt.TextFlag.TextWordWrap, item['text'])
        self.update()

    def update_selected_text_item_content(self, text):
        if not self.selected_item_id: return
        item = self.get_item_by_id(self.selected_item_id)
        if not item or item['type'] != 'text': return

        item['text'] = text
        font = item.get('font', QFont())
        metrics = QFontMetrics(font)
        # We need to recalculate the bounding rect as the text content changes
        new_rect = metrics.boundingRect(QRect(item['rect'].topLeft(), QSize(item['rect'].width(), 5000)), Qt.TextFlag.TextWordWrap, text)
        item['rect'] = new_rect
        self._update_layer_view()
        self.update()

    def update_selected_text_item_glow(self, glow_fx_data):
        if not self.selected_item_id: return
        item = self.get_item_by_id(self.selected_item_id)
        if not item or item['type'] != 'text': return

        item['glow_fx'] = glow_fx_data
        self.update()

    def _update_layer_view(self): self.layer_manager.update_layers(self.get_current_page_items(), self.selected_item_id)
    def find_item_for_selection(self, pos):
        if self.edit_mode_parent_id:
            parent = self.get_item_by_id(self.edit_mode_parent_id)
            if parent:
                for child_id in reversed(parent['children']):
                    child = self.get_item_by_id(child_id)
                    if child and child['rect'].contains(pos): return child
            return parent
        return self.find_top_level_item(pos)
    def find_top_level_item(self, pos, item_type=None):
        all_items = self.get_current_page_items()
        # Create a z-ordered list based on the layer manager's list
        z_ordered_ids = self.layer_manager.get_z_ordered_ids()
        for item_id in reversed(z_ordered_ids):
            item = all_items.get(item_id)
            if item and item.get('parent') is None and (item_type is None or item['type'] == item_type) and item['rect'].contains(pos):
                return item
        return None

    def reparent_item(self, item_id, new_parent_id):
        item = self.get_item_by_id(item_id)
        if not item: return False

        # --- Validation ---
        # 1. An item cannot be its own parent.
        if item_id == new_parent_id: return False

        # 2. If the new parent is not a panel, we can't drop onto it.
        #    (But we can drop "between" items, making it top-level, so new_parent_id can be None)
        if new_parent_id:
            new_parent = self.get_item_by_id(new_parent_id)
            if not new_parent or new_parent['type'] != 'panel':
                # If the target is not a panel, make the item top-level instead
                new_parent_id = None

        # 3. Prevent cyclical parenting (e.g., parenting a panel to one of its own children)
        temp_parent_id = new_parent_id
        while temp_parent_id:
            if temp_parent_id == item_id:
                return False # Found a cycle
            temp_parent = self.get_item_by_id(temp_parent_id)
            temp_parent_id = temp_parent.get('parent') if temp_parent else None

        # --- Reparenting Logic ---
        # 1. Remove from old parent's children list
        old_parent_id = item.get('parent')
        if old_parent_id:
            old_parent = self.get_item_by_id(old_parent_id)
            if old_parent and item_id in old_parent['children']:
                old_parent['children'].remove(item_id)

        # 2. Set new parent
        item['parent'] = new_parent_id

        # 3. Add to new parent's children list
        if new_parent_id:
            new_parent = self.get_item_by_id(new_parent_id)
            if new_parent: # Should always exist after our check
                if 'children' not in new_parent: new_parent['children'] = []
                new_parent['children'].append(item_id)

        self._update_layer_view()
        self.update()
        return True
    def dropEvent(self, event):
        pixmap = None
        if event.mimeData().hasFormat(self.MIME_TYPE): pixmap = QPixmap(); pixmap.loadFromData(event.mimeData().data(self.MIME_TYPE))
        elif event.mimeData().hasUrls(): pixmap = QPixmap(event.mimeData().urls()[0].toLocalFile())
        if not (pixmap and not pixmap.isNull()): return

        new_rect = QRect(event.position().toPoint(), pixmap.size())
        item_id, new_image_item = self._create_item('image', new_rect, {'pixmap': pixmap})

        parent_panel = self.find_top_level_item(event.position().toPoint(), item_type='panel')
        if parent_panel: new_image_item['parent'] = parent_panel['id']; parent_panel['children'].append(item_id)
        self.set_selected_item_id(item_id)

    def add_text_item(self, pos):
        text = "New Text"
        font = QFont()
        rect = QFontMetrics(font).boundingRect(text).translated(pos)
        item_data = {
            'text': text,
            'color': self.character_manager.get_current_character_color(),
            'font': font,
            'glow_fx': {
                'enabled': False,
                'color': QColor(255, 255, 0, 255), # Default to yellow
                'size': 10,
                'opacity': 1.0
            }
        }
        item_id, new_text_item = self._create_item('text', rect, item_data)

        if self.edit_mode_parent_id:
            parent = self.get_item_by_id(self.edit_mode_parent_id)
            if parent:
                new_text_item['parent'] = parent['id']
                parent['children'].append(item_id)

        self.set_selected_item_id(item_id)
        self.edit_text_item(new_text_item) # Immediately enter edit mode

    def edit_text_item(self, item):
        if self.text_editor:
            self.text_editor.deleteLater()

        self.text_editor = QLineEdit(self)
        self.text_editor.setGeometry(item['rect'])
        self.text_editor.setText(item['text'])
        self.text_editor.setFont(item.get('font', QFont()))

        self.text_editor.setStyleSheet("background-color: rgba(255, 255, 255, 0.8); border: 1px solid #aaa;")

        self.text_editor.returnPressed.connect(self.finish_text_edit)
        self.text_editor.editingFinished.connect(self.finish_text_edit) # Handles focus loss

        self.text_editor.show()
        self.text_editor.setFocus()

    def finish_text_edit(self):
        if not self.text_editor or not self.selected_item_id:
            return

        item = self.get_item_by_id(self.selected_item_id)
        if not item or item['type'] != 'text':
            self.text_editor.deleteLater()
            self.text_editor = None
            return

        new_text = self.text_editor.text()
        item['text'] = new_text

        # Recalculate bounding rect based on new text and existing font
        font = item.get('font', QFont())
        metrics = QFontMetrics(font)
        # Use a reasonable width for boundingRect calculation if the original rect was tiny
        current_rect = item['rect']
        new_rect = metrics.boundingRect(QRect(current_rect.topLeft(), current_rect.size()), Qt.TextFlag.TextWordWrap, new_text)
        item['rect'] = new_rect

        self.text_editor.deleteLater()
        self.text_editor = None
        self._update_layer_view()
        self.update()

    def delete_selected_item(self):
        if not self.selected_item_id: return
        items_to_delete = {self.selected_item_id}
        item = self.get_item_by_id(self.selected_item_id)
        if item and item['type'] == 'panel':
            for child_id in item['children']: items_to_delete.add(child_id)

        if item and item.get('parent'):
            parent = self.get_item_by_id(item['parent'])
            if parent and self.selected_item_id in parent['children']:
                parent['children'].remove(self.selected_item_id)

        for item_id in items_to_delete:
            self.get_current_page_items().pop(item_id, None)

        self.set_selected_item_id(None)
    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        items_dict = self.get_current_page_items()

        for item in items_dict.values():
            if item.get('parent') is None: self._draw_item_recursive(painter, item, items_dict)

        if self.edit_mode_parent_id:
            panel = self.get_item_by_id(self.edit_mode_parent_id)
            if panel: painter.setPen(QPen(Qt.GlobalColor.cyan, 4, Qt.PenStyle.DashLine)); painter.drawRect(panel['rect'])

        if self.interaction_mode == "split" and len(self.split_line_points) == 2:
            pen = QPen(Qt.GlobalColor.red, 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(self.split_line_points[0], self.split_line_points[1])

        if self.selected_item_id:
            selected_item = self.get_item_by_id(self.selected_item_id)
            if selected_item: self._draw_selection_handles(painter, selected_item)
        if self.current_rect_for_drawing: self._draw_drawing_rect(painter)
    def _draw_item_recursive(self, painter, item, all_items):
        if item['type'] == 'panel':
            points = item['polygon_points']
            polygon_f = QPolygonF([QPointF(p) for p in points])
            path = QPainterPath()
            path.addPolygon(polygon_f)

            painter.save()
            painter.setClipPath(path)

            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.drawPolygon(polygon_f)

            for child_id in item.get('children', []):
                child_item = all_items.get(child_id)
                if child_item: self._draw_item_recursive(painter, child_item, all_items)
            painter.restore()
        elif item['type'] == 'image': painter.drawPixmap(item['rect'], item['pixmap'])
        elif item['type'] == 'text':
            glow_fx = item.get('glow_fx')
            if glow_fx and glow_fx['enabled']:
                self.draw_text_with_glow(painter, item)
            else:
                self.draw_standard_text(painter, item)

    def draw_standard_text(self, painter, item):
        font = item.get('font', QFont())
        painter.setFont(font)
        painter.setPen(QPen(item['color']))
        painter.drawText(item['rect'], Qt.TextFlag.TextWordWrap, item['text'])

    def draw_text_with_glow(self, painter, item):
        glow_fx = item['glow_fx']
        font = item.get('font', QFont())

        # Determine the size needed for the offscreen pixmap
        glow_size = glow_fx['size']
        padding = glow_size * 2
        original_rect = item['rect']
        pixmap_rect = original_rect.adjusted(-padding, -padding, padding, padding)

        # Create offscreen buffer
        buffer = QPixmap(pixmap_rect.size())
        buffer.fill(Qt.GlobalColor.transparent)

        # Draw the text onto the buffer
        buffer_painter = QPainter(buffer)
        buffer_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        buffer_painter.setFont(font)
        buffer_painter.setPen(QPen(glow_fx['color']))
        # Adjust text position for the padding
        buffer_painter.drawText(QRect(padding, padding, original_rect.width(), original_rect.height()), Qt.TextFlag.TextWordWrap, item['text'])
        buffer_painter.end()

        # Apply blur effect
        scene = QGraphicsScene()
        pixmap_item = scene.addPixmap(buffer)
        blur_effect = QGraphicsBlurEffect()
        blur_effect.setBlurRadius(glow_size)
        pixmap_item.setGraphicsEffect(blur_effect)

        # Render the blurred scene back to a pixmap
        glow_pixmap = QPixmap(pixmap_rect.size())
        glow_pixmap.fill(Qt.GlobalColor.transparent)
        renderer = QPainter(glow_pixmap)
        scene.render(renderer)
        renderer.end()

        # Draw the glow pixmap to the main canvas
        painter.setOpacity(glow_fx['opacity'])
        painter.drawPixmap(pixmap_rect.topLeft(), glow_pixmap)
        painter.setOpacity(1.0) # Reset opacity

        # Draw the original text on top
        self.draw_standard_text(painter, item)

    def mouseDoubleClickEvent(self, event):
        item_at_pos = self.find_item_for_selection(event.pos())

        if item_at_pos and item_at_pos['type'] == 'text':
            self.edit_text_item(item_at_pos)
            return

        panel_at_pos = self.find_top_level_item(event.pos(), item_type='panel')
        if panel_at_pos:
            if self.edit_mode_parent_id == panel_at_pos['id']:
                self.edit_mode_parent_id = None
                self.set_selected_item_id(panel_at_pos['id'])
            else:
                self.edit_mode_parent_id = panel_at_pos['id']
                self.set_selected_item_id(None)
        else:
            self.edit_mode_parent_id = None
            self.double_click_flag = True
            self.start_point = event.pos()
        self.update()

    def mousePressEvent(self, event):
        self.double_click_flag = False # Reset flag on any single press
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.pos()

        if self.interaction_mode == "split":
            self.split_line_points = [pos, pos]
            self.update()
            return

        if self.interaction_mode == "edit_frame":
            if self.hovered_vertex_index != -1:
                self.dragged_vertex_index = self.hovered_vertex_index
            elif self.hovered_edge_index != -1:
                self.dragged_edge_index = self.hovered_edge_index
                self.drag_start_position = pos
            return

        handle = self.get_handle_at_pos(pos)

        if handle:
            self.interaction_mode = "resize"
            self.resize_handle = handle
        else:
            item_to_select = self.find_item_for_selection(pos)
            if item_to_select:
                self.set_selected_item_id(item_to_select['id'])
                self.interaction_mode = "move"
                self.move_offset = pos - item_to_select['rect'].topLeft()
            else:
                self.set_selected_item_id(None)
                # Important: Don't reset interaction_mode if it's already "split"
                if self.interaction_mode != "split":
                     self.interaction_mode = "none"
        self.update()

    def mouseMoveEvent(self, event):
        if self.double_click_flag and (event.buttons() & Qt.MouseButton.LeftButton):
            self.interaction_mode = "draw"
            self.current_rect_for_drawing = QRect(self.start_point, event.pos()).normalized()
            self.update()
            return # Prioritize drawing after a double click

        if self.interaction_mode == "split":
            if len(self.split_line_points) == 2:
                self.split_line_points[1] = event.pos()
                self.update()
            return

        if self.interaction_mode == "edit_frame":
            if self.dragged_vertex_index != -1 and self.selected_item_id:
                item = self.get_item_by_id(self.selected_item_id)
                if item:
                    item['polygon_points'][self.dragged_vertex_index] = event.pos()
                    self.update_item_bounding_rect(self.selected_item_id)
                    self.update()
            elif self.dragged_edge_index != -1 and self.selected_item_id:
                item = self.get_item_by_id(self.selected_item_id)
                if item:
                    points = item['polygon_points']
                    p1_idx = self.dragged_edge_index
                    p2_idx = (self.dragged_edge_index + 1) % len(points)
                    p1 = points[p1_idx]
                    p2 = points[p2_idx]

                    edge_vec = p2 - p1
                    normal_vec = QPointF(edge_vec.y(), -edge_vec.x())
                    normal_vec.normalize()

                    drag_vec = event.pos() - self.drag_start_position

                    dot_product = QPointF.dotProduct(QPointF(drag_vec), normal_vec)
                    move_vec = normal_vec * dot_product

                    item['polygon_points'][p1_idx] = p1 + move_vec.toPoint()
                    item['polygon_points'][p2_idx] = p2 + move_vec.toPoint()

                    self.drag_start_position = event.pos() # Update start for next delta
                    self.update_item_bounding_rect(self.selected_item_id)
                    self.update()
            else: # Only update hover state if not dragging
                self.hovered_vertex_index = -1
                self.hovered_edge_index = -1
                if self.selected_item_id:
                    item = self.get_item_by_id(self.selected_item_id)
                    self.hovered_vertex_index = self.get_vertex_at_pos(event.pos(), item)
                    if self.hovered_vertex_index == -1:
                        self.hovered_edge_index = self.get_edge_at_pos(event.pos(), item)
                self.update()
            return

        if self.interaction_mode == "resize" and self.selected_item_id: self._handle_resize(event)
        elif self.interaction_mode == "move" and self.selected_item_id:
            item = self.get_item_by_id(self.selected_item_id)
            if not item: return
            new_top_left = event.pos() - self.move_offset
            delta = new_top_left - item['rect'].topLeft()
            item['rect'].moveTopLeft(new_top_left)

            # If the item has polygon points, move them as well
            if 'polygon_points' in item:
                item['polygon_points'] = [p + delta for p in item['polygon_points']]

            # If the item is a panel, move all its children too
            if item['type'] == 'panel' and not self.edit_mode_parent_id:
                for child_id in item['children']:
                    child = self.get_item_by_id(child_id)
                    if child:
                        child['rect'].translate(delta)
                        # Also move polygon points of children if they exist
                        if 'polygon_points' in child:
                            child['polygon_points'] = [p + delta for p in child['polygon_points']]
        elif self.interaction_mode == "draw":
             self.current_rect_for_drawing = QRect(self.start_point, event.pos()).normalized()
        self.update()

    def mouseReleaseEvent(self, event):
        if self.interaction_mode == "split":
            if len(self.split_line_points) == 2:
                p1 = self.split_line_points[0]
                p2 = self.split_line_points[1]

                # Find a panel that intersects the line's bounding box
                line_rect = QRect(p1, p2).normalized()
                target_item = None
                z_ordered_ids = self.layer_manager.get_z_ordered_ids()
                for item_id in reversed(z_ordered_ids):
                    item = self.get_item_by_id(item_id)
                    if item and item['type'] == 'panel' and item.get('parent') is None:
                        if item['rect'].intersects(line_rect):
                             # A simple rect intersection is a good first check
                            target_item = item
                            break

                if target_item:
                    self.split_polygon(target_item['id'], p1, p2)
                else:
                    # If no panel is under the line, split the whole canvas view
                    canvas_rect = self.rect()
                    # Create a temporary item representing the canvas
                    temp_canvas_id = str(uuid.uuid4())
                    self.get_current_page_items()[temp_canvas_id] = {
                        'id': temp_canvas_id, 'type': 'panel', 'rect': canvas_rect,
                        'polygon_points': [canvas_rect.topLeft(), canvas_rect.topRight(), canvas_rect.bottomRight(), canvas_rect.bottomLeft()]
                    }
                    self.split_polygon(temp_canvas_id, p1, p2)


            self.split_line_points = []
            self.update()
            return

        if self.interaction_mode == "draw" and self.current_rect_for_drawing:
            item_id, _ = self._create_item('panel', self.current_rect_for_drawing)
            self.set_selected_item_id(item_id)

        if self.dragged_vertex_index != -1:
            self.dragged_vertex_index = -1
        if self.dragged_edge_index != -1:
            self.dragged_edge_index = -1

        # Reset interaction mode if not in a persistent mode
        if self.interaction_mode not in ["split", "edit_frame"]:
            self.interaction_mode = "none"
        self.current_rect_for_drawing = None
        self.double_click_flag = False # Always reset flag on release
        self._update_layer_view()
        self.update()
    def clear_canvas(self): self.pages = [{'items': {}}]; self.set_current_page(0)

    def wheelEvent(self, event):
        if not self.selected_item_id:
            return

        item = self.get_item_by_id(self.selected_item_id)
        if not item:
            return

        delta = event.angleDelta().y()
        if item['type'] == 'image':
            scale_factor = 1.1 if delta > 0 else 1 / 1.1
            rect = item['rect']
            new_width = rect.width() * scale_factor
            new_height = rect.height() * scale_factor

            center = rect.center()
            new_rect = QRect(
                int(center.x() - new_width / 2),
                int(center.y() - new_height / 2),
                int(new_width),
                int(new_height)
            )
            item['rect'] = new_rect
            self.update()
        elif item['type'] == 'text':
            font = item.get('font', QFont())
            current_size = font.pointSize()
            if current_size <= 0: current_size = 12 # Default size

            if delta > 0:
                new_size = current_size + 1
            else:
                new_size = max(1, current_size - 1)

            font.setPointSize(new_size)
            self.update_selected_text_item_font(font)
            # Also update the controls in the text tools widget
            if self.text_tools:
                self.text_tools.update_controls(item)

        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace: self.delete_selected_item()
        else: super().keyPressEvent(event)
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasFormat(self.MIME_TYPE): event.acceptProposedAction()
    def _handle_resize(self, event):
        item = self.get_item_by_id(self.selected_item_id)
        if not item: return

        old_rect = QRect(item['rect'])
        new_rect = QRect(item['rect']) # This is the one we'll modify

        if item['type'] == 'image' and item['pixmap']:
            aspect_ratio = item['pixmap'].width() / item['pixmap'].height() if item['pixmap'].height() != 0 else 1.0
            if self.resize_handle == "topLeft": fixed_corner = new_rect.bottomRight()
            elif self.resize_handle == "topRight": fixed_corner = new_rect.bottomLeft()
            elif self.resize_handle == "bottomLeft": fixed_corner = new_rect.topRight()
            else: fixed_corner = new_rect.topLeft()
            new_pos = event.pos(); delta = new_pos - fixed_corner; new_width = abs(delta.x()); new_height = abs(delta.y())
            if new_width / aspect_ratio > new_height: new_height = int(new_width / aspect_ratio)
            else: new_width = int(new_height * aspect_ratio)
            if self.resize_handle == "topLeft": new_rect = QRect(fixed_corner.x() - new_width, fixed_corner.y() - new_height, new_width, new_height)
            elif self.resize_handle == "topRight": new_rect = QRect(fixed_corner.x(), fixed_corner.y() - new_height, new_width, new_height)
            elif self.resize_handle == "bottomLeft": new_rect = QRect(fixed_corner.x() - new_width, fixed_corner.y(), new_width, new_height)
            else: new_rect = QRect(fixed_corner, QPoint(fixed_corner.x() + new_width, fixed_corner.y() + new_height))
        else: # For panels and other non-image types
            if self.resize_handle == "topLeft": new_rect.setTopLeft(event.pos())
            elif self.resize_handle == "topRight": new_rect.setTopRight(event.pos())
            elif self.resize_handle == "bottomLeft": new_rect.setBottomLeft(event.pos())
            elif self.resize_handle == "bottomRight": new_rect.setBottomRight(event.pos())

        normalized_new_rect = new_rect.normalized()
        item['rect'] = normalized_new_rect

        # If the item has polygon points, scale them to match the new rect
        if 'polygon_points' in item:
            old_width = old_rect.width()
            old_height = old_rect.height()
            new_width = normalized_new_rect.width()
            new_height = normalized_new_rect.height()

            if old_width == 0: old_width = 1
            if old_height == 0: old_height = 1

            scale_x = new_width / old_width
            scale_y = new_height / old_height

            new_points = []
            for p in item['polygon_points']:
                # Vector from old top-left to the point
                vec_from_origin = p - old_rect.topLeft()
                # Scale the vector
                scaled_vec = QPointF(vec_from_origin.x() * scale_x, vec_from_origin.y() * scale_y)
                # Add to new top-left to get final point position
                final_p = scaled_vec + QPointF(normalized_new_rect.topLeft())
                new_points.append(final_p.toPoint())
            item['polygon_points'] = new_points
    def get_handle_at_pos(self, pos):
        if self.selected_item_id:
            item = self.get_item_by_id(self.selected_item_id)
            if not item: return None
            handles = self.get_resize_handles(item['rect'])
            for handle, rect in handles.items():
                if rect.contains(pos): return handle
        return None
    def _draw_selection_handles(self, painter, item):
        painter.setPen(QPen(Qt.GlobalColor.blue, 3, Qt.PenStyle.SolidLine)); painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawRect(item['rect'])

        # In edit_frame mode, draw vertices and highlight hovered edge
        if self.interaction_mode == "edit_frame" and item['type'] == 'panel':
            points = item['polygon_points']
            # Draw vertices
            painter.setBrush(QBrush(Qt.GlobalColor.red))
            for p in points:
                painter.drawRect(p.x() - 4, p.y() - 4, 8, 8)

            # Highlight hovered edge
            if self.hovered_edge_index != -1:
                p1 = points[self.hovered_edge_index]
                p2 = points[(self.hovered_edge_index + 1) % len(points)]
                painter.setPen(QPen(Qt.GlobalColor.red, 3, Qt.PenStyle.SolidLine))
                painter.drawLine(p1, p2)
        else:
             # Draw standard resize handles if not in frame edit mode
            handles = self.get_resize_handles(item['rect'])
            painter.setBrush(QBrush(Qt.GlobalColor.blue))
            for handle in handles.values(): painter.drawRect(handle)

    def _draw_drawing_rect(self, painter):
        painter.setPen(QPen(Qt.GlobalColor.red, 1, Qt.PenStyle.DashLine)); painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawRect(self.current_rect_for_drawing)
    def get_resize_handles(self, rect):
        h = {}; h["topLeft"] = QRect(rect.topLeft().x() - 4, rect.topLeft().y() - 4, 8, 8); h["topRight"] = QRect(rect.topRight().x() - 4, rect.topRight().y() - 4, 8, 8); h["bottomLeft"] = QRect(rect.bottomLeft().x() - 4, rect.bottomLeft().y() - 4, 8, 8); h["bottomRight"] = QRect(rect.bottomRight().x() - 4, rect.bottomRight().y() - 4, 8, 8); return h

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Comic Creator v2.6")
        self.setGeometry(100, 100, 1400, 900)

        self.character_manager = CharacterManager(self)
        self.layer_manager = LayerManager(self)
        self.bg_remover = BackgroundRemover(self)
        self.page_manager = PageManager(self)
        self.text_tools = TextToolsWidget(self)

        self.canvas = Canvas(self, self.character_manager, self.layer_manager, self.page_manager, self.text_tools)
        self.setCentralWidget(self.canvas)

        self.character_manager.set_canvas(self.canvas) # Set canvas reference
        self.layer_manager.set_canvas(self.canvas)
        self.page_manager.set_canvas(self.canvas)
        self.text_tools.set_canvas(self.canvas)

        # Connect canvas selection signal to character manager
        self.canvas.selectionChanged.connect(self.character_manager.update_dialogue_editor)

        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(self.toolbar)
        self._create_toolbar()

        self.menu_bar = self.menuBar()
        self._create_menu_bar()
        self._create_docks()
        self.page_manager.update_page_list()

    def _create_docks(self):
        self.page_dock = QDockWidget("Pages", self)
        self.page_dock.setWidget(self.page_manager)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.page_dock)

        self.text_dock = QDockWidget("Text Tools", self) # New dock for text tools
        self.text_dock.setWidget(self.text_tools)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.text_dock)

        self.bg_remover_dock = QDockWidget("Background Remover", self)
        self.bg_remover_dock.setWidget(self.bg_remover)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.bg_remover_dock)

        self.character_dock = QDockWidget("Characters", self)
        self.character_dock.setWidget(self.character_manager)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.character_dock)

        self.layer_dock = QDockWidget("Layers", self)
        self.layer_dock.setWidget(self.layer_manager)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.layer_dock)

    def _create_toolbar(self):
        # Panel splitting action
        split_panel_action = QAction("Split Panel", self)
        split_panel_action.setCheckable(True) # Make it a toggle-able mode
        split_panel_action.triggered.connect(self.toggle_split_mode)
        self.toolbar.addAction(split_panel_action)

        # Frame editing action
        edit_frame_action = QAction("Edit Frame", self)
        edit_frame_action.setCheckable(True)
        edit_frame_action.triggered.connect(self.toggle_edit_frame_mode)
        self.toolbar.addAction(edit_frame_action)
        self.toolbar.addSeparator()

        add_panel_action = QAction("Add Panel (Container)", self)
        self.toolbar.addAction(add_panel_action)
        # Add Text action is now in the TextToolsWidget
        self.toolbar.addSeparator()
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self.canvas.delete_selected_item)
        self.toolbar.addAction(delete_action)

    def toggle_split_mode(self, checked):
        if checked:
            self.canvas.enter_split_mode()
        else:
            self.canvas.exit_split_mode()

    def toggle_edit_frame_mode(self, checked):
        if checked:
            self.canvas.enter_edit_frame_mode()
        else:
            self.canvas.exit_edit_frame_mode()

    def _create_menu_bar(self):
        file_menu = self.menu_bar.addMenu("&File"); actions = {"New": self.new_project, "Open...": self.open_project, "Save As...": self.save_project, "Export As...": self.export_comic, "Exit": self.close}; file_menu.addAction(QAction("New", self, triggered=actions["New"])); file_menu.addAction(QAction("Open...", self, triggered=actions["Open..."])); file_menu.addAction(QAction("Save As...", self, triggered=actions["Save As..."])); file_menu.addSeparator(); file_menu.addAction(QAction("Export As...", self, triggered=actions["Export As..."])); file_menu.addSeparator(); file_menu.addAction(QAction("Exit", self, triggered=actions["Exit"]))
    def new_project(self): self.canvas.clear_canvas(); self.character_manager.clear_characters()

    def project_data_to_dict(self):
        project_data = {'characters': {}, 'pages': []}
        for name, color in self.character_manager.characters.items(): project_data['characters'][name] = color.name()
        for page in self.canvas.pages:
            page_data = {'items': {}}
            for item_id, item in page['items'].items():
                item_copy = item.copy()
                item_copy['rect'] = (item['rect'].x(), item['rect'].y(), item['rect'].width(), item['rect'].height())
                if item_copy['type'] == 'panel':
                    item_copy['polygon_points'] = [(p.x(), p.y()) for p in item['polygon_points']]
                if item_copy['type'] == 'image':
                    buffer = QBuffer(); buffer.open(QIODevice.OpenModeFlag.WriteOnly); item_copy['pixmap'].save(buffer, "PNG");
                    item_copy['pixmap_base64'] = base64.b64encode(buffer.data().data()).decode('utf-8')
                    del item_copy['pixmap']
                elif item_copy['type'] == 'text':
                    color = item_copy['color']
                    item_copy['color'] = (color.red(), color.green(), color.blue(), color.alpha())
                    if 'font' in item_copy:
                        font = item_copy['font']
                        item_copy['font_data'] = {
                            'family': font.family(),
                            'pointSize': font.pointSize(),
                            'bold': font.bold(),
                            'italic': font.italic()
                        }
                        del item_copy['font']
                    if 'glow_fx' in item_copy:
                        glow_color = item_copy['glow_fx']['color']
                        item_copy['glow_fx']['color_hex'] = glow_color.name()
                        del item_copy['glow_fx']['color']
                page_data['items'][item_id] = item_copy
            project_data['pages'].append(page_data)
        return project_data

    def load_project_from_data(self, project_data):
        self.character_manager.load_characters(project_data.get('characters', {}))
        self.canvas.pages = []
        for page_data in project_data.get('pages', [{'items': {}}]):
            new_page = {'items': {}}
            for item_id, item_data in page_data['items'].items():
                item_copy = item_data.copy()
                item_copy['rect'] = QRect(*item_copy['rect'])
                if item_copy['type'] == 'panel':
                    item_copy['polygon_points'] = [QPoint(x, y) for x, y in item_copy['polygon_points']]
                if item_copy['type'] == 'image':
                    pixmap = QPixmap()
                    pixmap.loadFromData(QByteArray(base64.b64decode(item_copy['pixmap_base64'])))
                    item_copy['pixmap'] = pixmap
                    del item_copy['pixmap_base64']
                elif item_copy['type'] == 'text':
                    item_copy['color'] = QColor(*item_copy['color'])
                    if 'font_data' in item_copy:
                        font_data = item_copy['font_data']
                        font = QFont(font_data['family'])
                        font.setPointSize(font_data['pointSize'])
                        font.setBold(font_data['bold'])
                        font.setItalic(font_data['italic'])
                        item_copy['font'] = font
                        del item_copy['font_data']
                    if 'glow_fx' in item_copy:
                        item_copy['glow_fx']['color'] = QColor(item_copy['glow_fx']['color_hex'])
                        del item_copy['glow_fx']['color_hex']
                new_page['items'][item_id] = item_copy
            self.canvas.pages.append(new_page)
        self.canvas.set_current_page(0)

    def save_project(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Comic Project", "", "Comic Project Files (*.comicproj)")
        if not file_path: return
        try:
            with open(file_path, 'w') as f: json.dump(self.project_data_to_dict(), f, indent=2)
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
                self.canvas.set_current_page(i); QApplication.processEvents()
                pixmap = QPixmap(self.canvas.size()); self.canvas.render(pixmap)
                page_file_path = f"{base_path}_page_{i+1}{ext}"
                if not pixmap.save(page_file_path): QMessageBox.warning(self, "Export Error", f"Failed to save page {i+1}."); break
            else: QMessageBox.information(self, "Export Successful", f"All pages exported successfully.")
        else:
            pixmap = QPixmap(self.canvas.size()); self.canvas.render(pixmap)
            if not pixmap.save(file_path): QMessageBox.warning(self, "Export Error", "Failed to save the comic.")
            else: QMessageBox.information(self, "Export Successful", f"Current page exported to:\n{file_path}")
        self.canvas.set_current_page(original_page)

if __name__ == "__main__":
    app = QApplication(sys.argv); main_win = MainWindow(); main_win.show(); sys.exit(app.exec())
