#  Copyright 2008-2012 Nokia Siemens Networks Oyj
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import wx
from robot.model import TagPatterns
from robotide.action import ActionInfo
from robotide.pluginapi import Plugin
from robotide.searchtests.dialogsearchtests import TestsDialog
from robotide.widgets import ImageProvider


class TestSearchPlugin(Plugin):
    """A plugin for searching tests based on name, tags and documentation"""
    HEADER = 'Search Tests'
    _selection = None

    def enable(self):
        self.register_action(ActionInfo('Tools', self.HEADER, self.show_empty_search, shortcut='F3', doc=self.__doc__,icon=ImageProvider().TEST_SEARCH_ICON,position=50))
        self.register_search_action(self.HEADER, self.show_search_for, ImageProvider().TEST_SEARCH_ICON, default=True)
        self._dialog = None

    def show_search_for(self, text):
        if self._dialog is None:
            self._create_tests_dialog()
        self._dialog.set_search_model(text, self._search_results(TestSearchMatcher(text)))
        self._dialog.set_focus_to_default_location()

    def show_search_for_tag_patterns(self, includes, excludes):
        matcher =  TagSearchMatcher(includes, excludes)
        self._dialog.set_tag_search_model(includes, excludes, self._search_results(matcher))
        self._dialog.set_focus_to_default_location()

    def _create_tests_dialog(self):
        self._dialog = TestsDialog(fuzzy_search_handler=self.show_search_for, tag_search_handler=self.show_search_for_tag_patterns)
        self._dialog.add_selection_listener(self._selected)
        self._dialog.Bind(wx.EVT_CLOSE, self._dialog_closed)
        self._selected_timer = wx.Timer(self._dialog)
        self._dialog.Bind(wx.EVT_TIMER, self._do_with_selection)
        self._dialog.Show()

    def _dialog_closed(self, event):
        self._dialog = None
        event.Skip()

    def show_empty_search(self, event):
        self.show_search_for('')

    def _do_with_selection(self, evt=None):
        test, match_location = self._selection
        self.tree.select_node_by_data(test)
        self._dialog.set_focus_to_default_location(test)

    def _selected(self, selection):
        self._selection = selection
        self._selected_timer.Start(400, True)

    def _search_results(self, matcher):
        current_suite = self.frame._controller.data
        if not current_suite:
            return []
        result = self._search(matcher, current_suite)
        return sorted(result, cmp=lambda x,y: cmp(x[1], y[1]))

    def _search(self, matcher, data):
        for test in data.tests:
            match = matcher.matches(test)
            if match:
                yield test, match
        for s in data.suites:
            for test, match in self._search(matcher, s):
                yield test, match


class TagSearchMatcher(object):

    def __init__(self, includes, excludes):
        self._tag_pattern_includes = TagPatterns(includes.split()) if includes.split() else None
        self._tag_pattern_excludes = TagPatterns(excludes.split())

    def matches(self, test):
        tags = [unicode(tag) for tag in test.tags]
        if self._matches(tags):
            return test.longname
        return False

    def _matches(self, tags):
        return (self._tag_pattern_includes is None or self._tag_pattern_includes.match(tags)) and \
               not self._tag_pattern_excludes.match(tags)


class TestSearchMatcher(object):

    def __init__(self, text):
        self._texts = text.split()
        self._texts_lower = [t.lower() for t in self._texts]

    def matches(self, test):
        if self._matches(test):
            return SearchResult(self._texts, self._texts_lower, test)
        return False

    def _matches(self, test):
        name = test.name.lower()
        if self._match_in(name):
            return True
        if any(self._match_in(unicode(tag).lower()) for tag in test.tags):
            return True
        doc = test.documentation.value.lower()
        if self._match_in(doc):
            return True
        return False

    def _match_in(self, text):
        return any(word in text for word in self._texts_lower)


class SearchResult(object):

    def __init__(self, original_search_terms, search_terms_lower, test):
        self._original_search_terms = original_search_terms
        self._search_terms_lower = search_terms_lower
        self._test = test
        self.__total_matches = None
        self.__tags = None

    def __cmp__(self, other):
        totals, other_totals = self._total_matches(), other._total_matches()
        if totals != other_totals:
            return cmp(other_totals, totals)
        names = self._compare(self._is_name_match(), other._is_name_match(), self._test.name, other._test.name)
        if names:
            return names
        tags = self._compare(self._is_tag_match(), other._is_tag_match(), self._tags(), other._tags())
        if tags:
            return tags
        return cmp(self._test.name, other._test.name)

    def _compare(self, my_result, other_result, my_comparable, other_comparable):
        if my_result and not other_result:
            return -1
        if not my_result and other_result:
            return 1
        if my_result and other_result:
            return cmp(my_comparable, other_comparable)
        return 0

    def _total_matches(self):
        if not self.__total_matches:
            self.__total_matches = sum(1 for word in self._search_terms_lower
                                        if word in self._test.name.lower()
                                        or any(word in t for t in self._tags())
                                        or word in self._test.documentation.value.lower())
        return self.__total_matches

    def _match_in(self, text):
        return any(word in text for word in self._search_terms_lower)

    def _is_name_match(self):
        return self._match_in(self._test.name.lower())

    def _is_tag_match(self):
        return any(self._match_in(t) for t in self._tags())

    def _tags(self):
        if self.__tags is None:
            self.__tags = [unicode(tag).lower() for tag in self._test.tags]
        return self.__tags

    def __repr__(self):
        return self._test.name
