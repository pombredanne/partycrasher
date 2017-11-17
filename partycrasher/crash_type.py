#!/usr/bin/env python
# -*- coding: utf-8 -*-

#  Copyright (C) 2015, 2016 Joshua Charles Campbell

#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from six import string_types
import re
from partycrasher.pc_exceptions import BadTypeNameError

good = re.compile('(\w+)$')

class CrashType(object):
    """
    Metadata about a crash type.
    """
    __slots__ = 'name'
    
    def __init__(self, crash_type):
        if isinstance(crash_type, CrashType):
            self.name = crash_type.name
        elif isinstance(crash_type, string_types):
            self.name = crash_type
        elif isinstance(crash_type, dict) and 'name' in crash_type:
            self.name = crash_type['name']
        else:
            raise BadTypeNameError(repr(crash_type))
        m = good.match(self.name)
        if m is None:
            raise BadTypeNameError(self.name)
        if m.group(1) != self.name:
            raise BadTypeNameError(self.name)
    
    def __str__(self):
        return self.name
    
    def __copy__(self):
        return CrashType(self)

    def __hash__(self):
        return hash((CrashType, self.name))
    
    def __eq__(self, other):
        return isinstance(other, CrashType) and self.name == other.name
    
    def __repr__(self):
        return self.__class__.__name__ + "(" + repr(self.name) + ")"