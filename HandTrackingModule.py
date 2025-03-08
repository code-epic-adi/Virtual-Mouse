import mediapipe as mp
import cv2
import time
import math


# Define a class to detect hands
class handDetector():
    def __init__(self, mode=False, maxHands=2, detection_confidence=0.5, tracking_confidence=0.5):
        # Initialize the hand detector with the given parameters
        self.mode = mode
        self.maxHands = maxHands
        self.detection_confidence = detection_confidence
        self.tracking_confidence = tracking_confidence

        # Initialize mediapipe hands solution
        self.mpHands = mp.solutions.hands
        self.hands = self.mpHands.Hands(
            static_image_mode=self.mode,
            max_num_hands=self.maxHands,
            min_detection_confidence=self.detection_confidence,
            min_tracking_confidence=self.tracking_confidence
        )
        self.mpDraw = mp.solutions.drawing_utils  # Utility to draw hand landmarks

        self.tipIds = [8, 12, 16, 20]

    # Method to find hands in the image
    def findHands(self, img, draw=True):
        # Convert the image to RGB
        iRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.results = self.hands.process(iRGB)  # Process the image to find hands

        # If hands are detected, draw landmarks on the image
        if self.results.multi_hand_landmarks:
            for handLms in self.results.multi_hand_landmarks:
                if draw:
                    self.mpDraw.draw_landmarks(img, handLms, self.mpHands.HAND_CONNECTIONS)

        return img

    # Method to find the position of specific landmarks
    def findPosition(self, img, handNo=0, draw=True):
        xList = []
        yList = []
        bbox = []
        self.lmList = []
        if self.results.multi_hand_landmarks:
            myHand = self.results.multi_hand_landmarks[handNo]
            for id, lm in enumerate(myHand.landmark):
                # print(id, lm)
                h, w, c = img.shape
                cx, cy = int(lm.x * w), int(lm.y * h)
                xList.append(cx)
                yList.append(cy)
                # print(id, cx, cy)
                self.lmList.append([id, cx, cy])
                if draw:
                    cv2.circle(img, (cx, cy), 5, (255, 0, 255), cv2.FILLED)

        if len(xList) & len(yList):
            xmin, xmax = min(xList), max(xList)
            ymin, ymax = min(yList), max(yList)
            bbox = xmin, ymin, xmax, ymax

            if draw:
                cv2.rectangle(img, (xmin - 20, ymin - 20), (xmax + 20, ymax + 20),
                              (0, 255, 0), 2)

        return self.lmList, bbox

    def fingersUp(self):
        fingers = []

        if self.lmList[4][1] > self.lmList[5][1]:
            fingers.append(1)
        else:
            fingers.append(0)

        for id in range(0, 4):
            if self.lmList[self.tipIds[id]][2] < self.lmList[self.tipIds[id] - 2][2]:
                fingers.append(1)

            else:
                fingers.append(0)

        return fingers

    def findDistance(self, p1, p2, img, draw=True, r=15, t=3):
        x1, y1 = self.lmList[p1][1:]
        x2, y2 = self.lmList[p2][1:]
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        if draw:
            cv2.line(img, (x1, y1), (x2, y2), (255, 0, 255), t)
            cv2.circle(img, (x1, y1), r, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (x2, y2), r, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (cx, cy), r, (0, 0, 255), cv2.FILLED)
            length = math.hypot(x2 - x1, y2 - y1)

        return length, img, [x1, y1, x2, y2, cx, cy]


# Main function to run the hand detection
def main():
    pTime = 0  # Previous time to calculate FPS
    cap = cv2.VideoCapture(0)  # Capture video from the default camera
    detector = handDetector()  # Create an instance of the handDetector

    while True:
        success, img = cap.read()  # Read a frame from the camera
        img = detector.findHands(img)  # Find hands in the image
        lmList = detector.findPosition(img)  # Find the positions of the landmarks

        cTime = time.time()  # Current time
        fps = 1 / (cTime - pTime)  # Calculate FPS
        pTime = cTime  # Update previous time

        # Display FPS on the image
        cv2.putText(img, str(int(fps)), (10, 70), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 2)

        # Show the image with landmarks
        cv2.imshow("Output", img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break  # Break the loop if 'q' is pressed

    cap.release()  # Release the camera
    cv2.destroyAllWindows()  # Close all OpenCV windows


# Entry point of the script
if __name__ == "__main__":
    main()  # Run the main function
