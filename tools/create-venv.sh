#!/bin/sh

python -m venv venv
source venv/bin/activate

pip install --upgrade pip

pip install         \
    av              \
    glfw            \
    ipykernel       \
    numpy           \
    pillow          \
    pypng           \
    rendercanvas    \
    wgpu            \
    $NULL

# Pycairo is special.  It tries to drag in X11.

pip install -C setup-args='-Dno-x11=true' pycairo
