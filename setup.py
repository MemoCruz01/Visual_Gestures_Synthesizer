"""
Setup file for Visual Gestures Synthesizer
"""

from setuptools import setup, find_packages

setup(
    name="visual-gestures-synthesizer",
    version="0.1.0",
    description="Air Music App with Hand Tracking",
    author="Visual Gestures Team",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.9",
    install_requires=[
        "opencv-python>=4.8.0",
        "mediapipe>=0.10.0",
        "PySide6>=6.6.0",
        "numpy>=1.24.0",
        "pyaudio>=0.2.13",
        "scipy>=1.11.0",
    ],
    entry_points={
        "console_scripts": [
            "visual-gestures-synthesizer=visual_gestures_synthesizer.main:main",
        ],
    },
)
