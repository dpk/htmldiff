# -*- coding: utf-8 -*-

from lxml.html import fragment_fromstring
from lxml.etree import XPath
from difflib import SequenceMatcher
import itertools, re


## data / constants and default arguments

EmptyElements = {
  "area",
  "base",
  "br",
  "col",
  "menuitem",
  "embed",
  "hr",
  "img",
  "input",
  "isindex",
  "keygen",
  "link",
  "meta",
  "param",
  "source",
  "track",
  "wbr"
}
SignificantAttrs = {
  'a': {'href'},
  'img': {'src'}
}

def default_ins(text):
  return ('<ins class="diff">%s</ins>' % text)
def default_del(text):
  return ('<del class="diff">%s</del>' % text)


## public-facing functions

def html_diff(a, b, insertion=default_ins, deletion=default_del):
  aleaves, bleaves = (leaves(fragment_fromstring(x, create_parent='div')) for x in (a, b))
  dleaves = diffleaves(aleaves, bleaves)
  
  return leaves2html(dleaves, insertion, deletion)


## internal functions

def leaves(elt, parents=[]):
  leaflist = []
  def emit(content):
    leaflist.append(leaf(parents, content))
  
  lastwaselt = False
  for child in allchildren(elt):
    if isinstance(child, str):
      for word in allwords(child):
        emit(word)
      
      lastwaselt = False
    else:
      if lastwaselt:
        emit('')
      
      if child.tag in EmptyElements:
        emit(element(child))
      else:
        leaflist += leaves(child, parents + [element(child)])
        lastwaselt = True
  
  return leaflist

def diffleaves(aleaves, bleaves):
  def junkp(elt):
    assert isinstance(elt, leaf), 'tried to test junkiness of non-leaf'
    return isinstance(elt.content, str) and (len(elt.content) == 0 or elt.content.isspace())
  
  leaves = []
  diff = SequenceMatcher(a=aleaves, b=bleaves, autojunk=False, isjunk=junkp)
  for changetype, abeg, aend, bbeg, bend in diff.get_opcodes():
    if changetype == 'equal':
      leaves += aleaves[abeg:aend]
    elif changetype == 'delete':
      for adel in aleaves[abeg:aend]:
        adel.change = '-'
        leaves.append(adel)
    elif changetype == 'insert':
      for bins in bleaves[bbeg:bend]:
        bins.change = '+'
        leaves.append(bins)
    elif changetype == 'replace':
      for adel in aleaves[abeg:aend]:
        adel.change = '-'
        leaves.append(adel)
      for bins in bleaves[bbeg:bend]:
        bins.change = '+'
        leaves.append(bins)
  
  return leaves

def leaves2html(leaves, insertion, deletion):
  leaves = [leaf([], '')] + leaves + [leaf([], '')]
  source = ""
  for prev, dleaf in pairwise(leaves):
    keep, close, open = path_difference(prev.parents, dleaf.parents)
    for tag in reversed(close):
      source += tag.end_tag()
    for tag in open:
      source += tag.start_tag()
    
    if dleaf.change == '-':
      source += deletion(dleaf.content_html())
    elif dleaf.change == '+':
      source += insertion(dleaf.content_html())
    else:
      source += dleaf.content_html()
  
  return source


## classes

class element:
  def __init__(self, elt):
    self.name = elt.tag
    self.attrs = elt.attrib
    
  def start_tag(self):
    attrs = ''.join((' %s="%s"' % (name, html_attr(value))) for name, value in self.attrs.items())
    return '<%s%s>' % (self.name, attrs)
  
  def end_tag(self):
    return '</%s>' % self.name
  
  def significant_attrs(self):
    if self.name not in SignificantAttrs:
      return {}
    attrs = {}
    
    for name, value in self.attrs.items():
      if name in SignificantAttrs[self.name]:
        attrs[name] = value
    
    return attrs
  
  def __repr__(self):
    return "<%s %s>" % (self.name, self.attrs)
  
  def __hash__(self):
    return hash( ('element', self.name, tuple(self.significant_attrs().items())) )
  
  def __eq__(self, other):
    return self.name == other.name and self.significant_attrs() == other.significant_attrs()

class leaf:
  def __init__(self, parents, content, change=' '):
    self.parents = parents
    self.content = content
    self.change = change
  
  def content_html(self):
    if isinstance(self.content, str):
      return html(self.content)
    else:
      return self.content.start_tag()
  
  def __hash__(self):
    return hash( ('leaf', tuple(self.parents), self.content) )
  
  def __eq__(self, other):
    return self.parents == other.parents and self.content == other.content


## utilities

allchildren = XPath('self::*/* | self::*/text()') # lxml ſucks
wordre = re.compile(r'(\S+)')
def allwords(text):
  return [x for x in wordre.split(text) if len(x) != 0]

# i know, shut up
def html(text):
  return text.replace('&', '&amp;').replace('<', '&lt;')
def html_attr(text):
  return html(text).replace('"', '&quot;')

# http://stackoverflow.com/questions/5878403
def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)

# fixme: hacky
# sbp wrote a better version: http://swhack.com/logs/2013-03-17#T17-35-18
# but it returns iterators, which is not convenient
def path_difference(a, b):
 switch = False
 if len(a) > len(b):
   a, b = b, a
   switch = True
 
 sames = []
 lasti = -1
 for i, x in enumerate(a):
   if a[i] == b[i]:
     sames.append(x)
     lasti = i
   else:
     break
 
 if not switch:
   return (sames, a[lasti+1:], b[lasti+1:])
 else:
   return (sames, b[lasti+1:], a[lasti+1:])
