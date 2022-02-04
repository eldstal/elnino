
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

# Returns type
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

# Returns None if the type can't be resolved for some reason
# Generates pointers, gets structures and enums from parsed_structs
# Returns type,typeref,typename
# If the type doesn't need a typeref, the type info is returned twice.
def resolve_type(arch, m, types):
  if hasattr(m, "name"):
    typename = m.name
  else:
    typename = "unnamed_garbage"

  if not hasattr(m, "leaf_type"):
    t = guess_builtin_type(arch, m)
    return t, t, str(m)

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
    return Type.void(), Type.void(), "invalid_type"

  if m.leaf_type == "LF_MEMBER":
    #return guess_builtin_type(arch, m.index.name), typename
    return resolve_type(arch,m.index, types)

  elif m.leaf_type == "LF_STRUCTURE":
    typename = m.name
    t = None
    if m.name in types["struct"]:
      t = types["struct"][m.name]
    typeclass = NamedTypeReferenceClass["StructNamedTypeClass"]
    ntr = Type.named_type_reference(type_class=typeclass, name=m.name)
    return t, ntr, typename

  elif m.leaf_type == "LF_ENUM":
    typename = m.name
    if m.name in types["enum"]:
      t = types["enum"][m.name]
      typeclass = NamedTypeReferenceClass["EnumNamedTypeClass"]
      ntr = Type.named_type_reference(type_class=typeclass, name=m.name)
      return t, ntr, typename

  elif m.leaf_type == "LF_UNION":
    typename = m.name
    t = None
    if m.name in types["struct"]:
      t = types["struct"][m.name]
    typeclass = NamedTypeReferenceClass["UnionNamedTypeClass"]
    ntr = Type.named_type_reference(type_class=typeclass, name=m.name)
    return t, ntr, typename

  elif m.leaf_type == "LF_POINTER":
    target_type, typeref, ttypename = resolve_type(arch, m.utype, types)
    if typeref is not None:
      t = Type.pointer(arch, type = typeref)
      return t, t, ttypename + "*"

  elif m.leaf_type == "LF_ARRAY":
    #log.log(0, str(dir(m.element_type)))
    target_type,tref,ttypename = resolve_type(arch, m.element_type, types)
    if target_type is not None:
      #log.log(0, f"Array {m.name}: ")
      #log.log(0, "  " + str(target_type))
      #log.log(0, "  " + ttypename)

      count = 0
      if target_type.width != 0:
        count = m.size // target_type.width

      t = Type.array(tref, count)
      return t, t, f"{ttypename}"

  elif m.leaf_type == "LF_BITFIELD":
    target_type, tref, ttypename = resolve_type(arch, m.base_type, types)
    if target_type is not None:
      return target_type, tref, typename

  else:
    log.log(0, f"Unknown leaf type {m.leaf_type}")
    return Type.void(), Type.void(), typename

  return None, None, typename

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
def parse_struct(arch, s, types):
  # We can only generate this type if all the subtypes are known
  missing_types = []
  members = []
  for m in s.fieldlist.substructs:
    name = "unnamed_substruct"
    if hasattr(m, "name"): name = m.name

    if hasattr(m, "offset"):
      subtype,typeref, typename = resolve_type(arch, m, types)
      if typeref is None:
        missing_types.append((typename, name))
      else:
        # Reference to a named type
        t = typeref

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

  return Type.structure(members=members)

# Returns None if the type is still incomplete,
# i.e. members have types that aren't yet in parsed_structs
def parse_union(arch, s, types):
  # We can only generate this type if all the subtypes are known
  missing_types = []
  members = []
  for m in s.fieldlist.substructs:
    name = "unnamed_substruct"
    if hasattr(m, "name"): name = m.name

    if hasattr(m, "offset"):
      subtype,typeref, typename = resolve_type(arch, m, types)
      if typeref is None:
        missing_types.append(typename)
      else:
        # Reference to a named type
        t = typeref

        # Inline it as an anonymous struct
        if "__unnamed_" in typename:
          log.log(0, f"Inlining type {typename} inside {s.name}")
          t = subtype

        members.append(StructureMember(type=t,
                                       name=name,
                                       offset=m.offset))

  if len(missing_types) != 0:
    log.log(0, f"Unable to parse union {s.name}, missing {missing_types}")
    return None

  return Type.union(members=members)



# Returns a dictionary of name -> type
def load_pdb(bv, path):
  types = { "struct": {}, "enum": {}, "union": {} }

  pdb = pp.parse(path)


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
    ntr = Type.named_type_reference(type_class=typeclass, name=e.name)
    types["enum"][e.name] = ntr

  n_parsed_structs = 0
  iteration_structs = -1
  while len(structs) > 0 and iteration_structs != 0:
    iteration_structs = 0
    remaining_structs = []
    for s in structs:
      #if "nickle" not in s.name: continue
      p = None
      if s.leaf_type == "LF_STRUCTURE":
        log.log(0, f"Parsing struct {s.name}")
        p = parse_struct(arch, s, types)
        typeclass = NamedTypeReferenceClass["StructNamedTypeClass"]

      elif s.leaf_type == "LF_UNION":
        log.log(0, f"Parsing union {s.name}")
        p = parse_union(arch, s, types)
        typeclass = NamedTypeReferenceClass["UnionNamedTypeClass"]

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
    log.log(0, f"{len(structs)} not parsed due to incomplete info. This is probably a bug in the script.")

  return types


def go(bv):
  load_pdb(bv, r"C:\Symbols\ntdll.pdb\23E72AA7E3873AC79882BF6E394DA71E1\ntdll.pdb")
  #load_pdb(bv, r"D:\Storage\Hax\experiments\symapp\symapp\Debug\symapp.pdb")

def menu_click(view):
  types = go(view)

  


if __name__ == "__main__":
  go(bv)



