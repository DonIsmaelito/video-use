The unmodified 232589-byte `face_detection_yunet_2023mar.onnx` model and its
MIT notice come from OpenCV Zoo commit
`f12e12798e8314f7c074a6656816c048dcc95b7a`:

https://github.com/opencv/opencv_zoo/tree/f12e12798e8314f7c074a6656816c048dcc95b7a/models/face_detection_yunet

Model SHA256: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`.
License SHA256: `c83b8120c50ccbd4c4f96edf53141bdd566ebb8f8e9227e415326aa1b1aba958`.

This model works with the existing OpenCV 4.x `FaceDetectorYN` API. The newer
OpenCV Zoo dynamic-shape export targets OpenCV 5.x; this project intentionally
pins the tested 4.x model instead of silently upgrading the computer-vision
runtime. Detection locates visible face boxes. It does not identify people,
detect active speakers, segment hair, or guarantee tracking through occlusion.
