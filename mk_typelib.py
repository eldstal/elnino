from binaryninja import *

import subprocess
import os

def load_and_preprocess(sourcefile, defines=[], preincludes=[], include_dirs=None):

  if (include_dirs is None): include_dirs = []

  d = os.path.dirname(sourcefile)
  include_dirs = [d] + include_dirs

  commands = [
    # Option 1: Microsoft cl.exe
    #( [ "cl.exe", "/E" ]
    #  + [ f"/D{NAME}={VAL}" for NAME,VAL in defines ]
    #  + [ f"/I{DIR}" for DIR in include_dirs ]
    #  + [ f"/FI{FILE}" for FILE in preincludes ]
    #  + [ sourcefile ]
    #),

    # Option 2: clang++
    ( [ "clang", "-E", "-P" ]
      + [ f"-D{NAME}={VAL}" for NAME,VAL in defines ]
      + [ f"-I{DIR}" for DIR in include_dirs ]
      + [ arg for FILE in preincludes for arg in ("-include", f"{FILE}") ]
      #+ [ "-o", r"D:\Temp\source.h" ]
      + [ f"{sourcefile}" ]
    ),

    # Option 3: g++

    # Option 4: ...?
  ]

  for cmd in commands:
    try:
      log.log(0, str(cmd))
      completed = subprocess.run(cmd, capture_output=True, stderr=None, check=True, encoding="utf-8")
      return str(completed.stdout)
    except Exception as e:
      log.log(0, f"Failed to preprocess using {cmd[0]}")
      log.log(0, str(e))
      #log.log(0, e.stdout)
      log.log(0, e.stderr)

  log.log(1, "elnino: No preprocessors found. Falling back to plain header file.")
  log.log(1, "elnino: You better not have any macros or comments in there!")
  return open(sourcefile, "r").read()


def strip_dangerous(source):
  pragmas = re.compile(r"\s*#\s*pragma.*", re.I)

  source = re.sub(pragmas, "", source)

  return source

def make_lib(plat, sourcefile, destination, defines=[], preincludes=[], include_dirs=None):
  source = load_and_preprocess(sourcefile, defines, preincludes, include_dirs)

  source = strip_dangerous(source)

  open(r"D:\temp\source.h", "w+").write(source)

  loaded = plat.parse_types_from_source(source)
  print(loaded)


def menu_click(view):
  defines_win = [
                  ("_WIN64", 1),
                  ("_AMD64_", 1),
                  ("AMD64", 1),
                  ("_WIN32_WINNT", 0x0A00),
                  ("WINVER", 0x0A00),
                  ("WINNT", 1),
                  ("NTDDI_VERSION", 0xA00000B),
                  #("NTAPI", "__stdcall"),
                 ]

  make_lib(
           plat = Platform['windows-x86_64'],
           sourcefile = r"C:\Program Files (x86)\Windows Kits\10\Include\wdf\umdf\2.33\wdf.h",
           destination = r"C:\Users\Albin\AppData\Roaming\Binary Ninja\typelib\wdf.bntl",
           preincludes = [
            r"sdkddkver.h"
           ],
           include_dirs = [
            r"C:\Program Files (x86)\Windows Kits\10\Include\10.0.22000.0\shared"
           ],
           defines=defines_win
          )
  pass
