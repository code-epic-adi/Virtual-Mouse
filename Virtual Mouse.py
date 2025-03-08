import cv2
import numpy as np
import HandTrackingModule as htm
import time
import autopy

# Parameters
wCam, hCam = 640, 480
frameR = 100  # Frame Reduction
smoothening = 7

pTime = 0
plocX, plocY = 0, 0
clocX, clocY = 0, 0

# Set up the webcam (try using index 0 if 1 doesn't work)
cap = cv2.VideoCapture(0)
cap.set(3, wCam)
cap.set(4, hCam)

# Initialize the hand detector (from your HandTrackingModule)
detector = htm.handDetector(maxHands=1)
wScr, hScr = autopy.screen.size()
print("Screen size:", wScr, hScr)

while True:
    # 1. Read a frame from the webcam and find hands
    success, img = cap.read()
    if not success:
        print("Failed to grab frame")
        break
    img = detector.findHands(img)
    lmList, bbox = detector.findPosition(img)

    # 2. Proceed if landmarks are detected
    if len(lmList) != 0:
        # Get coordinates of index finger tip (landmark 8) and middle finger tip (landmark 12)
        x1, y1 = lmList[8][1:]
        x2, y2 = lmList[12][1:]

        # 3. Check which fingers are up
        fingers = detector.fingersUp()
        # Debug print: Uncomment the next line to see finger values
        # print("Fingers:", fingers)

        # Draw the active region (frame reduction)
        cv2.rectangle(img, (frameR, frameR), (wCam - frameR, hCam - frameR),
                      (255, 0, 255), 2)

        # 4. Moving Mode: Only the index finger is up
        if fingers[1] == 1 and fingers[2] == 0:
            # 5. Convert coordinates: Map the index finger tip position from camera coords to screen coords
            x3 = np.interp(x1, (frameR, wCam - frameR), (0, wScr))
            y3 = np.interp(y1, (frameR, hCam - frameR), (0, hScr))

            # 6. Smoothen values to reduce jitter
            clocX = plocX + (x3 - plocX) / smoothening
            clocY = plocY + (y3 - plocY) / smoothening

            # 7. Move Mouse:
            # You may need to switch between these two options:
            # Option A (flipped x-coordinate, common if the webcam feed is mirrored):
            autopy.mouse.move(wScr - clocX, clocY)
            # Option B (direct mapping):
            # autopy.mouse.move(clocX, clocY)

            # Visual feedback for index finger
            cv2.circle(img, (x1, y1), 15, (255, 0, 255), cv2.FILLED)
            plocX, plocY = clocX, clocY

        # 8. Clicking Mode: Both index and middle fingers are up
        if fingers[1] == 1 and fingers[2] == 1:
            # 9. Measure the distance between index and middle finger
            length, img, lineInfo = detector.findDistance(8, 12, img)
            # Debug print: Uncomment to see the distance value
            # print("Distance between fingers:", length)
            # 10. If the distance is short, trigger a click
            if length < 40:
                cv2.circle(img, (lineInfo[4], lineInfo[5]), 15, (0, 255, 0), cv2.FILLED)
                autopy.mouse.click()

    # 11. Calculate and display FPS
    cTime = time.time()
    if cTime - pTime != 0:
        fps = 1 / (cTime - pTime)
    else:
        fps = 0
    pTime = cTime
    cv2.putText(img, f'FPS: {int(fps)}', (20, 50),
                cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)

    # 12. Display the image
    cv2.imshow("Image", img)
    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
