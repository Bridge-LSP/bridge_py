import cv2
import mediapipe as mp
from hand_tracker import create_hand_landmarker
from visualizer import draw_landmarks, draw_connections, draw_handedness_label
from config import CAMERA_WIDTH, CAMERA_HEIGHT

def main():
    hand_landmarker = create_hand_landmarker()
    cap = cv2.VideoCapture(0)
    cap.set(3, CAMERA_WIDTH)
    cap.set(4, CAMERA_HEIGHT)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
        timestamp_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))
        results = hand_landmarker.detect_for_video(mp_image, timestamp_ms)

        if results.hand_landmarks:
            for idx, landmarks in enumerate(results.hand_landmarks):
                draw_landmarks(frame, landmarks, frame.shape[1], frame.shape[0])
                draw_connections(frame, landmarks, frame.shape[1], frame.shape[0])
                handedness = results.handedness[idx][0].category_name
                draw_handedness_label(frame, handedness, idx)
                world_landmarks = results.hand_world_landmarks[idx]
                for i, lm in enumerate(world_landmarks):
                    print(f'Hand {idx + 1} ({handedness}) - Landmark {i}: x={lm.x:.4f}, y={lm.y:.4f}, z={lm.z:.4f}')

        cv2.imshow("Hand Tracking Live", frame)
        if cv2.waitKey(5) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()