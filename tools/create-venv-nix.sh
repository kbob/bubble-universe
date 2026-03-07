#!/bin/sh

# Nix (home-manager) really does not want to cooperate with other
# package managers.  These packages are installed but not in a
# findable place.  The paths will probably change from time to time,
# and are certainly not right for any machine other than mine.

cairo=/nix/store/5ybma9c5cnkdarvfcb3xa2nw2qcxckq4-cairo-1.18.4-dev/lib/pkgconfig
girep=/nix/store/qf354zx5pdnpc9bhc9lj084s952v8w84-glib-2.80.4-dev/lib/pkgconfig
ffi=/nix/store/ac75zvf4brm8w58hfg7c86kl68rhf4m2-libffi-40-dev/lib/pkgconfig
export PKG_CONFIG_PATH="${cairo}:${girep}:${ffi}"
# echo PKG_CONFIG_PATH="$PKG_CONFIG_PATH"

sh -x "`dirname $0`/create-venv.sh"
exit
# python -m venv venv
# source venv/bin/activate
# pip 

# cairo_pc='/nix/store/5ybma9c5cnkdarvfcb3xa2nw2qcxckq4-cairo-1.18.4-dev/lib/pkgconfig'
# xcb_pc='/nix/store/bzh86i8c1rybaggxf1qgp2gq4dmlwldf-libxcb-1.17.0-dev/lib/pkgconfig'

# export PKG_CONFIG_PATH="${cairo_pc}:${xcb_pc}"
# pip install av graphviz numpy pypng pillow wgpu rendercanvas glfw ipykernel
