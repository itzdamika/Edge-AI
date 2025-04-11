import cv2
import numpy as np
import tflite_runtime.interpreter as tflite

# Load labels
with open('labels.txt', 'r') as f:
    labels = [line.strip() for line in f.readlines()]

# Load model
interpreter = tflite.Interpreter(model_path="best_float16.tflite")
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
input_shape = input_details[0]['shape'][1:3] 

print("Output details:")
for i, detail in enumerate(output_details):
    print(f"Output{i}:{detail}")

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    height, width, _ = frame.shape

    # Preprocess input image
    resized = cv2.resize(frame, tuple(input_shape))
    input_tensor = resized.astype(np.float32) / 255.0 
    input_tensor = np.expand_dims(input_tensor, axis=0)  

    # Run inference
    interpreter.set_tensor(input_details[0]['index'], input_tensor)
    interpreter.invoke()

    output_data = interpreter.get_tensor(output_details[0]['index'])[0]  

    boxes = output_data[:4]  
    confs = output_data[4]    

    for i in range(confs.shape[0]):
        confidence = confs[i]
        if confidence > 0.5:
            cx, cy, w, h = boxes[0][i], boxes[1][i], boxes[2][i], boxes[3][i]

            # Convert to pixel coordinates
            x1 = int((cx - w / 2) * width)
            y1 = int((cy - h / 2) * height)
            x2 = int((cx + w / 2) * width)
            y2 = int((cy + h / 2) * height)

            # Draw bounding box and label
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{labels[0]} {confidence:.2f}"
            cv2.putText(frame, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Show output
    cv2.imshow("YOLOv11 Nano - Persona Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()