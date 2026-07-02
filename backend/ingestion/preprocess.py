import cv2

def blur_faces_and_plates(image_path: str) -> str:
    img = cv2.imread(image_path)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(img, 1.1, 4)
    for (x, y, w, h) in faces:
        img[y:y+h, x:x+w] = cv2.GaussianBlur(img[y:y+h, x:x+w], (99, 99), 30)
    out_path = image_path.replace(".", "_safe.")
    cv2.imwrite(out_path, img)
    return out_path
