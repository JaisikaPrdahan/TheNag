"""
Image preprocessing to improve OCR accuracy. Tesseract performs
meaningfully better on high-contrast black-text-on-white images than on
raw video frames with busy backgrounds, gradients, or semi-transparent
overlay boxes — this converts a raw frame into something closer to that
before OCR ever sees it.
"""

import cv2


def preprocess_for_ocr(image_path):
    """
    Loads an image and applies grayscale conversion, contrast
    enhancement, and adaptive thresholding (binarization).

    Returns the processed image as a numpy array, ready to pass to
    pytesseract directly (no need to save it back to disk).
    """
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # CLAHE (Contrast Limited Adaptive Histogram Equalization) boosts
    # local contrast, which helps text stand out against busy or
    # gradient backgrounds without over-brightening the whole image.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Adaptive thresholding converts to pure black/white, deciding the
    # threshold locally per region rather than one global cutoff —
    # important since reels often have varying lighting and background
    # across a single frame.
    binarized = cv2.adaptiveThreshold(
        enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=15,
    )

    return binarized