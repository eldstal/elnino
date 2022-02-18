# Mocks for testing on the command line

import enum
from collections import defaultdict

class Type:
  def __init__(self, name, width, members=None):
    self.name = name
    self.width = width
    self.members = members

  @staticmethod
  def int(w): return Type("int", w)

  @staticmethod
  def bool(): return Type("bool", 1)

  @staticmethod
  def pointer_of_width(width, type): return Type(type.name + "*", width)

  @staticmethod
  def pointer(arch, type): return Type(type.name + "*", arch.address_size)

  @staticmethod
  def float(w): return Type("float", w)

  @staticmethod
  def char(): return Type("char", 1)

  @staticmethod
  def wide_char(w): return Type("wchar", w)

  @staticmethod
  def void(): return Type("void", 0)

  @staticmethod
  def enumeration(width, members): return Type("enum", width)

  @staticmethod
  def union(members): return Type(f"union", max(m[0].width for m in members), members=members)

  @staticmethod
  def array(target_type, count): return Type(f"{target_type.name}[{count}]", count*target_type.width)

  @staticmethod
  def structure(members): return Type(f"struct", sum(m[0].width for m in members), members=members)

  @staticmethod
  def named_type_reference(type_class, name): return Type(name, -1)

class BinaryView:
  def define_user_type(self, name, typ):
    pass

class Arch:
  def __init__(self):
    self.address_size = 8


class log:
  @staticmethod
  def log(lvl, msg): print(msg)

class NamedTypeReferenceClass(enum.IntEnum):
  UnknownNamedTypeClass = 0
  TypedefNamedTypeClass = 1
  ClassNamedTypeClass = 2
  StructNamedTypeClass = 3
  UnionNamedTypeClass = 4
  EnumNamedTypeClass = 5

Architecture = defaultdict(lambda: Arch())

bv = BinaryView()
