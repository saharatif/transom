import os

import cv2


def safe_output_path(image_path: str) -> str:
    """Path of the sanitized copy blur_faces_and_plates() writes for a
    given input (photo.jpg -> photo_safe.jpg). splitext, not
    str.replace(".", ...) — a filename or directory with extra dots
    ("kitchen.v2.jpg") would otherwise produce a broken path.
    """
    root, ext = os.path.splitext(image_path)
    return f"{root}_safe{ext}"


def blur_faces_and_plates(image_path: str) -> str:
    """Blur any detected faces in the image and write a sanitized copy
    alongside the original (photo.jpg -> photo_safe.jpg). This runs BEFORE
    the image is sent to any external API — Presidio only redacts text, so
    visual PII has to be handled here.
    """
    img = cv2.imread(image_path)
    if img is None:
        # cv2.imread returns None (no exception) for missing/corrupt/
        # unsupported files — fail here with a clear message instead of an
        # opaque OpenCV assertion later in detectMultiScale.
        raise ValueError(f"Could not read image file: {image_path}")

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(img, 1.1, 4)
    for (x, y, w, h) in faces:
        img[y:y+h, x:x+w] = cv2.GaussianBlur(img[y:y+h, x:x+w], (99, 99), 30)

    out_path = safe_output_path(image_path)
    if not cv2.imwrite(out_path, img):
        raise IOError(f"Could not write sanitized image: {out_path}")
    return out_path
