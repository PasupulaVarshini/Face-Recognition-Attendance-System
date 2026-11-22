
const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const capturedImage = document.getElementById("captured-image");
const statusText = document.getElementById("camera-status");

const startButton = document.getElementById("start-camera");
const captureButton = document.getElementById("capture-face");
const retakeButton = document.getElementById("retake-face");

let cameraStream = null;

startButton.addEventListener("click", async () => {
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: "user"
            },
            audio: false
        });

        video.srcObject = cameraStream;
        video.hidden = false;
        capturedImage.hidden = true;

        statusText.textContent = "Camera started successfully.";
    } catch (error) {
        statusText.textContent =
            "Unable to access camera. Please allow camera permission.";
    }
});

captureButton.addEventListener("click", () => {
    if (!cameraStream) {
        statusText.textContent = "Please start the camera first.";
        return;
    }

    if (video.readyState < 2) {
        statusText.textContent = "Camera is not ready yet.";
        return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const context = canvas.getContext("2d");

    context.drawImage(
        video,
        0,
        0,
        canvas.width,
        canvas.height
    );

    capturedImage.src = canvas.toDataURL("image/jpeg", 0.9);

    document.getElementById("face_image").value =
        capturedImage.src;

    capturedImage.hidden = false;
    video.hidden = true;

    statusText.textContent = "Face captured successfully.";
});

retakeButton.addEventListener("click", () => {
    if (!cameraStream) {
        statusText.textContent = "Please start the camera first.";
        return;
    }

    document.getElementById("face_image").value = "";

    capturedImage.hidden = true;
    video.hidden = false;

    statusText.textContent = "You can capture your face again.";
});