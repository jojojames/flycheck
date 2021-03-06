# Copyright (C) 2016 Sebastian Wiesner and Flycheck contributors

# This file is not part of GNU Emacs.

# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.

# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.

# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


from collections import namedtuple
from sphinx import addnodes
from sphinx.roles import XRefRole
from sphinx.domains import Domain, ObjType
from sphinx.util.nodes import make_refnode
from sphinx.directives import ObjectDescription


def make_target(cell, name):
    """Create a target name from ``cell`` and ``name``.

    ``cell`` is the name of a symbol cell, and ``name`` is a symbol name, both
    as strings.

    The target names are used as cross-reference targets for Sphinx.

    """
    return 'el-{cell}-{name}'.format(cell=cell, name=name)


def to_mode_name(symbol_name):
    """Convert ``symbol_name`` to a mode name.

    Split at ``-`` and titlecase each part.

    """
    return ' '.join(p.title() for p in symbol_name.split('-'))


class Cell(namedtuple('Cell', 'objtype docname')):
    """A cell in a symbol.

    A cell holds the object type and the document name of the description for
    the cell.

    Cell objects are used within symbol entries in the domain data.

    """
    pass


class KeySequence(namedtuple('KeySequence', 'keys')):
    """A key sequence."""

    PREFIX_KEYS = {'C-u'}
    PREFIX_KEYS.update('M-{}'.format(n) for n in range(10))

    @classmethod
    def fromstring(cls, s):
        return cls(s.split())

    @property
    def command_name(self):
        """The command name in this key sequence.

        Return ``None`` for key sequences that are no command invocations with
        ``M-x``.

        """
        try:
            return self.keys[self.keys.index('M-x')+1]
        except ValueError:
            return None

    @property
    def has_prefix(self):
        """Whether this key sequence has a prefix."""
        return self.keys[0] in self.PREFIX_KEYS

    def __str__(self):
        return ' '.join(self.keys)


class EmacsLispSymbol(ObjectDescription):
    """An abstract base class for directives documenting symbols.

    Provide target and index generation and registration of documented symbols
    within the domain data.

    Deriving classes must have a ``cell`` attribute which refers to the cell
    the documentation goes in, and a ``label`` attribute which provides a
    human-readable name for what is documented, used in the index entry.

    """

    cell_for_objtype = {
        'option': 'variable',
        'constant': 'variable',
        'variable': 'variable',
        'hook': 'variable',
        'face': 'face'
    }

    label_for_objtype = {
        'option': 'User option',
        'constant': 'Constant',
        'variable': 'Variable',
        'hook': 'Hook',
        'face': 'Face'
    }

    @property
    def cell(self):
        """The cell in which to store symbol metadata."""
        return self.cell_for_objtype[self.objtype]

    @property
    def label(self):
        """The label for the documented object type."""
        return self.label_for_objtype[self.objtype]

    def handle_signature(self, signature, signode):
        """Create nodes in ``signode`` for the ``signature``.

        ``signode`` is a docutils node to which to add the nodes, and
        ``signature`` is the symbol name.

        Add the object type label before the symbol name and return
        ``signature``.

        """
        label = self.label + ' '
        signode += addnodes.desc_annotation(label, label)
        signode += addnodes.desc_name(signature, signature)
        return signature

    def _add_index(self, name, target):
        index_text = '{name}; {label}'.format(
             name=name, label=self.label)
        self.indexnode['entries'].append(('pair', index_text, target, ''))

    def _add_target(self, name, sig, signode):
        target = make_target(self.cell, name)
        if target not in self.state.document.ids:
            signode['names'].append(name)
            signode['ids'].append(target)
            signode['first'] = (not self.names)
            self.state.document.note_explicit_target(signode)

            obarray = self.env.domaindata['el']['obarray']
            symbol = obarray.setdefault(name, {})
            if self.cell in symbol:
                self.state_machine.reporter.warning(
                    'duplicate description of %s %s, ' % (self.objtype, name) +
                    'other instance in ' +
                    self.env.doc2path(symbol[self.cell].docname),
                    line=self.lineno)
            symbol[self.cell] = Cell(self.objtype, self.env.docname)

        return target

    def add_target_and_index(self, name, sig, signode):
        target = self._add_target(name, sig, signode)
        self._add_index(name, target)


class EmacsLispMinorMode(EmacsLispSymbol):
    cell = 'function'
    label = 'Minor Mode'

    def handle_signature(self, signature, signode):
        """Create nodes in ``signode`` for the ``signature``.

        ``signode`` is a docutils node to which to add the nodes, and
        ``signature`` is the symbol name.

        Add the object type label before the symbol name and return
        ``signature``.

        """
        label = self.label + ' '
        signode += addnodes.desc_annotation(label, label)
        signode += addnodes.desc_name(signature, to_mode_name(signature))
        return signature

    def _add_index(self, name, target):
        return super()._add_index(to_mode_name(name), target)


class EmacsLispCommand(ObjectDescription):
    """A directive to document interactive commands via their bindings."""

    label = 'Interactive command'

    def handle_signature(self, signature, signode):
        """Create nodes to ``signode`` for ``signature``.

        ``signode`` is a docutils node to which to add the nodes, and
        ``signature`` is the symbol name.
        """
        key_sequence = KeySequence.fromstring(signature)
        signode += addnodes.desc_name(signature, str(key_sequence))
        return str(key_sequence)

    def _add_command_target_and_index(self, name, sig, signode):
        target_name = make_target('function', name)
        if target_name not in self.state.document.ids:
            signode['names'].append(name)
            signode['ids'].append(target_name)
            self.state.document.note_explicit_target(signode)

            obarray = self.env.domaindata['el']['obarray']
            symbol = obarray.setdefault(name, {})
            if 'function' in symbol:
                self.state_machine.reporter.warning(
                    'duplicate description of %s %s, ' % (self.objtype, name) +
                    'other instance in ' +
                    self.env.doc2path(symbol['function'].docname),
                    line=self.lineno)
            symbol['function'] = Cell(self.objtype, self.env.docname)

        index_text = '{name}; {label}'.format(name=name, label=self.label)
        self.indexnode['entries'].append(('pair', index_text, target_name, ''))

    def _add_binding_target_and_index(self, binding, sig, signode):
        reftarget = make_target('binding', binding)

        if reftarget not in self.state.document.ids:
            signode['names'].append(reftarget)
            signode['ids'].append(reftarget)
            signode['first'] = (not self.names)
            self.state.document.note_explicit_target(signode)

            keymap = self.env.domaindata['el']['keymap']
            if binding in keymap:
                self.state_machine.reporter.warning(
                    'duplicate description of binding %s, ' % binding +
                    'other instance in ' +
                    self.env.doc2path(keymap[binding]),
                    line=self.lineno)
            keymap[binding] = self.env.docname

        index_text = '{name}; key binding'.format(name=binding)
        self.indexnode['entries'].append(('pair', index_text, reftarget, ''))

    def add_target_and_index(self, name, sig, signode):
        # If unprefixed M-x command index as function and not as key binding
        sequence = KeySequence.fromstring(name)
        if sequence.command_name and not sequence.has_prefix:
            self._add_command_target_and_index(sequence.command_name,
                                               sig, signode)
        else:
            self._add_binding_target_and_index(name, sig, signode)


class XRefModeRole(XRefRole):
    """A role to cross-reference a minor mode.

    Like a normal cross-reference role but appends ``-mode`` to the reference
    target and title-cases the symbol name like Emacs does when referring to
    modes.

    """

    fix_parens = False
    lowercase = False

    def process_link(self, env, refnode, has_explicit_title, title, target):
        refnode['reftype'] = 'minor-mode'
        target = target + '-mode'
        return (title if has_explicit_title else to_mode_name(target), target)


class EmacsLispDomain(Domain):
    """A domain to document Emacs Lisp code."""

    name = 'el'
    label = 'Emacs Lisp'

    object_types = {
        # TODO: Set search prio for object types
        # Types for user-facing options and commands
        'minor-mode': ObjType('minor-mode', 'function', 'mode',
                              cell='function'),
        'binding': ObjType('binding', 'binding'),
        'command': ObjType('command', 'command', cell='command'),
        'option': ObjType('option', 'option', cell='variable'),
        'face': ObjType('face', 'face', cell='face'),
        # Object types for code
        'function': ObjType('function', 'function', cell='function'),
        'macro': ObjType('macro', 'macro', cell='function'),
        'variable': ObjType('variable', 'variable', cell='variable'),
        'constant': ObjType('constant', 'constant', cell='variable'),
        'hook': ObjType('hook', 'hook', cell='variable'),
    }
    directives = {
        'minor-mode': EmacsLispMinorMode,
        'command': EmacsLispCommand,
        'option': EmacsLispSymbol,
        'variable': EmacsLispSymbol,
        'constant': EmacsLispSymbol,
        'hook': EmacsLispSymbol,
        'face': EmacsLispSymbol
    }
    roles = {
        'mode': XRefModeRole(),
        'variable': XRefRole(),
        'constant': XRefRole(),
        'option': XRefRole(),
        'hook': XRefRole(),
        'face': XRefRole()
    }

    data_version = 1
    initial_data = {
        # Our domain data attempts to somewhat mirror the semantics of Emacs
        # Lisp, so we have an obarray which holds symbols which in turn have
        # function, variable, face, etc. cells, and a keymap which holds the
        # documentation for key bindings.
        'obarray': {},
        'keymap': {}
    }

    def clear_doc(self, docname):
        """Clear all cells documented ``docname``."""
        for symbol in self.data['obarray'].values():
            for cell in list(symbol.keys()):
                if docname == symbol[cell].docname:
                    del symbol[cell]
        for binding in list(self.data['keymap']):
            if self.data['keymap'][binding] == docname:
                del self.data['keymap'][binding]

    def resolve_xref(self, env, fromdocname, builder,
                     objtype, target, node, contnode):
        """Resolve a cross reference to ``target``."""
        if objtype == 'binding':
            todocname = self.data['keymap'].get(target)
            if not todocname:
                return None
            reftarget = make_target('binding', target)
        else:
            cell = self.object_types[objtype].attrs['cell']
            symbol = self.data['obarray'].get(target, {})
            if cell not in symbol:
                return None
            reftarget = make_target(cell, target)
            todocname = symbol[cell].docname

        return make_refnode(builder, fromdocname, todocname,
                            reftarget, contnode, target)

    def resolve_any_xref(self, env, fromdocname, builder,
                         target, node, contnode):
        """Return all possible cross references for ``target``."""
        nodes = ((objtype, self.resolve_xref(env, fromdocname, builder,
                                             objtype, target, node, contnode))
                 for objtype in ['binding', 'function', 'variable', 'face'])
        return [('el:{}'.format(objtype), node) for (objtype, node) in nodes
                if node is not None]

    def get_objects(self):
        """Get all documented symbols for use in the search index."""
        for name, symbol in self.data['obarray'].items():
            for cellname, cell in symbol.items():
                yield (name, name, cell.objtype, cell.docname,
                       make_target(cellname, name),
                       self.object_types[cell.objtype].attrs['searchprio'])


def setup(app):
    app.add_domain(EmacsLispDomain)
