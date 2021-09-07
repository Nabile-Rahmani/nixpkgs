#!/usr/bin/env nix-shell
#!nix-shell update-shell.nix -i python3


# format:
# $ nix run nixpkgs.python3Packages.black -c black update.py
# type-check:
# $ nix run nixpkgs.python3Packages.mypy -c mypy update.py
# linted:
# $ nix run nixpkgs.python3Packages.flake8 -c flake8 --ignore E501,E265,E402 update.py

# If you see `HTTP Error 429: too many requests` errors while running this script,
# refer to:
#
# https://github.com/NixOS/nixpkgs/blob/master/doc/languages-frameworks/vim.section.md#updating-plugins-in-nixpkgs-updating-plugins-in-nixpkgs

import inspect
import os
import sys
import logging
import textwrap
from typing import List, Tuple
from pathlib import Path

log = logging.getLogger()
log.addHandler(logging.StreamHandler())

# Import plugin update library from maintainers/scripts/pluginupdate.py
ROOT = Path(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))))
sys.path.insert(0, os.path.join(ROOT.parent.parent.parent, "maintainers", "scripts"))
import pluginupdate

GET_PLUGINS = f"""(with import <localpkgs> {{}};
let
  inherit (vimUtils.override {{inherit vim;}}) buildVimPluginFrom2Nix;
  generated = callPackage {ROOT}/generated.nix {{
    inherit buildVimPluginFrom2Nix;
  }};
  hasChecksum = value: lib.isAttrs value && lib.hasAttrByPath ["src" "outputHash"] value;
  getChecksum = name: value:
    if hasChecksum value then {{
      submodules = value.src.fetchSubmodules or false;
      sha256 = value.src.outputHash;
      rev = value.src.rev;
    }} else null;
  checksums = lib.mapAttrs getChecksum generated;
in lib.filterAttrs (n: v: v != null) checksums)"""

HEADER = (
    "# This file has been generated by ./pkgs/misc/vim-plugins/update.py. Do not edit!"
)


class VimEditor(pluginupdate.Editor):
    def generate_nix(self, plugins: List[Tuple[str, str, pluginupdate.Plugin]], outfile: str):
        sorted_plugins = sorted(plugins, key=lambda v: v[2].name.lower())

        with open(outfile, "w+") as f:
            f.write(HEADER)
            f.write(textwrap.dedent("""
                { lib, buildVimPluginFrom2Nix, fetchFromGitHub }:

                final: prev:
                {"""
            ))
            for owner, repo, plugin in sorted_plugins:
                if plugin.has_submodules:
                    submodule_attr = "\n      fetchSubmodules = true;"
                else:
                    submodule_attr = ""

                f.write(textwrap.indent(textwrap.dedent(
                    f"""
  {plugin.normalized_name} = buildVimPluginFrom2Nix {{
    pname = "{plugin.name}";
    version = "{plugin.version}";
    src = fetchFromGitHub {{
      owner = "{owner}";
      repo = "{repo}";
      rev = "{plugin.commit}";
      sha256 = "{plugin.sha256}";{submodule_attr}
    }};
    meta.homepage = "https://github.com/{owner}/{repo}/";
  }};
"""
                ), '  '))
            f.write("\n}\n")
        print(f"updated {outfile}")



def main():
    editor = VimEditor("vim", ROOT, GET_PLUGINS)
    parser = editor.create_parser()
    args = parser.parse_args()
    pluginupdate.update_plugins(editor, args)


if __name__ == "__main__":
    main()
