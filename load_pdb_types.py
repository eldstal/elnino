
if __name__ == "__main__":
  from binja_dummy import *
else:
  from binaryninja import *

import time
import re

import pdbparse as pp

# Snipped from one of the pdbparse examples
ctype = {
    "T_32PINT4": "long*",
    "T_32PRCHAR": "unsigned char*",
    "T_32PUCHAR": "unsigned char*",
    "T_32PULONG": "unsigned long*",
    "T_32PLONG": "long*",
    "T_32PUQUAD": "unsigned long long*",
    "T_32PUSHORT": "unsigned short*",
    "T_32PVOID": "void*",
    "T_64PVOID": "void*",
    "T_INT4": "long",
    "T_INT8": "long long",
    "T_LONG": "long",
    "T_QUAD": "long long",
    "T_RCHAR": "unsigned char",
    "T_REAL32": "float",
    "T_REAL64": "double",
    "T_REAL80": "long double",
    "T_SHORT": "short",
    "T_UCHAR": "unsigned char",
    "T_UINT4": "unsigned long",
    "T_ULONG": "unsigned long",
    "T_UQUAD": "unsigned long long",
    "T_USHORT": "unsigned short",
    "T_WCHAR": "wchar",
    "T_VOID": "void",
}

base_type_size = {
    "T_32PRCHAR": 4,
    "T_32PUCHAR": 4,
    "T_32PULONG": 4,
    "T_32PUQUAD": 4,
    "T_32PUSHORT": 4,
    "T_32PVOID": 4,
    "T_64PVOID": 8,
    "T_INT4": 4,
    "T_INT8": 8,
    "T_LONG": 4,
    "T_QUAD": 8,
    "T_RCHAR": 1,
    "T_REAL32": 4,
    "T_REAL64": 8,
    "T_REAL80": 10,
    "T_SHORT": 2,
    "T_UCHAR": 1,
    "T_UINT4": 4,
    "T_ULONG": 4,
    "T_UQUAD": 8,
    "T_USHORT": 2,
    "T_WCHAR": 2,
    "T_32PLONG": 4,
}


builtin_types = {
    "T_32PINT4":   Type.pointer_of_width(width=4, type=Type.int(4)),
    "T_32PRCHAR":  Type.pointer_of_width(width=4, type=Type.char()),
    "T_32PUCHAR":  Type.pointer_of_width(width=4, type=Type.char()),
    "T_32PLONG":   Type.pointer_of_width(width=4, type=Type.int(4)),
    "T_32PULONG":  Type.pointer_of_width(width=4, type=Type.int(4)),
    "T_32PUQUAD":  Type.pointer_of_width(width=4, type=Type.int(8)),
    "T_32PUSHORT": Type.pointer_of_width(width=4, type=Type.int(2)),
    "T_32PVOID":   Type.pointer_of_width(width=4, type=Type.void()),
    "T_64PVOID":   Type.pointer_of_width(width=8, type=Type.void()),
    "T_INT4": Type.int(4),
    "T_INT8": Type.int(8),
    "T_LONG": Type.int(4),
    "T_QUAD": Type.int(8),
    "T_RCHAR": Type.char(),
    "T_REAL32": Type.float(4),
    "T_REAL64": Type.float(8),
    "T_REAL80": Type.float(10),
    "T_SHORT": Type.int(2),
    "T_UCHAR": Type.char(),
    "T_UINT4": Type.int(4),
    "T_ULONG": Type.int(4),
    "T_UQUAD": Type.int(8),
    "T_USHORT": Type.int(2),
    "T_WCHAR": Type.wide_char(2),
}

basic_width = {
  "SHORT": 2,
  "INT": 4,
  "LONG": 4,
  "QUAD": 8,
}

spec_width = {
  "08": 1,
  "1" : 1,
  "2" : 2,
  "4" : 4,
  "8" : 8,

  # The rules just changed
  "32": 4,
  "64": 8,
  "80": 10,
}

# This takes a basic typename on the microsoft format such as T_PUWCHAR80 and
# generates a binja Type from it.
def guess_builtin_type(arch, typename):

  #log.log(0, f"Basic type: {typename}")

  if typename in builtin_types:
    return builtin_types[typename]

  # The windows types are numerous and verbose.
  # This is my best attempt at deciphering the ones we're missing as they come up
  components = re.compile("T_(?P<psize>(32|64)?)(?P<ptr>P?)(?P<unsigned>U?)(?P<typ>VOID|BOOL|INT|RCHAR|WCHAR|CHAR|SHORT|LONG|QUAD|REAL)(?P<vsize>(08|1|2|4|8|32|64|80)?)")

  m = components.match(typename)
  if not m:
    raise RuntimeError(f"Unknown builtin? type {typename}")

  ty = None

  if m.group("typ") in [ "VOID" ]:
    ty = Type.void()

  elif m.group("typ") in [ "BOOL" ]:
    ty = Type.bool()  # Maybe int(1)?

  elif m.group("typ") in [ "INT", "SHORT", "LONG", "QUAD" ]:
    width = basic_width[m.group("typ")]
    if m.group("vsize"):
      width = spec_width[m.group("vsize")]
    ty = Type.int(width)

  elif m.group("typ") in [ "RCHAR", "WCHAR", "CHAR" ]:
    width = 1
    if m.group("vsize"):
      width = spec_width[m.group("vsize")]
    ty = Type.wide_char(1)

  elif m.group("typ") in [ "REAL" ]:
    width = 4
    if m.group("vsize"):
      width = spec_width[m.group("vsize")]
    ty = Type.float(width)

  else:
    raise RuntimeError(f"Unknown basic type {m.group('typ')} in builtin type {typename}.")


  # Pointer to whatever we parsed above
  if m.group("ptr") == "P":
    width = arch.address_size
    if m.group("psize") is not None:
      width = int(m.group("psize")) // 8
      ty = Type.pointer_of_width(width=width, type=ty)

  builtin_types[typename] = ty
  return ty

# Returns type,loose_typeref,firm_typeref,typename
# A loose_typeref is an attempt at a reference to a future type,
# which is not yet defined. a firm_typeref is definitely valid right now,
# and already present in binja's type system.
# Generates pointers, gets structures and enums from types["struct"] and types["enum"]
# If the type doesn't need a typeref, the type info is returned twice.
def resolve_type(bv, arch, m, types):
  if hasattr(m, "name"):
    typename = m.name
  else:
    typename = "unnamed_garbage"

  if not hasattr(m, "leaf_type"):
    t = guess_builtin_type(arch, m)
    return t, t, t, str(m)

  known_leaves = [
                     "LF_ARRAY",
                     "LF_ARRAY_ST",
                     "LF_ENUM",
                     "LF_STRUCTURE",
                     "LF_STRUCTURE_ST",
                     "LF_UNION",
                     "LF_POINTER",
                     "LF_MEMBER",
                     "LF_UNION_ST",
                     "LF_CLASS"
                 ]

  if m.leaf_type not in known_leaves:
    return Type.void(), Type.void(), Type.void(), "invalid_type"

  if m.leaf_type == "LF_MEMBER":
    #return guess_builtin_type(arch, m.index.name), typename
    return resolve_type(bv, arch,m.index, types)

  elif m.leaf_type == "LF_STRUCTURE":
    typename = m.name
    t = None
    ltr = None
    ftr = None

    typeclass = NamedTypeReferenceClass["StructNamedTypeClass"]
    ltr = Type.named_type_reference(type_class=typeclass, name=typename)

    ## We need the member structure type to be completely defined already,
    ## because you can't have a member struct of an unknown size.
    if m.name in types["struct"] and m.name in bv.type_names:
      t = types["struct"][m.name]
      ftr = Type.named_type_from_registered_type(bv, typename)

    # The caller may be OK with just a loose reference, for example to
    # make a pointer to a struct that is unknown (or the self!)
    # In that case, ftr is None but ltr is a named_type_reference
    # which appears to be useless other than as a placeholder.
    return t, ltr, ftr, typename

  elif m.leaf_type == "LF_ENUM":
    typename = m.name
    if m.name in types["enum"]:
      t = types["enum"][m.name]
      typeclass = NamedTypeReferenceClass["EnumNamedTypeClass"]
      ltr = Type.named_type_reference(type_class=typeclass, name=m.name)
      ftr = Type.named_type_from_registered_type(bv, name=m.name)
      return t, ltr, ftr, typename

  elif m.leaf_type == "LF_UNION":
    typename = m.name
    t = None
    ftr = None
    if m.name in types["struct"]:
      t = types["struct"][m.name]
      ftr = Type.named_type_from_registered_type(bv, name=m.name)

    typeclass = NamedTypeReferenceClass["UnionNamedTypeClass"]
    ltr = Type.named_type_reference(type_class=typeclass, name=m.name)
    return t, ltr, ftr, typename

  elif m.leaf_type == "LF_POINTER":
    target_type, ltyperef, ftyperef, ttypename = resolve_type(bv, arch, m.utype, types)

    # It's OK for the target type to be undefined as of yet, because a pointer
    # is certainly of known size.
    if ltyperef is None:
      ltyperef = Type.named_type_reference(type_class=NamedTypeReferenceClass["StructNamedTypeClass"], name=typename)

    t = Type.pointer(arch, type = ltyperef)
    return t, t, t, ttypename + "*"

  elif m.leaf_type == "LF_ARRAY":
    #log.log(0, str(dir(m.element_type)))
    target_type,ltr,ftr,ttypename = resolve_type(bv, arch, m.element_type, types)

    # Can't make an array unless we know for sure the size of the inner type
    # The loose type reference isn't enough.
    if ftr is not None:
      count = 0
      if target_type.width != 0:
        count = m.size // target_type.width

      t = Type.array(ftr, count)
      return t, t, t, f"{ttypename}"

  elif m.leaf_type == "LF_BITFIELD":
    target_type, ltr, ftr, ttypename = resolve_type(bv, arch, m.base_type, types)
    if target_type is not None:
      return target_type, ltr, ftr, typename

  else:
    log.log(0, f"Unknown leaf type {m.leaf_type}")
    return Type.void(), Type.void(), Type.void(), typename

  # Can't resolve this type. Parse some more of the PDB and try again later.
  return None, None, None, typename

# Pass in a pdbparse object
# Receive a Type.enum
def parse_enum(arch, e):
  elem_size = guess_builtin_type(arch, e.utype).width
  members = []
  for s in e.fieldlist.substructs:
    if not hasattr(s, "name"):
      return None
    members.append( (s.name, s.enum_value) )

  return Type.enumeration(width=elem_size, members=members)

# Returns None if the type is still incomplete,
# i.e. members have types that aren't yet in parsed_structs
def parse_struct(bv, arch, s, types, is_union=False):
  # We can only generate this type if all the subtypes are known
  missing_types = []
  members = []
  for m in s.fieldlist.substructs:
    name = "unnamed_substruct"
    if hasattr(m, "name"): name = m.name

    if hasattr(m, "offset"):
      subtype,ltr,ftr,typename = resolve_type(bv, arch, m, types)
      # If that member's type couldn't be firmly determined, i.e.
      # well enough to know its size, give up on it for now.
      # This struct will be parsed again later.
      if ftr is None:
        missing_types.append((typename, name))
      else:
        # Reference to a named type
        t = ltr

        # Inline it as an anonymous struct
        if "__unnamed_" in typename:
          log.log(0, f"Inlining type {typename} inside {s.name}")
          t = subtype

        members.append(StructureMember(type=t,
                                       name=name,
                                       offset=m.offset))

  if len(missing_types) != 0:
    log.log(0, f"Unable to parse struct {s.name}, missing {missing_types}")
    return None

  if is_union:
    return Type.union(members=members)
  else:
    return Type.structure(members=members)




# Returns a dictionary of name -> type
def load_pdb(bv, path):
  types = { "struct": {}, "enum": {}, "union": {} }

  pdb = pp.parse(path)

  if pdb is None:
    log.log(2, f"Unable to open {path}.")
    return None


  # TODO: Determine from PDB
  arch = Architecture['x86_64']


  structs = [
               s for s in pdb.streams[pp.PDB_STREAM_TPI].types.values()
               if (s.leaf_type == "LF_STRUCTURE" or s.leaf_type == "LF_UNION") and not s.prop.fwdref
            ]

  enums = [
               e for e in pdb.streams[pp.PDB_STREAM_TPI].types.values()
               if e.leaf_type == "LF_ENUM" and not e.prop.fwdref
          ]


  # The PDB may contain duplicate types. That's part of the deal.
  # We only care about the latest version of each type, though.

  for e in enums:
    log.log(0, f"Parsing enum {e.name}")
    et = parse_enum(arch, e)
    if et is None:
      log.log(1, f"Unable to parse enum {e.name}.")
      continue

    # Add the type to the binja project
    bv.define_user_type(e.name, et)

    # Create a named reference for others to use this structure as a member
    typeclass = NamedTypeReferenceClass["EnumNamedTypeClass"]
    ltr = Type.named_type_reference(type_class=typeclass, name=e.name)
    types["enum"][e.name] = ltr

  n_parsed_structs = 0
  iteration_structs = -1
  while len(structs) > 0 and iteration_structs != 0:
    iteration_structs = 0
    remaining_structs = []
    for s in structs:
      #if "unnamed_143b" not in s.name: continue
      p = None
      if s.leaf_type == "LF_STRUCTURE":
        log.log(0, f"Parsing struct {s.name}")
        #print(s)
        p = parse_struct(bv, arch, s, types, is_union=False)
        #typeclass = NamedTypeReferenceClass["StructNamedTypeClass"]

      elif s.leaf_type == "LF_UNION":
        log.log(0, f"Parsing union {s.name}")
        p = parse_struct(bv, arch, s, types, is_union=True)
        #typeclass = NamedTypeReferenceClass["UnionNamedTypeClass"]

      if p is not None:
        iteration_structs += 1

        # Add the type to the binja project
        bv.define_user_type(s.name, p)

        # Create a named reference for others to use this structure as a member
        types["struct"][s.name] = p
      else:
        remaining_structs.append(s)

    # Discard the ones we've successfully parsed out
    structs = remaining_structs
    log.log(0, f"{len(structs)} incomplete structs left to parse...")

    n_parsed_structs += iteration_structs
    log.log(1, f"{n_parsed_structs} structures parsed from PDB.")

  log.log(1, f"{len(enums)} enums parsed from PDB.")
  if len(structs) > 0:
    log.log(2, f"{len(structs)} not parsed due to incomplete info. This is probably a bug in the script.")

  return types


def go(bv):
  pdb_path = interaction.get_open_filename_input("Select PDB file to load types")
  if pdb_path is not None:
    load_pdb(bv, pdb_path)

# Test code to figure out what can and cannot work in binja's type system
# It turns out that named_type_reference will never be a good member of a struct,
# because even once the target type is known the size of the member will not be updated.
# Not sure what good it is.
# The workaround for now is to register the types in the bv as soon as they are complete, and
# get fully-fledged type references from the registered types instead.
def attempt(bv):

  STRUCT = NamedTypeReferenceClass["StructNamedTypeClass"]
  bv.define_user_type("complete", Type.structure([ (Type.int(4), "num"), (Type.int(8), "quad") ]))

  bv.define_user_type("uses_both",
                              Type.structure([
                                       StructureMember(offset=0x00, name="incomp", type=Type.named_type_reference(type_class=STRUCT, name="incomplete")),
                                       #StructureMember(offset=0x40, name="comp",   type=Type.named_type_reference(type_class=STRUCT, name="complete")),
                                       StructureMember(offset=0x40, name="comp",   type=Type.named_type_from_registered_type(bv, name="complete")),
                              ])
                     )

  log.log(0, "the incomplete member is currently width=" + str(bv.get_type_by_name("uses_both").members[0].type.width))
  log.log(0, "the complete member is currently width=" + str(bv.get_type_by_name("uses_both").members[1].type.width))
  log.log(0, "the total struct is currently width=" + str(bv.get_type_by_name("uses_both").width))

  bv.define_user_type("incomplete", Type.structure([ (Type.array(Type.char(), 64), "txt")]))


  builder = StructureBuilder.create(type=StructureVariant["StructStructureType"])

  # This works, but has no forward references. The `incomplete` type must have been registered previously.
  builder.add_member_at_offset(offset=0x00, name="comp",  type=Type.named_type_from_registered_type(bv, name="complete"))
  builder.add_member_at_offset(offset=0x10, name="incomp", type=Type.named_type_from_registered_type(bv, name="incomplete"))

  #builder.add_member_at_offset(offset=0x00, name="comp",  type=Type.named_type_reference(type_class=STRUCT, name="complete"))
  #builder.add_member_at_offset(offset=0x10, name="incomp", type=Type.named_type_reference(type_class=STRUCT, name="incomplete"))

  #builder.add_member_at_offset(offset=0x00, name="comp",  type=bv.get_type_by_name("complete"))
  #builder.add_member_at_offset(offset=0x10, name="incomp", type=bv.get_type_by_name("incomplete"))

  bv.define_user_type("slow_built", builder.immutable_copy())

  log.log(0, "the slow struct is currently width=" + str(bv.get_type_by_name("slow_built").width))

def menu_click(view):
  types = go(view)

  #attempt(view)


if __name__ == "__main__":
  go(bv)



