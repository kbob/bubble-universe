#!/bin/sh

python -m venv --copies --upgrade-deps venv
source venv/bin/activate
pip install numpy pypng pillow wgpu rendercanvas glfw ipykernel
