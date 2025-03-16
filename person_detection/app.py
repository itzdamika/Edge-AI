import cv2
import torch
import numpy as np

# If you have the SimpleDetectionCNN class and detection_loss from your training code,
# import them or define them here. For brevity, we assume they're already defined/imported.

# ---------------------------
# 2. Define a Simple CNN Model (no final sigmoid)
# ---------------------------
class SimpleDetectionCNN(nn.Module):
    def __init__(self):
        super(SimpleDetectionCNN, self).__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1))
        )
        self.fc = nn.Linear(64, 5)

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)
        return x

def run_realtime_inference(model_path,
                           input_size=(320, 320),
                           threshold=0.5):
    """
    Runs real-time person detection using a webcam feed.

    Args:
        model_path (str): Path to the trained model's .pth or .pt file.
        input_size (tuple): (width, height) to resize each frame.
        threshold (float): Objectness threshold for displaying a detection.
    """

    # 1. Set up the device and load your trained model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SimpleDetectionCNN()  # Instantiate the same architecture you trained
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device)
    model.eval()

    # 2. Initialize webcam (0 = default camera)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam.")
        return

    print("Press 'q' to quit the real-time inference window.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Original image size
        orig_h, orig_w = frame.shape[:2]

        # 3. Preprocess the frame
        #    a) Resize to the model's input size
        resized_frame = cv2.resize(frame, input_size)
        #    b) Convert to float32 and normalize to [0,1]
        resized_frame = resized_frame.astype(np.float32) / 255.0
        #    c) Convert from (H,W,C) to (C,H,W), add batch dimension
        input_tensor = torch.from_numpy(resized_frame.transpose(2, 0, 1)).unsqueeze(0).to(device)

        # 4. Forward pass (inference)
        with torch.no_grad():
            # If you want to use mixed precision, wrap in autocast (optional):
            # with torch.cuda.amp.autocast():
            outputs = model(input_tensor)  # shape: [1, 5]

        # 5. Postprocess the outputs
        #    a) BBox coords in [0,1], so apply sigmoid to the first 4
        bbox_pred = torch.sigmoid(outputs[0, :4]).cpu().numpy()  # x_center, y_center, w, h
        #    b) Objectness is raw logit; apply sigmoid to get confidence
        obj_conf = torch.sigmoid(outputs[0, 4]).item()

        # 6. If confidence > threshold, draw the predicted bounding box
        if obj_conf > threshold:
            x_center, y_center, box_w, box_h = bbox_pred
            # Convert normalized coords to pixel coords
            x1 = int((x_center - box_w / 2) * orig_w)
            y1 = int((y_center - box_h / 2) * orig_h)
            x2 = int((x_center + box_w / 2) * orig_w)
            y2 = int((y_center + box_h / 2) * orig_h)

            # Draw the box in green
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"Person: {obj_conf:.2f}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # 7. Show the frame
        cv2.imshow("Real-Time Person Detection", frame)

        # 8. Quit on 'q' key
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # 9. Clean up
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    # Example usage:
    # Make sure 'model_path' is the path to your saved weights file (e.g. "best_model.pth")
    model_path = "person_detection_model.pt"
    run_realtime_inference(model_path, input_size=(320, 320), threshold=0.5)
