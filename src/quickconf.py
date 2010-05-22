# -*- coding: utf-8 -*-
#
# QuickConf - Use GConf, quickly!
#
# Copyright © 2010 Siegfried-Angel Gevatter Pujals <siegfried@gevatter.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gconf
import functools

class BadSchemaFileError(Exception):
    pass

class QuickConf:
    """
    Abstraction layer around gconf.Client, providing several features:
     * Dictionary-like access to keys and transparent handling of their type.
     * Automatic prefixation of key names with their root path.
     * Support for specifying a default value in case a key is unset.
     * Support for asserting that the types of given values are correct, reading
       them from a .schemas file.
    """
    
    _root = None
    _schema = None
    _schema_strict = False
    _schema_strict_read = False
    
    _typemap = {
        int: 'int',
        str: 'string',
        bool: 'bool',
        float: 'float',
        list: 'list',
        tuple: 'list',
    }
    _typemap_inv = dict(zip(_typemap.values(), _typemap.keys()))
    
    def __init__(self, root=None, preload=None, gconf_client=None):
        self._gconf = gconf.Client() or gconf_client
        self._preload = preload or gconf.CLIENT_PRELOAD_RECURSIVE
        if root:
            self.set_root(root)
    
    # We give read-only access to the GConf Client instance in case users
    # need to access additional functionality.
    @property
    def gconf(self):
        """
        The `gconf.Client' instance internally used by QuickConf.
        """
        
        return self._gconf
    
    def _parse_schema_file(self, schema_file):
        """
        Parse the given .schema or .schema.in file. Return True if successful
        or false if the file can't be accessed.
        
        In case the file can't be parsed correctly, raise BadSchemaFileError.
        """
        
        from xml.dom.minidom import parse as parse_xml
        from xml.parsers.expat import ExpatError
        
        try:
            content = parse_xml(schema_file)
        except IOError:
            return False
        except ExpatError, e:
            raise BadSchemaFileError, e.message
        
        self._schema = {}
        try:
            for entry in content.getElementsByTagName('schema'):
                key = entry.getElementsByTagName('applyto')[0].childNodes[0].data
                if key in self._schema:
                    raise BadSchemaFileError, 'duplicate key: %s' % key
                type = entry.getElementsByTagName('type')[0].childNodes[0].data
                default = entry.getElementsByTagName('default')
                if default:
                    default = self._typemap_inv[type](default[0].childNodes[0].data)
                self._schema[key] = (type, default if default else None)
        except IndexError:
            raise BadSchemaFileError, \
                'missing "key" or "type" entry in <schema> node'
        
        return True
    
    def set_schema(self, *schema_files, **kwargs):
        """
        set_schema(schema_files...) -> None
        
        Parse the given .schema or .schema.in file and extract key names,
        types and default values from it.
        
        Type information will be used to perform conversions and ensure all
        keys get the right type. Default values will be returned when accessing
        an unset key, unless another default value is explicitly provided when
        accessing the key.
        
        The type checking can avoid problems with code such as the following:
         >>> conf['value'] = raw_input('Introduce a number:')
        Where "value" would get a string assigned instead of a number. Of
        course, the following code would be preferable:
         >>> conf['value'] = int(raw_input('Introduce a number:'))
        However, for convenience, QuickConf offers the possibility to handle
        this transparently when the required schemas are available.
        
        For further convenience, you can call this method passing several
        schema files as arguments. If this is done, set_schema will use the
        first of them which exists and is readable. In case none of them
        can be read, IOError will be raised, or in case a corrupt one is found,
        BadSchemaFileError.
        
        Additionally, if set_schema is called with the parameter "strict=True",
        trying to set a key not defined in the schema will raise a KeyError
        exception. If "strict_read=True" is used, the same will happen when
        trying to read a key not defined in the schema.
        """
        
        if 'strict_read' in kwargs and kwargs['strict_read']:
            self._schema_strict = self._schema_strict_read = True
        elif 'strict' in kwargs and kwargs['strict']:
            self._schema_strict = True
        
        # Parse the first existing file of those provided
        for filename in schema_files:
            if self._parse_schema_file(filename):
                return
        
        raise IOError, 'None of the provided .schema files could be read.'
    
    def set_root(self, root):
        """
        set_root(root) -> str
        
        Change the root path. Key names given to all other methods will
        be automatically prefixed with this path.
        """
        
        if self._root:
            self._gconf.remove_dir(self._root)
        self._root = root.rstrip('/')
        self._gconf.add_dir(self._root, self._preload)
    
    def get_root(self):
        """
        get_root() -> str
        
        Return the root path with which key names given in all other methods
        will be automatically prefixed.
        """
        
        return self._root
    
    def __getitem__(self, key):
        return self.get(key)
    
    def __setitem__(self, key, value):
        return self.set(key, value)
    
    def get_complete_path(self, key):
        """
        get_complete_path(key) -> str
        
        Return the complete GConf key name, after prefixing the given `key'
        with the root path specified when calling  `__init__()' or using
        `set_root()'.
        """
        
        return (self._root + '/' + key) if self._root else key
    
    # decorator
    def _normalize_key(method):
        @functools.wraps(method)
        def decorated(self, key, *args, **kwargs):
            return method(self, self.get_complete_path(key), *args, **kwargs)
        return decorated
    
    def _get_value(self, gconfvalue):
        value = getattr(gconfvalue, 'get_' + gconfvalue.type.value_nick)()
        if self._typemap[type(value)] == 'list':
            return [self._get_value(el) for el in value]
        return value
    
    @_normalize_key
    def get(self, key, default=None):
        """
        get(key, [default]) -> bool/str/int/float/list
        
        Return the value of the given key or, if the key is unset, the value
        given as `default'.
        
        In case you have specified a .schemas file with `set_schema()',
        QuickConf will try to look for a default value there if need.
        """
        
        gconfvalue = self._gconf.get(key)
        if not gconfvalue:
            if not default and self._schema:
                if key in self._schema:
                    return self._schema[key][1]
                elif self._schema_strict_read:
                    raise KeyError, \
                        'Reading key not defined in schema: %s' % key
            return default
        return self._get_value(gconfvalue)
    
    @_normalize_key
    def set(self, key, value):
        """
        set(key, value) -> None
        
        Assign the given value to the given key.
        """
        
        keytype = None
        if self._schema:
            if key in self._schema:
                keytype = self._schema[key][0]
                safe_value = self._typemap_inv[keytype](value)
            elif self._schema_strict:
                raise KeyError, 'Writing key not defined in schema: %s' % key
        if not keytype:
            keytype = self._typemap[type(value)]
            safe_value = value
        
        setter = getattr(self._gconf, 'set_' + keytype)
        if keytype == 'list':
            # TODO: How is this represented in .schemas?
            elemtype = self._typemap[type(value[0])].upper()
            setter(key, getattr(gconf, 'VALUE_' + elemtype), safe_value)
        else:
            setter(key, safe_value)
    
    @_normalize_key
    def connect(self, key, callback, *user_data):
        """
        connect(key, callback, [user_data...]) -> None
        
        Connect the given callback to change events of the given key.
        
        The callback method will receive the changed key and its value as
        parameters. If you need something else you can set it as user_data
        and you'll receive it aswell.
        """
        
        def cb(gconfclient, id, gconfentry, *user_data2):
            key = gconfentry.get_key()[len(self._root)+1:]
            value = self._get_value(gconfentry.get_value()) if \
                gconfentry.get_value() else None
            if user_data:
                callback(key, value, *user_data2)
            else:
                # Do not pass in user_data2, as GConf puts an useless
                # empty tuple there when there shouldn't be anything.
                callback(key, value)
        
        self._gconf.notify_add(key, cb, *user_data)
    
    @_normalize_key
    def remove_key(self, key):
        """
        remove_key(key) -> None
        
        Unset a GConf key.        
        """
        
        self._gconf.unset(key)
    
    @_normalize_key
    def remove_path(self, path):
        """
        remove_path(path) -> None
        
        Unset all GConf keys found in the given path.
        """
        
        self._gconf.recursive_unset(path.rstrip('/'),
            gconf.UNSET_INCLUDING_SCHEMA_NAMES)
