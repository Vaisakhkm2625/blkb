{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    bluez
    dbus
    dbus-glib
    glib
    cairo
    gobject-introspection
    pkg-config
    (python3.withPackages (ps: with ps; [
      dbus-python
      pygobject3
    ]))
  ];

  shellHook = ''
    export GI_TYPELIB_PATH="$GI_TYPELIB_PATH:${pkgs.gobject-introspection.out}/lib/girepository-1.0"
    export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:${pkgs.cairo.out}/lib:${pkgs.glib.out}/lib"
  '';
}
