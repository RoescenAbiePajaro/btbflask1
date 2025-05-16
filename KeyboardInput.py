# KeyboardInput.py
import cv2
import numpy as np
from collections import deque

class KeyboardInput:
    def __init__(self):
        self.text = ""
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0
        self.cursor_blink_interval = 0.5  # seconds
        self.text_objects = deque(maxlen=20)  # Stores all text objects
        self.dragging = False
        self.drag_object_index = -1
        self.drag_offset = (0, 0)
        self.default_font = cv2.FONT_HERSHEY_SIMPLEX
        self.default_scale = 1.0
        self.default_thickness = 2
        self.default_color = (255, 255, 255)  # White
        self.outline_color = (0, 0, 0)  # Black for outline
        self.outline_thickness = 4
        self.current_input_position = (640, 360)  # Center position
        self.input_dragging = False
        self.input_drag_offset = (0, 0)
        self.selected_object_index = -1  # Track selected text object
        self.text_history = []  # To store text object states for undo/redo
        self.history_index = -1


    def toggle_keyboard_mode(self):
        self.active = not self.active
        if self.active:
            self.text = ""
            self.cursor_visible = True
            self.cursor_timer = 0
            # Create a new text object at center when toggling on
            self.current_input_position = (640, 360)

    def process_key_input(self, key):
        if not self.active:
            return False

        if key == 13:  # Enter key
            if self.text:
                self.add_text_object()
                self.text = ""
                # Create new text at current drag position
                self.current_input_position = self.current_input_position
            return True
        elif key == 8:  # Backspace
            self.text = self.text[:-1]
            return True
        elif 32 <= key <= 126:  # Printable ASCII characters
            self.text += chr(key)
            return True

        return False

    def add_text_object(self):
        if not self.text:
            return


        self.save_state()

        self.text_objects.append({
            'text': self.text,
            'position': self.current_input_position,
            'color': self.default_color,
            'font': self.default_font,
            'scale': self.default_scale,
            'thickness': self.default_thickness,
            'selected': False
        })



    def delete_selected(self):
        """Delete the currently selected text object"""
        if self.drag_object_index >= 0:
            # Remove the selected object
            if 0 <= self.drag_object_index < len(self.text_objects):
                del self.text_objects[self.drag_object_index]
            self.drag_object_index = -1

    def save_state(self):
        """Save current text objects state for undo/redo"""
        # Truncate history if we're not at the end
        if self.history_index < len(self.text_history) - 1:
            self.text_history = self.text_history[:self.history_index + 1]

        # Save current state
        self.text_history.append(list(self.text_objects))
        self.history_index = len(self.text_history) - 1

    def undo(self):
        """Undo the last text operation"""
        if self.history_index > 0:
            self.history_index -= 1
            self.text_objects = deque(list(self.text_history[self.history_index]), maxlen=20)
            return True
        return False

    def redo(self):
        """Redo the last undone text operation"""
        if self.history_index < len(self.text_history) - 1:
            self.history_index += 1
            self.text_objects = deque(list(self.text_history[self.history_index]), maxlen=20)
            return True
        return False

    def update(self, dt):
        if not self.active:
            return

        # Update cursor blink timer
        self.cursor_timer += dt
        if self.cursor_timer >= self.cursor_blink_interval:
            self.cursor_timer = 0
            self.cursor_visible = not self.cursor_visible

    def draw(self, img):
        # Draw all existing text objects (always draw these)
        for i, obj in enumerate(self.text_objects):
            # Draw outline
            cv2.putText(
                img,
                obj['text'],
                obj['position'],
                obj['font'],
                obj['scale'],
                self.outline_color,
                self.outline_thickness
            )
            # Draw main text
            cv2.putText(
                img,
                obj['text'],
                obj['position'],
                obj['font'],
                obj['scale'],
                obj['color'],
                obj['thickness']
            )

            # Draw selection rectangle if selected
            if obj['selected']:
                text_size = cv2.getTextSize(
                    obj['text'],
                    obj['font'],
                    obj['scale'],
                    obj['thickness']
                )[0]
                top_left = (
                    obj['position'][0] - 5,
                    obj['position'][1] - text_size[1] - 5
                )
                bottom_right = (
                    obj['position'][0] + text_size[0] + 5,
                    obj['position'][1] + 5
                )
                cv2.rectangle(img, top_left, bottom_right, (0, 255, 0), 2)

        # Only draw current input text and cursor if keyboard is active
        if self.active and (self.text or self.cursor_visible):
            # Draw outline
            cv2.putText(
                img,
                self.text,
                self.current_input_position,
                self.default_font,
                self.default_scale,
                self.outline_color,
                self.outline_thickness
            )

            # Draw main text
            cv2.putText(
                img,
                self.text,
                self.current_input_position,
                self.default_font,
                self.default_scale,
                self.default_color,
                self.default_thickness
            )

            # Draw cursor if visible
            if self.cursor_visible:
                text_size = cv2.getTextSize(
                    self.text,
                    self.default_font,
                    self.default_scale,
                    self.default_thickness
                )[0]
                cursor_pos = (
                    self.current_input_position[0] + text_size[0],
                    self.current_input_position[1]
                )
                cv2.line(
                    img,
                    cursor_pos,
                    (cursor_pos[0], cursor_pos[1] - 30),
                    self.default_color,
                    2
                )

    def check_drag_start(self, x, y):
        # First check if we're selecting existing text objects
        for i, obj in enumerate(reversed(self.text_objects)):
            idx = len(self.text_objects) - 1 - i  # Get original index
            text_size = cv2.getTextSize(
                obj['text'],
                obj['font'],
                obj['scale'],
                obj['thickness']
            )[0]

            text_left = obj['position'][0]
            text_right = obj['position'][0] + text_size[0]
            text_top = obj['position'][1] - text_size[1]
            text_bottom = obj['position'][1]

            if (text_left <= x <= text_right and
                    text_top <= y <= text_bottom):
                # Deselect all other objects
                for obj in self.text_objects:
                    obj['selected'] = False
                # Select this object
                self.text_objects[idx]['selected'] = True
                self.drag_object_index = idx
                self.drag_offset = (x - obj['position'][0], y - obj['position'][1])
                self.dragging = True
                return True

        # Then check if we're dragging current input text (only if keyboard active)
        if self.active and (self.text or self.cursor_visible):
            text_size = cv2.getTextSize(
                self.text,
                self.default_font,
                self.default_scale,
                self.default_thickness
            )[0]

            text_left = self.current_input_position[0]
            text_right = self.current_input_position[0] + text_size[0]
            text_top = self.current_input_position[1] - text_size[1]
            text_bottom = self.current_input_position[1]

            if (text_left <= x <= text_right and
                    text_top <= y <= text_bottom):
                self.input_dragging = True
                self.input_drag_offset = (
                    x - self.current_input_position[0],
                    y - self.current_input_position[1]
                )
                return True

        # If clicking elsewhere, deselect all
        for obj in self.text_objects:
            obj['selected'] = False
        self.drag_object_index = -1
        return False

    def update_drag(self, x, y):
        if self.input_dragging:
            # Update position of current input text
            self.current_input_position = (
                x - self.input_drag_offset[0],
                y - self.input_drag_offset[1]
            )
        elif self.dragging and self.drag_object_index >= 0:
            # Update position of dragged text object
            obj = self.text_objects[self.drag_object_index]
            new_pos = (x - self.drag_offset[0], y - self.drag_offset[1])
            self.text_objects[self.drag_object_index]['position'] = new_pos

    def end_drag(self):
        self.input_dragging = False
        self.dragging = False
        self.drag_object_index = -1

    def clear_selection(self):
        """Clear all text selections"""
        for obj in self.text_objects:
            obj['selected'] = False
        self.drag_object_index = -1