import cv2
import numpy as np
import onnxruntime as ort

# Load ONNX model
session = ort.InferenceSession("yolo11n_int8.onnx")
input_name = session.get_inputs()[0].name
input_shape = session.get_inputs()[0].shape
input_height, input_width = input_shape[2], input_shape[3]

# Load labels
with open('labels.txt', 'r') as f:
    labels = [line.strip() for line in f.readlines()]

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    orig_h, orig_w, _ = frame.shape

    # Preprocess image
    img = cv2.resize(frame, (input_width, input_height))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.transpose(2, 0, 1)  
    img = img.astype(np.float32) / 255.0
    img = np.expand_dims(img, axis=0)

    # Run inference
    outputs = session.run(None, {input_name: img})

    predictions = outputs[0] 

    for pred in predictions:
        x1, y1, x2, y2, score, cls_id = pred
        if score < 0.5:
            continue

        x1 = int(x1 * orig_w)
        y1 = int(y1 * orig_h)
        x2 = int(x2 * orig_w)
        y2 = int(y2 * orig_h)

        label = f"{labels[int(cls_id)]} {score:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, label, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    cv2.imshow("YOLOv11n - ONNX Inference", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
