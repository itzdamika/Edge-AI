import cv2
import numpy as np
import tflite_runtime.interpreter as tflite
import time

# Load labels (adjust path as needed)
with open('labels.txt', 'r') as f:
    labels = [line.strip() for line in f.readlines()]

interpreter = tflite.Interpreter(model_path="best_float16.tflite")
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

input_shape = input_details[0]['shape'][1:3]  

cap = cv2.VideoCapture(0)

last_state = None

try:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Failed to capture frame.")
            break

        height, width, _ = frame.shape

        resized = cv2.resize(frame, tuple(input_shape))
        input_tensor = resized.astype(np.float32) / 255.0  
        input_tensor = np.expand_dims(input_tensor, axis=0)  

        interpreter.set_tensor(input_details[0]['index'], input_tensor)
        interpreter.invoke()

        output_data = interpreter.get_tensor(output_details[0]['index'])[0]

        boxes = output_data[:4]    
        confs = output_data[4]      

        person_detected = False

        for i in range(confs.shape[0]):
            confidence = confs[i]

            if confidence > 0.5:  
                class_id = 0 
                if len(output_details) > 1:
                    class_id = int(np.argmax(interpreter.get_tensor(output_details[1]['index'])[0][i]))

                if labels[class_id].lower() == 'person':
                    person_detected = True
                    break

        if person_detected != last_state:
            timestamp = time.strftime('%H:%M:%S')
            if person_detected:
                print(f"[{timestamp}] Person detected.")
            else:
                print(f"[{timestamp}] No person detected.")
            last_state = person_detected

        time.sleep(0.1)  

except KeyboardInterrupt:
    print("Detection stopped by user.")

finally:
    cap.release()
