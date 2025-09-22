# backend/action_recognizer.py
import numpy as np

class SimpleActionClassifier:
    """
    Простейший rule-based классификатор на основе позы MediaPipe.
    Ожидает landmarks как np.array shape (N,3) с normalized coords.
    Выдаёт строку: "standing", "moving", "fall"
    """
    def __init__(self):
        # параметры порогов можно тонко настроить потом
        self.fall_angle_thresh = 50  # градусы
        self.movement_speed_thresh = 0.02  # norm coords/frame

        # для вычисления скорости — хранит предыдущие когорты ключевых точек
        self._prev_centroid = None

    def compute_centroid(self, landmarks):
        # берем среднее по видимым точкам (x,y)
        pts = landmarks[:, :2]
        return np.nanmean(pts, axis=0)

    def predict(self, landmarks):
        """
        landmarks: np.ndarray shape (num_landmarks, 3) or None
        """
        if landmarks is None:
            return "no_person"

        # используем плечо(11)/hip(23) и нос(0) для оценки торса
        try:
            left_sh = landmarks[11][:2]
            left_hip = landmarks[23][:2]
            nose = landmarks[0][:2]
        except Exception:
            return "unknown"

        # угол между вектором (hip -> shoulder) и горизонталью
        dx = left_sh[0] - left_hip[0]
        dy = left_sh[1] - left_hip[1]
        angle = abs(np.degrees(np.arctan2(dy, dx)))  # в градусах

        centroid = self.compute_centroid(landmarks)
        movement = 0.0
        if self._prev_centroid is not None:
            movement = np.linalg.norm(centroid - self._prev_centroid)
        self._prev_centroid = centroid

        # простая логика:
        if angle > self.fall_angle_thresh:
            return "fall"
        if movement > self.movement_speed_thresh:
            return "moving"
        return "standing"
