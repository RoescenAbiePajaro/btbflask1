# VirtualPainter.py
# from flask import Flask, render_template, Response, request, jsonify
from flask import Blueprint, render_template, Response, request, jsonify
import cv2
import numpy as np
import os
import time
import HandTrackingModule as htm
from KeyboardInput import KeyboardInput

# app = Flask(__name__)
painter_bp = Blueprint('painter', __name__)

# Variables
brushSize = 10
eraserSize = 100
fps = 60
time_per_frame = 5.0 / fps

# Load header images
folderPath = 'static/header'
myList = sorted(os.listdir(folderPath))
overlayList = [cv2.imread(f"{folderPath}/{imPath}") for imPath in myList]

# Load guide images (resized to 1280x595)
folderPath = 'static/guide'
myList = sorted(os.listdir(folderPath))
guideList = []
for imPath in myList:
    img = cv2.imread(f"{folderPath}/{imPath}")
    if img is not None:
        # Resize guide images to fit below header (1280x595)
        img = cv2.resize(img, (1280, 595))
        guideList.append(img)

# Default images
header = overlayList[0]
current_guide_index = 0  # Track current guide index
current_guide = None  # Initially no guide shown
show_guide = False  # Track guide visibility state

# Swipe detection variables
swipe_threshold = 50  # Minimum horizontal movement to consider a swipe
swipe_start_x = None  # To track where swipe started
swipe_active = False  # To track if swipe is in progress

# Default drawing color
drawColor = (255, 0, 255)

# Set up the camera
cap = cv2.VideoCapture(1)
cap.set(3, 1280)  # Width
cap.set(4, 720)  # Height

# Assigning Detector
detector = htm.handDetector(detectionCon=0.85)

# Previous points
xp, yp = 0, 0

# Create Image Canvas
imgCanvas = np.zeros((720, 1280, 3), np.uint8)

# Undo/Redo Stack - now stores both canvas and text state
undoStack = []
redoStack = []

# Create keyboard input handler
keyboard_input = KeyboardInput()
last_time = time.time()


# Function to save current state (both canvas and text)
def save_state():
    return {
        'canvas': imgCanvas.copy(),
        'text_objects': keyboard_input.text_objects.copy()
    }


# Function to restore state (both canvas and text)
def restore_state(state):
    global imgCanvas
    imgCanvas = state['canvas'].copy()
    keyboard_input.text_objects = state['text_objects'].copy()


# Function to save the canvas
def save_canvas():
    import time
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(os.path.expanduser("~"), "Pictures", f"saved_painting_{timestamp}.png")

    # Create a copy of the canvas to draw text on
    saved_img = imgCanvas.copy()

    # Draw all text objects onto the saved image
    for obj in keyboard_input.text_objects:
        cv2.putText(
            saved_img,
            obj['text'],
            obj['position'],
            obj['font'],
            obj['scale'],
            obj['color'],
            obj['thickness'] + 2
        )

        # Then draw main text
        cv2.putText(
            saved_img,
            obj['text'],
            obj['position'],
            obj['font'],
            obj['scale'],
            obj['color'],
            obj['thickness']
        )

    cv2.imwrite(save_path, saved_img)
    print(f"Canvas Saved at {save_path}")
    return save_path


# Function to interpolate points
def interpolate_points(x1, y1, x2, y2, num_points=10):
    points = []
    for i in range(num_points):
        x = int(x1 + (x2 - x1) * (i / num_points))
        y = int(y1 + (y2 - y1) * (i / num_points))
        points.append((x, y))
    return points

def generate_frames():
    global xp, yp, swipe_start_x, swipe_active, last_time, header, current_guide_index, current_guide, show_guide, drawColor, undoStack, redoStack, brushSize, eraserSize


    while True:
        start_time = time.time()

        # 1. Import Image
        success, img = cap.read()
        if not success:
            break
        img = cv2.flip(img, 1)

        # 2. Find Hand Landmarks
        img = detector.findHands(img, draw=False)
        lmList = detector.findPosition(img, draw=False)

        # Draw black outline (thicker)
        cv2.putText(img, "Selection Mode - Two Fingers Up", (50, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)  # Black with thickness 4

        # Draw main white text (thinner)
        cv2.putText(img, "Selection Mode - Two Fingers Up", (50, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)  # White with thickness 2

        if len(lmList) != 0:
            # Tip of index and middle fingers
            x1, y1 = lmList[8][1:]
            x2, y2 = lmList[12][1:]

            # 3. Check which fingers are up
            fingers = detector.fingersUp()

            # 4. Selection Mode - Two Fingers Up
            if fingers[1] and fingers[2]:
                xp, yp = 0, 0  # Reset points
                swipe_start_x = None  # Reset swipe tracking when in selection mode

                # Detecting selection based on X coordinate
                if y1 < 125:  # Ensure the selection is within the header area
                    if 0 < x1 < 128:  # Save
                        header = overlayList[1]
                        save_path = save_canvas()
                        show_guide = False

                    elif 128 < x1 < 256:  # Pink
                        header = overlayList[2]
                        drawColor = (255, 0, 255)  # Pink
                        show_guide = False
                        keyboard_input.active = False  # Close keyboard input if open

                    elif 256 < x1 < 384:  # Blue
                        header = overlayList[3]
                        drawColor = (255, 0, 0)  # Blue
                        show_guide = False
                        keyboard_input.active = False  # Close keyboard input if open

                    elif 384 < x1 < 512:  # Green
                        header = overlayList[4]
                        drawColor = (0, 255, 0)  # Green
                        show_guide = False
                        keyboard_input.active = False  # Close keyboard input if open

                    elif 512 < x1 < 640:  # Yellow
                        header = overlayList[5]
                        drawColor = (0, 255, 255)  # Yellow
                        show_guide = False
                        keyboard_input.active = False  # Close keyboard input if open

                    elif 640 < x1 < 768:  # Eraser
                        header = overlayList[6]
                        drawColor = (0, 0, 0)  # Eraser
                        show_guide = False
                        keyboard_input.active = False  # Close keyboard input if open
                        # Delete selected text if any
                        keyboard_input.delete_selected()

                    # Undo/Redo handling with global state
                    elif 768 < x1 < 896:  # Undo
                        header = overlayList[7]
                        if len(undoStack) > 0:
                            redoStack.append(save_state())
                            state = undoStack.pop()
                            restore_state(state)
                        show_guide = False

                    elif 896 < x1 < 1024:  # Redo
                        header = overlayList[8]
                        if len(redoStack) > 0:
                            undoStack.append(save_state())
                            state = redoStack.pop()
                            restore_state(state)
                        show_guide = False

                    elif 1024 < x1 < 1152:  # Guide
                        header = overlayList[9]
                        # Toggle guide display
                        show_guide = True  # Always show guide when selected
                        current_guide_index = 0  # Reset to first guide
                        current_guide = guideList[current_guide_index]  # Show first guide image
                        keyboard_input.active = False  # Close keyboard input if open

                    elif 1155 < x1 < 1280:
                        if not keyboard_input.active:
                            keyboard_input.active = True
                        header = overlayList[10]
                        show_guide = False

                    # Brush/Eraser size controls
                    elif 1155 < x1 < 1280 and y1 > 650:  # Bottom right area
                        if x1 < 1200:  # Left side - decrease size
                            if drawColor == (0, 0, 0):  # Eraser
                                eraserSize = max(10, eraserSize - 5)
                            else:  # Brush
                                brushSize = max(1, brushSize - 1)
                        else:  # Right side - increase size
                            if drawColor == (0, 0, 0):  # Eraser
                                eraserSize = min(200, eraserSize + 5)
                            else:  # Brush
                                brushSize = min(50, brushSize + 1)

                # Show selection rectangle
                cv2.rectangle(img, (x1, y1 - 25), (x2, y2 + 25), drawColor, cv2.FILLED)

            # ==================== HAND GESTURE LOGIC ====================
            # GUIDE NAVIGATION MODE - One index finger, guide visible, keyboard not active
            if fingers[1] and not fingers[2] and show_guide and not keyboard_input.active:
                # Start or continue swipe gesture
                if swipe_start_x is None:
                    swipe_start_x = x1
                    swipe_active = True
                else:
                    delta_x = x1 - swipe_start_x
                    if abs(delta_x) > swipe_threshold and swipe_active:
                        if delta_x > 0:
                            # Swipe right - previous guide
                            current_guide_index = max(0, current_guide_index - 1)
                        else:
                            # Swipe left - next guide
                            current_guide_index = min(len(guideList) - 1, current_guide_index + 1)

                        current_guide = guideList[current_guide_index]
                        swipe_active = False  # avoid rapid multiple swipes

                # Visual feedback
                cv2.circle(img, (x1, y1), 15, (0, 255, 0), cv2.FILLED)

            # DRAWING MODE - One index finger, guide hidden, keyboard not active
            elif fingers[1] and not fingers[2] and not show_guide and not keyboard_input.active:
                swipe_start_x = None  # cancel swipe tracking when drawing

                # Eraser: Check for overlapping with existing text
                if drawColor == (0, 0, 0):
                    for i, obj in enumerate(reversed(keyboard_input.text_objects)):
                        idx = len(keyboard_input.text_objects) - 1 - i
                        text_size = cv2.getTextSize(obj['text'], obj['font'], obj['scale'], obj['thickness'])[0]

                        x_text, y_text = obj['position']
                        if (x_text <= x1 <= x_text + text_size[0] and
                                y_text - text_size[1] <= y1 <= y_text):
                            del keyboard_input.text_objects[idx]
                            break

                # Visual feedback
                cv2.circle(img, (x1, y1), 15, drawColor, cv2.FILLED)

                if xp == 0 and yp == 0:
                    xp, yp = x1, y1

                # Smooth drawing
                points = interpolate_points(xp, yp, x1, y1)
                for point in points:
                    if drawColor == (0, 0, 0):  # eraser
                        cv2.line(img, (xp, yp), point, drawColor, eraserSize)
                        cv2.line(imgCanvas, (xp, yp), point, drawColor, eraserSize)
                    else:
                        cv2.line(img, (xp, yp), point, drawColor, brushSize)
                        cv2.line(imgCanvas, (xp, yp), point, drawColor, brushSize)
                    xp, yp = point

                # Update undo/redo stacks
                undoStack.append(save_state())
                redoStack.clear()

            # TEXT DRAGGING MODE - Two fingers, keyboard active
            elif keyboard_input.active and fingers[1] and fingers[2]:
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2

                if not keyboard_input.dragging:
                    if keyboard_input.text or keyboard_input.cursor_visible:
                        keyboard_input.check_drag_start(center_x, center_y)
                else:
                    keyboard_input.update_drag(center_x, center_y)

                # Visual feedback
                cv2.circle(img, (center_x, center_y), 15, (0, 255, 255), cv2.FILLED)

            else:
                # Reset states when fingers not up or mode not active
                xp, yp = 0, 0
                swipe_start_x = None
                swipe_active = False
                if keyboard_input.dragging:
                    keyboard_input.end_drag()

        else:
            # No hand detected: reset everything
            swipe_start_x = None
            swipe_active = False
            if keyboard_input.dragging:
                keyboard_input.end_drag()

        # Handle keyboard input
        current_time = time.time()
        dt = current_time - last_time
        last_time = current_time
        keyboard_input.update(dt)

        # 8. Convert Canvas to Grayscale and Invert
        imgGray = cv2.cvtColor(imgCanvas, cv2.COLOR_BGR2GRAY)
        _, imgInv = cv2.threshold(imgGray, 50, 255, cv2.THRESH_BINARY_INV)
        imgInv = cv2.cvtColor(imgInv, cv2.COLOR_GRAY2BGR)
        img = cv2.bitwise_and(img, imgInv)
        img = cv2.bitwise_or(img, imgCanvas)

        # 9. Set Header Image
        img[0:125, 0:1280] = header

        # 10. Draw keyboard text and placeholder
        if keyboard_input.active:
            # Draw semi-transparent typing area background
            typing_area = np.zeros((100, 1280, 3), dtype=np.uint8)
            typing_area[:] = (50, 50, 50)  # Dark gray background
            img[620:720, 0:1280] = cv2.addWeighted(img[620:720, 0:1280], 0.7, typing_area, 0.3, 0)

            keyboard_input.draw(img)

            # Draw instruction text
            instruction_text = "Press Enter to confirm text, ESC to cancel"
            cv2.putText(img, instruction_text, (20, 700),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        else:
            # Draw existing text objects even when keyboard is inactive
            keyboard_input.draw(img)

        # 11. Display Guide Image if active
        if show_guide and current_guide is not None:
            # Create a composite image that preserves the drawing canvas
            guide_area = img[125:720, 0:1280].copy()
            # Blend the guide with the current camera feed (50% opacity)
            blended_guide = cv2.addWeighted(current_guide, 0.3, guide_area, 0.3, 0)
            # Put the blended guide back
            img[125:720, 0:1280] = blended_guide

            # Display guide navigation instructions
            cv2.putText(img, "", (50, 150),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(img, f"Guide {current_guide_index + 1}/{len(guideList)}", (1100, 150),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Encode the frame as JPEG
        ret, buffer = cv2.imencode('.jpg', img)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        # Maintain 60 FPS
        elapsed_time = time.time() - start_time
        if elapsed_time < time_per_frame:
            time.sleep(time_per_frame - elapsed_time)


@painter_bp.route('/')
def index():
    return render_template('index.html')


@painter_bp.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@painter_bp.route('/keypress', methods=['POST'])
def handle_keypress():
    data = request.get_json()
    key = data['key']
    keyboard_input.process_key_input(key)
    return jsonify({'status': 'success'})

@painter_bp.route('/save', methods=['POST'])
def save_image():
    save_path = save_canvas()
    return jsonify({'status': 'success', 'path': save_path})

# if __name__ == '__main__':
#     app.run(debug=True)