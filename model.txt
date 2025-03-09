# Face Recognition System

## Face Detection
- The system uses MTCNN (Multi-task Cascaded Convolutional Networks) to detect faces in real-time from the webcam feed.
- It draws bounding boxes around the detected faces.

## Face Embedding
- When a face is detected, it is cropped and resized to 160x160 pixels, the required input size for InceptionResnetV1.
- The cropped face is converted to a tensor and normalized to the range [-1, 1] as expected by the model.

## Face Recognition
- The cropped face is passed through the InceptionResnetV1 model, which outputs a face embedding (a numerical representation of the face).
- This embedding is compared with a previously saved face embedding using cosine similarity.
- If the cosine distance between the embeddings is below a predefined threshold, the face is recognized as the saved user (e.g., "Gaindu"). Otherwise, the face is marked as "Unknown".

## Saving the Face Embedding
- If desired, the user can save their face embedding for future recognition using the command:
  ```python
  torch.save(embedding, 'face_embeddings/my_face_embeddings.pth')
  ```

## Features
- **Real-time Face Recognition**: The system continuously captures webcam footage and identifies the user in real time.
- **Threshold-based Recognition**: The system uses a cosine similarity threshold (threshold = 0.6) to determine whether the detected face matches the saved face.

## Requirements
- Python 3.x
- torch
- opencv-python
- facenet-pytorch
- scipy
- torchvision
