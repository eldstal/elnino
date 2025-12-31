#
# reflutter support script for binary ninja
# 1. Instrument your app according to documentation at https://github.com/Impact-I/reFlutter
# 2. Run the instrumented app and extract dump.dart
# 3. Load app.so in binja
# 4. Load this script in binja and select dump.dart
# 5. Get some function info! Neat!
#

import os
import re


from json import JSONDecoder, JSONDecodeError


def load_stacked_json(path):
    document = open(path, "r").read()
    NOT_WHITESPACE = re.compile(r'\S')
    decoder = JSONDecoder()

    ret = []
    idx = 0
    while True:
        match = NOT_WHITESPACE.search(document, idx)
        if not match:
            break
        idx = match.start()
        
        try:
            obj, idx = decoder.raw_decode(document, idx)
        except JSONDecodeError:
            # do something sensible if there's some error
            raise
        ret.append(obj)

    return ret

def auto_name(info):
    package = info["library_url"].replace("package:", "")
    package_head = package.split("/")[0]
    package_tail = package.split("/")[-1].replace(".dart", "")

    package_shorthand = package_head
    if package_tail != package_head:
        package_shorthand += "::" + package_tail

    return package_shorthand + "::" + info["class_name"] + "::" + info["method_name"]

def main():
    dump_file = get_open_filename_input(prompt="Please select dump.dart from reflutter")

    if not bv.get_tag_type("Reflutter New"):
        bv.create_tag_type("Reflutter New", "🦋")
    if not bv.get_tag_type("Reflutter Renamed"):
        bv.create_tag_type("Reflutter Renamed", "🇳")
    if not bv.get_tag_type("Reflutter Collision"):
        bv.create_tag_type("Reflutter Collision", "💥")

    if not os.path.exists(dump_file):
        print("Failed to find the reflutter dump file.")
        print("You need to first instrument your app using reflutter, run it and then retrieve the dump.dart file")
        return

    if "_kDartIsolateSnapshotInstructions" not in bv.symbols:
        print("Failed to find symbol _kDartIsolateSnapshotInstructions in the loaded binary. Are you sure this is a flutter app.so you've loaded?")
        return

    base_addr = bv.symbols["_kDartIsolateSnapshotInstructions"][0].address

    dump_data = load_stacked_json(dump_file)

    n_unknowns = 0
    n_existing = 0
    n_interfering = 0

    name_collisions = {}
    for info in dump_data:
        best_name = auto_name(info)
        name_collisions[best_name] = name_collisions.get(best_name, set()) | {info["offset"]}


    for info in dump_data:
        if "method_name" not in info:
            print("Unknown dump info type:")
            print(info)
            print("Could be that reflutter has gained some functionality. Ignoring this data for now.")
            continue

        offset = int(info["offset"], 16)
        func_addr = base_addr + offset

        # Deconfliction of names
        new_name = auto_name(info)
        if len(name_collisions[new_name]) > 1:
            new_name = f"{new_name}_{offset:x}"
            #print(new_name)
        else:
            pass
            #print(new_name)

        existing_functions = bv.get_functions_containing(func_addr)

        if len(existing_functions) == 0:
            n_unknowns += 1
            f = bv.create_user_function(func_addr)
            f.name = new_name
            f.analyze()
            if not f.get_function_tags(tag_type="Reflutter New"):
                f.add_tag("Reflutter New", "Automatically generated from reflutter dump")

        for f in existing_functions:
            if f.lowest_address == func_addr:
                n_existing += 1
                f.name = new_name
                if not f.get_function_tags(tag_type="Reflutter Renamed"):
                    f.add_tag("Reflutter Renamed", "Automatically renamed from reflutter dump")
                break
            else:
                n_interfering += 1
                if not f.get_function_tags(tag_type="Reflutter Collision"):
                    f.add_tag("Reflutter Collision", "This function was truncated because another was found inside of it")

                nf = bv.create_user_function(func_addr)
                nf.name = new_name
                print(f"Colliding function: {new_name}")
                print(f"{func_addr:#x}")
                print(f)
                break

    print("Finished analyzing.")
    print(f"Dump functions matching existing functions: {n_existing}")
    print(f"Dump functions inside existing functions: {n_interfering}")
    print(f"Dump functions not at all identified as functions: {n_unknowns}")
            



main()
