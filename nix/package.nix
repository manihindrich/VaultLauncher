{
  lib,
  python3Packages,
  qt6,
}:

let
  appId = "io.github.manihindrich.VaultLauncher";
in
python3Packages.buildPythonApplication {
  pname = "vault-launcher";
  version = "0.1.0";
  pyproject = true;
  src = lib.cleanSource ../.;

  build-system = [ python3Packages.hatchling ];
  dependencies = [ python3Packages.pyside6 ];

  nativeBuildInputs = [ qt6.wrapQtAppsHook ];
  buildInputs = [
    qt6.qtbase
    qt6.qtsvg
    qt6.qtwayland
  ];

  # Wrap the Python entry point with the Qt environment instead of a second wrapper.
  dontWrapQtApps = true;
  preFixup = ''
    makeWrapperArgs+=("''${qtWrapperArgs[@]}")
  '';

  postInstall = ''
    install -Dm644 data/${appId}.desktop $out/share/applications/${appId}.desktop
    # Show Obsidian's own icon, which an Obsidian install provides.
    substituteInPlace $out/share/applications/${appId}.desktop \
      --replace-fail "Icon=${appId}" "Icon=obsidian"
    install -Dm644 data/${appId}.metainfo.xml $out/share/metainfo/${appId}.metainfo.xml
    install -Dm644 src/vault_launcher/resources/app-icon.svg \
      $out/share/icons/hicolor/scalable/apps/${appId}.svg
  '';

  nativeCheckInputs = [ python3Packages.pytestCheckHook ];
  pythonImportsCheck = [ "vault_launcher" ];

  meta = {
    description = "Small launcher window for Obsidian vaults";
    homepage = "https://github.com/manihindrich/VaultLauncher";
    license = lib.licenses.mit;
    mainProgram = "vault-launcher";
    platforms = lib.platforms.linux;
  };
}
