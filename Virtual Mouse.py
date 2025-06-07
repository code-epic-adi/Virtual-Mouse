import cv2
import numpy as np
import HandTrackingModule as htm
import time
import autopy
import math
from collections import deque
import pyautogui  # For scroll functionality

# Parameters
wCam, hCam = 640, 480
frameR = 80  # Frame Reduction (reduced for better coverage)
frameR_top = 30  # MOVED UP - Reduced from 50 to 30 for better bottom corner access
smoothening = 7
scroll_sensitivity = 3  # Reduced for finer control
scroll_threshold = 75  # Distance threshold for scroll activation

# SCROLL DEADZONE PARAMETERS
scroll_deadzone_center = 50  # Center position (50% of scroll bar)
scroll_deadzone_range = 10  # ±10% deadzone (40-60% range)
scroll_deadzone_min = scroll_deadzone_center - scroll_deadzone_range  # 40%
scroll_deadzone_max = scroll_deadzone_center + scroll_deadzone_range  # 60%

# Timing and smoothing variables
pTime = 0
plocX, plocY = 0, 0
clocX, clocY = 0, 0

# Scroll tracking variables
scroll_start_y = 0
scroll_active = False
scroll_position = 50  # Start at center (50%)
scroll_history = deque(maxlen=5)  # For smoothing scroll direction
virtual_scroll_y = 0  # Virtual Y position for scroll control

# Click prevention timers
last_left_click = 0
last_right_click = 0
last_double_click = 0
click_cooldown = 0.3  # 300ms cooldown between clicks

# Drag state tracking
drag_active = False
drag_start_pos = None

# Set up the webcam
cap = cv2.VideoCapture(0)
cap.set(3, wCam)
cap.set(4, hCam)

# Initialize the hand detector
detector = htm.handDetector(maxHands=1)
wScr, hScr = autopy.screen.size()
print("Screen size:", wScr, hScr)
print("Enhanced Virtual Mouse Started!")
print("Controls:")
print("- Index finger: Move cursor")
print("- Index + Middle VERY close (<25px): Left click")
print("- Thumb + Middle close: Right click")
print("- Index + Middle + Ring close: Double click")
print("- Index + Middle MEDIUM close (25-50px): Smart Scroll with Deadzone")
print("- Index + Thumb close: Drag and Drop")
print("- Press 'q' to quit")
print(f"- Scroll Deadzone: {scroll_deadzone_min}%-{scroll_deadzone_max}% (no movement)")


def calculate_distance(point1, point2):
    """Calculate Euclidean distance between two points"""
    return math.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)


def draw_scroll_bar(img, scroll_pos):
    """Draw an enhanced scroll position indicator with deadzone visualization"""
    bar_x = wCam - 35  # Moved further from edge for better visibility
    bar_y_start = 100  # Moved down to avoid overlapping with controls
    bar_height = 300  # Increased height for better precision
    bar_width = 20  # Increased width

    # Draw background bar
    cv2.rectangle(img, (bar_x, bar_y_start), (bar_x + bar_width, bar_y_start + bar_height),
                  (60, 60, 60), -1)

    # Draw deadzone area (40-60% range)
    deadzone_start = int((scroll_deadzone_min / 100) * bar_height)
    deadzone_end = int((scroll_deadzone_max / 100) * bar_height)
    cv2.rectangle(img, (bar_x, bar_y_start + deadzone_start),
                  (bar_x + bar_width, bar_y_start + deadzone_end),
                  (0, 100, 100), -1)  # Dark yellow for deadzone

    # Draw border
    cv2.rectangle(img, (bar_x, bar_y_start), (bar_x + bar_width, bar_y_start + bar_height),
                  (255, 255, 255), 2)

    # Draw current position indicator
    pos_height = int((scroll_pos / 100) * bar_height)
    indicator_size = 15
    cv2.rectangle(img, (bar_x - 2, bar_y_start + pos_height - indicator_size // 2),
                  (bar_x + bar_width + 2, bar_y_start + pos_height + indicator_size // 2),
                  (0, 255, 0), -1)

    # Add percentage text
    cv2.putText(img, f"{int(scroll_pos)}%", (bar_x - 45, bar_y_start + pos_height + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Add deadzone label
    cv2.putText(img, "DEAD", (bar_x - 45, bar_y_start + deadzone_start + 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 150, 150), 1)
    cv2.putText(img, "ZONE", (bar_x - 45, bar_y_start + deadzone_start + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 150, 150), 1)


def draw_controls_guide(img):
    """Draw enhanced controls guide with better visibility"""
    # Create semi-transparent overlay - positioned to not interfere with detection area
    overlay = img.copy()

    # Background rectangle for better text visibility (moved position)
    cv2.rectangle(overlay, (5, 5), (350, 220), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)

    # Title
    cv2.putText(img, "ENHANCED HAND GESTURE CONTROLS", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # Control instructions with color coding
    controls = [
        ("Index Finger: Move Cursor", (0, 255, 255)),  # Yellow
        ("Index + Middle VERY Close: Left Click", (0, 255, 0)),  # Green
        ("Thumb + Middle Close: Right Click", (0, 100, 255)),  # Orange
        ("Index + Middle + Ring: Double Click", (255, 0, 255)),  # Magenta
        ("Index + Middle MEDIUM: Smart Scroll", (100, 255, 100)),  # Light Green
        ("  - Deadzone (40-60%): No Movement", (0, 150, 150)),  # Dark Cyan
        ("  - <40%: Scroll UP (faster near 0%)", (100, 255, 100)),
        ("  - >60%: Scroll DOWN (faster near 100%)", (100, 255, 100)),
        ("Index + Thumb: Drag & Drop", (255, 255, 0)),  # Cyan
        ("Press 'q' to Quit", (255, 255, 255))  # White
    ]

    y_offset = 45
    for i, (text, color) in enumerate(controls):
        cv2.putText(img, text, (10, y_offset + i * 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)


def log_action(action, details=""):
    """Log actions with timestamp"""
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    print(f"[{timestamp}] {action} {details}")


def perform_smart_scroll(scroll_position):
    """Perform smart scroll with deadzone and variable speed"""
    global last_scroll_time

    current_time = time.time()

    # Check if we're in the deadzone
    if scroll_deadzone_min <= scroll_position <= scroll_deadzone_max:
        return "deadzone"  # No scrolling in deadzone

    # Calculate scroll speed based on distance from deadzone
    if scroll_position < scroll_deadzone_min:  # Scroll UP
        # Distance from deadzone determines speed (0% = fastest, 40% = slowest)
        distance_from_center = scroll_deadzone_min - scroll_position
        scroll_speed = max(2, int(distance_from_center*5))  # 1-4 scroll units

        try:
            pyautogui.scroll(scroll_speed)
            log_action("SCROLL UP", f"Speed: {scroll_speed}, Pos: {scroll_position:.1f}%")
            return "up"
        except Exception as e:
            log_action("SCROLL ERROR", str(e))

    elif scroll_position > scroll_deadzone_max:  # Scroll DOWN
        # Distance from deadzone determines speed (60% = slowest, 100% = fastest)
        distance_from_center = scroll_position - scroll_deadzone_max
        scroll_speed = max(2, int(distance_from_center*5))  # 1-4 scroll units

        try:
            pyautogui.scroll(-scroll_speed)
            log_action("SCROLL DOWN", f"Speed: {scroll_speed}, Pos: {scroll_position:.1f}%")
            return "down"
        except Exception as e:
            log_action("SCROLL ERROR", str(e))

    return "none"


# Main loop
while True:
    success, img = cap.read()
    if not success:
        print("Failed to grab frame")
        break

    # Flip image horizontally for mirror effect
    img = cv2.flip(img, 1)
    img = detector.findHands(img)
    lmList, bbox = detector.findPosition(img)

    current_time = time.time()

    # Draw the active region (frame reduction) - MOVED UP for better bottom corner access
    cv2.rectangle(img, (frameR, frameR_top), (wCam - frameR, hCam - frameR),
                  (255, 0, 255), 2)

    # Add text to show the improved detection area
    cv2.putText(img, "DETECTION AREA (Moved Up)", (frameR + 5, frameR_top + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

    if len(lmList) != 0:
        # Get finger tip coordinates
        thumb_tip = lmList[4][1:]  # Thumb tip
        index_tip = lmList[8][1:]  # Index finger tip
        middle_tip = lmList[12][1:]  # Middle finger tip
        ring_tip = lmList[16][1:]  # Ring finger tip

        # Check which fingers are up
        fingers = detector.fingersUp()

        # Calculate distances between fingers
        thumb_middle_dist = calculate_distance(thumb_tip, middle_tip)
        index_middle_dist = calculate_distance(index_tip, middle_tip)
        index_ring_dist = calculate_distance(index_tip, ring_tip)
        middle_ring_dist = calculate_distance(middle_tip, ring_tip)
        thumb_index_dist = calculate_distance(thumb_tip, index_tip)

        # 1. CURSOR MOVEMENT - Index finger only
        if fingers[1] == 1 and fingers[2] == 0 and fingers[0] == 0:
            # Convert coordinates with adjusted frame boundaries
            x3 = np.interp(index_tip[0], (frameR, wCam - frameR), (0, wScr))
            y3 = np.interp(index_tip[1], (frameR_top, hCam - frameR), (0, hScr))

            # Smoothen values
            clocX = plocX + (x3 - plocX) / smoothening
            clocY = plocY + (y3 - plocY) / smoothening

            # Move mouse
            autopy.mouse.move(clocX, clocY)

            # Visual feedback
            cv2.circle(img, index_tip, 15, (0, 255, 255), cv2.FILLED)
            cv2.putText(img, "MOVE", (index_tip[0] + 20, index_tip[1] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            plocX, plocY = clocX, clocY
            scroll_active = False

        # 2. LEFT CLICK - Index + Middle finger very close (primary click)
        elif (fingers[1] == 1 and fingers[2] == 1 and fingers[0] == 0 and fingers[3] == 0 and
              index_middle_dist < 25):  # Very close for left click
            if current_time - last_left_click > click_cooldown:
                autopy.mouse.click(autopy.mouse.Button.LEFT)
                last_left_click = current_time
                log_action("LEFT CLICK")

            # Visual feedback
            cv2.circle(img, index_tip, 15, (0, 255, 0), cv2.FILLED)
            cv2.circle(img, middle_tip, 15, (0, 255, 0), cv2.FILLED)
            cv2.line(img, index_tip, middle_tip, (0, 255, 0), 3)
            cv2.putText(img, "LEFT CLICK", (index_tip[0] - 50, index_tip[1] - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # 3. RIGHT CLICK - Thumb + Middle finger close
        elif fingers[0] == 1 and fingers[2] == 1 and thumb_middle_dist < 40:
            if current_time - last_right_click > click_cooldown:
                autopy.mouse.click(autopy.mouse.Button.RIGHT)
                last_right_click = current_time
                log_action("RIGHT CLICK")

            # Visual feedback
            cv2.circle(img, thumb_tip, 15, (0, 100, 255), cv2.FILLED)
            cv2.circle(img, middle_tip, 15, (0, 100, 255), cv2.FILLED)
            cv2.line(img, thumb_tip, middle_tip, (0, 100, 255), 3)
            cv2.putText(img, "RIGHT CLICK", (thumb_tip[0] - 50, thumb_tip[1] - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 100, 255), 2)

        # 4. DOUBLE CLICK - Index + Middle + Ring close together
        elif (fingers[1] == 1 and fingers[2] == 1 and fingers[3] == 1 and
              index_middle_dist < 30 and index_ring_dist < 30 and middle_ring_dist < 30):

            if current_time - last_double_click > click_cooldown:
                autopy.mouse.click(autopy.mouse.Button.LEFT)
                time.sleep(0.1)  # Small delay between clicks
                autopy.mouse.click(autopy.mouse.Button.LEFT)
                last_double_click = current_time
                log_action("DOUBLE CLICK")

            # Visual feedback
            cv2.circle(img, index_tip, 12, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, middle_tip, 12, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, ring_tip, 12, (255, 0, 255), cv2.FILLED)
            cv2.putText(img, "DOUBLE CLICK", (index_tip[0] - 60, index_tip[1] - 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)

        # 5. SMART SCROLL MODE - Index + Middle moderately close with deadzone control
        elif (fingers[1] == 1 and fingers[2] == 1 and fingers[0] == 0 and fingers[3] == 0 and
              35 < index_middle_dist < scroll_threshold):  # Medium distance for scroll

            # Calculate scroll position based on hand Y position
            hand_center_y = (index_tip[1] + middle_tip[1]) // 2
            # Map hand Y position to scroll percentage (0-100)
            scroll_position = np.interp(hand_center_y, (frameR_top, hCam - frameR), (0, 100))
            scroll_position = max(0, min(100, scroll_position))  # Clamp to 0-100

            # Perform smart scroll with deadzone
            scroll_result = perform_smart_scroll(scroll_position)

            # Visual feedback for scroll mode
            cv2.circle(img, index_tip, 15, (100, 255, 100), cv2.FILLED)
            cv2.circle(img, middle_tip, 15, (100, 255, 100), cv2.FILLED)
            cv2.line(img, index_tip, middle_tip, (100, 255, 100), 3)

            # Show scroll status
            if scroll_result == "deadzone":
                cv2.putText(img, "SCROLL DEADZONE", (index_tip[0] - 70, index_tip[1] - 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 150, 150), 2)
                cv2.putText(img, "NO MOVEMENT", (index_tip[0] - 60, index_tip[1] - 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 150, 150), 1)
            elif scroll_result == "up":
                cv2.putText(img, "SCROLL UP", (index_tip[0] - 50, index_tip[1] - 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 255, 100), 2)
            elif scroll_result == "down":
                cv2.putText(img, "SCROLL DOWN", (index_tip[0] - 60, index_tip[1] - 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 255, 100), 2)

            # Show position info
            cv2.putText(img, f"Pos: {scroll_position:.1f}%", (index_tip[0] - 50, index_tip[1] - 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            scroll_active = True

        # 6. ENHANCED DRAG MODE - Index + Thumb close (for drag and drop)
        elif fingers[1] == 1 and fingers[0] == 1 and thumb_index_dist < 35:
            if not drag_active:
                # Start drag - press and hold left mouse button
                drag_active = True
                drag_start_pos = (index_tip[0], index_tip[1])
                # Note: autopy doesn't support holding mouse button, so we simulate with rapid clicks
                # For proper drag functionality, you'd need a different library like pynput
                log_action("DRAG STARTED", f"At: {drag_start_pos}")

            # Visual feedback for active drag mode
            cv2.circle(img, index_tip, 18, (255, 255, 0), cv2.FILLED)
            cv2.circle(img, thumb_tip, 18, (255, 255, 0), cv2.FILLED)
            cv2.line(img, index_tip, thumb_tip, (255, 255, 0), 4)

            # Draw drag trail if we have a start position
            if drag_start_pos:
                cv2.line(img, drag_start_pos, index_tip, (255, 255, 0), 2)
                cv2.putText(img, "DRAGGING", (index_tip[0] - 50, index_tip[1] - 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

                # Move cursor while dragging
                x3 = np.interp(index_tip[0], (frameR, wCam - frameR), (0, wScr))
                y3 = np.interp(index_tip[1], (frameR_top, hCam - frameR), (0, hScr))
                autopy.mouse.move(x3, y3)
            else:
                cv2.putText(img, "DRAG READY", (index_tip[0] - 60, index_tip[1] - 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        else:
            # Reset drag mode when gesture is released
            if drag_active:
                drag_active = False
                drag_start_pos = None
                log_action("DRAG ENDED")

            scroll_active = False

        # Additional visual feedback for finger detection (moved to bottom right)
        for i, finger_up in enumerate(fingers):
            color = (0, 255, 0) if finger_up else (0, 0, 255)
            cv2.putText(img, str(finger_up), (wCam - 150 + i * 25, hCam - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    else:
        scroll_active = False
        if drag_active:
            drag_active = False
            drag_start_pos = None
            log_action("DRAG ENDED - Hand Lost")

    # Draw enhanced scroll bar with deadzone
    if scroll_active:
        # Update scroll position based on current hand position
        if len(lmList) != 0:
            hand_center_y = (lmList[8][2] + lmList[12][2]) // 2  # Index + Middle Y
            scroll_position = np.interp(hand_center_y, (frameR_top, hCam - frameR), (0, 100))
            scroll_position = max(0, min(100, scroll_position))

    draw_scroll_bar(img, scroll_position)

    # Draw enhanced controls guide
    draw_controls_guide(img)

    # Calculate and display FPS
    cTime = time.time()
    if cTime - pTime != 0:
        fps = 1 / (cTime - pTime)
    else:
        fps = 0
    pTime = cTime

    cv2.putText(img, f'FPS: {int(fps)}', (wCam - 120, 30),
                cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 2)

    # Display the image
    cv2.imshow("Enhanced Virtual Mouse with Smart Scroll", img)

    # Break loop on 'q' press
    if cv2.waitKey(1) & 0xFF == ord('q'):
        log_action("ENHANCED VIRTUAL MOUSE STOPPED")
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()
