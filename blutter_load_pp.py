#
# Binary Ninja importer for PP (Object Pointer Pool) data from blutter
#
# Blutter takes a Flutter-based mobile app and dumps information about
# object storage, and this script imports that data to identify the uses
# of strings and other objects from the PP (static object pool) created by the DART
# compiler.
# 
# Basically, it takes anonymous instructions like
#  x0 = [x27 + 0x1234].q
# and annotates them to tell you which value is loaded from PP.
#
#
# Load libapp.so in binja, and identify functions using reflutter (see reflutter_load_dump.py)
# Run blutter (https://github.com/worawit/blutter) on your app to generate pp.txt
# Run this binja script and point it at pp.txt
# Wait for a long long time while it applies hints
# Take a look at your strings list, and see that some interesting strings now have xrefs!
#

import string
import json
import re
import os


def load_blutter_pp(pp_txt):
    RE_OBJINFO=re.compile("^\\[pp\\+0x(?P<offset>[0-9a-f]+)\\] (?P<description>.*)$")


    db = {}

    for line in open(pp_txt, "r"):
        line = line.strip()

        m = RE_OBJINFO.match(line)
        if not m: continue

        offset = int(m.group("offset"), 16)
        description = m.group("description")

        description = "".join(filter(lambda x: x in string.printable, description))

        db[offset] = description


    return db

def llil_get_op(instr, name, kind):
    for op_name, operand, op_type in instr.detailed_operands:
        if op_name == name and isinstance(operand, kind): return operand
    return None

# Find something like x0 = [x27 + 0x1234].q
# where x27 is the important factor and 0x1234 is the PP offset we want to annotate
def ll_test_is_basic_offset(i):
    if not isinstance(i, lowlevelil.LowLevelILSetReg): return None

    datasource = llil_get_op(i, "src", lowlevelil.LowLevelILLoad)
    if not datasource: return None

    addr_expr = llil_get_op(datasource, "src", lowlevelil.LowLevelILAdd)
    if not addr_expr: return None

    base = llil_get_op(addr_expr, "left", lowlevelil.LowLevelILReg)
    if not base: return None

    offset = llil_get_op(addr_expr, "right", lowlevelil.LowLevelILConst)
    if not offset: return None

    if base.src.name != "x27": return None

    # We've found a PP lookup instruction!
    # Let's annotate
    offset = offset.constant

    return offset

# Identify a pair of instructions like
# x0 = x27 + 0xf000
# x2 = [x0 + 0x290].q
# where the base is x27 (PP pointer) and the total offset is what we're interested in finding
def ll_test_is_split_offset(i1, i2):
    if not i2: return None, -1
    if not isinstance(i1, lowlevelil.LowLevelILSetReg): return None, 0
    if not isinstance(i2, lowlevelil.LowLevelILSetReg): return None, 0


    # I1 checks
    res1 = llil_get_op(i1, "dest", ILRegister)
    if not res1: return None,1

    addr_expr1 = llil_get_op(i1, "src", lowlevelil.LowLevelILAdd)
    if not addr_expr1: return None,2

    offset1 = llil_get_op(addr_expr1, "right", lowlevelil.LowLevelILConst)
    if not offset1: return None,3

    base1 = llil_get_op(addr_expr1, "left", lowlevelil.LowLevelILReg)
    if not base1: return None, 3.5
    if base1.src.name != "x27": return None,4

    intermediate_reg = res1.name

    # I2 checks:
    datasource2 = llil_get_op(i2, "src", lowlevelil.LowLevelILLoad)
    if not datasource2: return None,5

    addr_expr2 = llil_get_op(datasource2, "src", lowlevelil.LowLevelILAdd)
    if not addr_expr2: return None,6

    base2 = llil_get_op(addr_expr2, "left", lowlevelil.LowLevelILReg)
    if not base2: return None,7

    offset2 = llil_get_op(addr_expr2, "right", lowlevelil.LowLevelILConst)
    if not offset2: return None,8

    if base2.src.name != intermediate_reg: return None,9

    return offset1.constant + offset2.constant, 0

RE_STRINGDATA=re.compile("^String: \"(?P<text>.*)\"$")
INPUT = get_open_filename_input(prompt="Please select pp.txt from blutter")

print("Loading PP database...")
db = load_blutter_pp(INPUT)

print(f"Loaded {len(db)} object offsets")

n_comments = 0
missing_offsets = 0
n_string_xrefs = 0
n_missing_strings = 0
n_duplicate_strings = 0

view = bv

print("Finding PP lookups...")
functions = list(view.functions)
#functions = [ current_function ]
total = len(functions)
step = max(int(total / 25), 1)

string_address_references = {}

for func_index in range(total):
    f = functions[func_index]

    if func_index % step == 0:
        print(f"{round(100 * func_index/total)}% ({func_index+1} / {total})")
    
    if not f.llil: continue
    

    instructions = list(f.llil.instructions)
    for ins_index in range(len(instructions)):

        i1 = instructions[ins_index]

        try:
            i2 = instructions[ins_index+1]
        except:
            i2 = None

        offset = ll_test_is_basic_offset(i1)

        if not offset:
            offset,_ = ll_test_is_split_offset(i1, i2)

        if not offset:
            continue

        if offset not in db:
            missing_offsets += 1
            continue

        description = db[offset]
        comment = f"PP lookup ({offset:#x}): {description}"
        view.set_comment_at(i1.address, comment)
        n_comments += 1

        # Keep track of which string, so we can create an xref later
        m = RE_STRINGDATA.match(description)
        if m and len(m.group("text")) > 5:
            text = m.group("text")
            string_address_references[i1.address] = text

if True:
    print(f"Creating xrefs for {len(string_address_references)} identified PP string lookups...")

    found_strings = list(string_address_references.values())

    for sr in view.strings:
        if len(sr.value) < 5: continue
        if sr.value not in found_strings: continue

        for ins_addr, text in string_address_references.items():
            if text == sr.value:
                n_string_xrefs += 1
                view.add_user_data_ref(ins_addr, sr.start)



    #matches = []
    #fuzzy_matches = []
    #for sr in view.strings:
    #    candidate = sr.value
    #    if candidate == text:
    #        matches.append(sr)

    #if len(matches) == 0:
    #    for sr in view.strings:
    #        candidate = sr.value
    #        if candidate.startswith(text):
    #            fuzzy_matches.append(sr)

    #if len(matches + fuzzy_matches) == 0:
    #    n_missing_strings += 1
    #    print(f"Couldn't make xref to string \"{text}\" ({description}), even though it was in the pp data. What are we missing?")

    #elif len(matches) > 1:
    #    n_duplicate_strings += 1
    #    print(f"Duplicate string {text}, probably need to refine this script.")

    #for sr in matches + fuzzy_matches:
    #    n_string_xrefs += 1
    #    view.add_user_data_ref(i.address, sr.start)



print(f"Set {n_comments} comments based on identified PP lookups")
print(f"Found {missing_offsets} not in pp.txt")
print(f"Created {n_string_xrefs} xrefs to strings")
#print(f"Created {n_duplicate_strings} were data duplicates (?)")
#print(f"{n_missing_strings} were referenced but not found in the binja strings list (bug, analysis failure, ...)")
