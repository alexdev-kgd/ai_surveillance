import cv2
import mediapipe as mp

def analyze_video_file(path: str):
    mp_pose = mp.solutions.pose
    total_frames, frames_with_people = 0, 0

    with mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        cap = cv2.VideoCapture(path)
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            total_frames += 1
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(frame_rgb)
            if results.pose_landmarks:
                frames_with_people += 1
        cap.release()

    return {
        "total_frames": total_frames,
        "frames_with_people": frames_with_people,
        "people_percent": round(frames_with_people / total_frames * 100, 2) if total_frames > 0 else 0
    }
