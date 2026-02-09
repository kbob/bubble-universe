#!/bin/sh

python -m venv --copies --upgrade-deps venv
source venv/bin/activate
pip install av numpy pypng pillow wgpu rendercanvas glfw ipykernel
