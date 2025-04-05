import cv2
import numpy as np
import tflite_runtime.interpreter as tflite

# Load labels
with open('labels.txt', 'r') as f:
    labels = [line.strip() for line in f.readlines()]

# Load model
interpreter = tflite.Interpreter(model_path="yolov11-nano.tflite")
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
input_shape = input_details[0]['shape'][1:3]  # height, width

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    height, width, _ = frame.shape

    # Preprocess image
    input_img = cv2.resize(frame, tuple(input_shape))
    input_img = input_img.astype(np.float32) / 255.0
    input_img = np.expand_dims(input_img, axis=0)

    # Run inference
    interpreter.set_tensor(input_details[0]['index'], input_img)
    interpreter.invoke()

    # Extract outputs
    boxes = interpreter.get_tensor(output_details[0]['index'])[0]
    classes = interpreter.get_tensor(output_details[1]['index'])[0]
    scores = interpreter.get_tensor(output_details[2]['index'])[0]

    # Draw detections
    for i in range(len(scores)):
        if scores[i] > 0.5:
            ymin, xmin, ymax, xmax = boxes[i]
            class_id = int(classes[i])
            label = labels[class_id]

            # Convert box to pixel coordinates
            (left, top, right, bottom) = (
                int(xmin * width),
                int(ymin * height),
                int(xmax * width),
                int(ymax * height),
            )

            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, f"{label} {scores[i]:.2f}", (left, top - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    cv2.imshow("YOLOv11 Nano - Persona Detection", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()