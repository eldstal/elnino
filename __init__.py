from binaryninja import *

import elnino.mk_typelib
import elnino.load_pdb_types

#PluginCommand.register("Elnino: Generate Type Library", "Parse C headers into a reusable binja type library", elnino.mk_typelib.menu_click)
PluginCommand.register("Elnino: Load Types from PDB", "Load all types from a Microsoft PDB file", elnino.load_pdb_types.menu_click)
