# -*- encoding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
import os
import sys

import yaml
from six import iteritems
from flask import Config
from nds_lexicon.lexicon import DEFAULT_XPATHS
from functools import cmp_to_key

# Import configs stuff to register overrides
# from conf import *




def gettext_yaml_wrapper(loader, node):
    from flask_babel import lazy_gettext as _
    return node.value


yaml.add_constructor('!gettext', gettext_yaml_wrapper)

# This should match most language words, with few surprises, however it
# does not include the cases where a language uses a period or
# apostrophe within a word.

DEFAULT_WORD_REGEX = '[\u00C0-\u1FFF\u2C00-\uD7FF\w\-]+'
DEFAULT_WORD_REGEX_OPTS = 'g'


def external_korp_url(pair_details, user_input):
    try: 
        from urllib import quote
    except ImportError:
        from urllib.parse import quote

    from flask import redirect
    from flask import g

    #    'korp_parallel'

    #    'bilingual_wordform_search_path'
    #    'bilingual_wordform_search_query'
    # Cip's test
    # Add this line for testing
    korp_opts = pair_details.get('korp_options')
    korp_host = pair_details.get('korp_search_host')
    link_corpus_param = pair_details.get('link_corpus_parameter')

    # TODO: original pair, if current pair is variant
    if korp_opts.get('is_korp_default_lang'):
        url_pattern = korp_opts.get('wordform_search_path_default_lang')
    else:
        url_pattern = korp_opts.get('wordform_search_path').replace(
            'TARGET_LANG_ISO', g.orig_from)

    if korp_opts.get('korp_parallel'):
        url_pattern = korp_opts.get('bilingual_wordform_search_path').replace(
            'TARGET_LANG_ISO', g.orig_from)
        if g.orig_from == 'fin':
            url_pattern = url_pattern.replace('mode=parallel',
                                              'mode=parallel_fin')
        url_pattern = url_pattern.replace(
            'SEARCH_QUERY',
            quote(
                korp_opts.get('bilingual_wordform_search_query'), safe="#&/"))

    delimiter_pattern = korp_opts.get('lemma_multiword_delimeter')

    if ' ' in user_input and delimiter_pattern:
        user_input = delimiter_pattern.join(user_input.split(' '))

    try:
        user_input = user_input.encode("utf-8")
    except UnicodeError as e:
        print('Error in user_input:', e)

    try:
        url_pattern = url_pattern.encode("utf-8")
    except UnicodeError as e:
        print('Error in url_pattern:', e)

    url_pattern = url_pattern.replace('USER_INPUT', user_input)

    try:
        url_pattern = url_pattern.decode("utf-8")
    except UnicodeError as e:
        print('Error in url_pattern:', e)

    if len(link_corpus_param) != 0:
        url_pattern = url_pattern + '&corpus=' + link_corpus_param

    redirect_url = korp_host + url_pattern

    return redirect(redirect_url)


def validate_variants(variants, lexicon):
    if not variants:
        return variants
    obligatory_keys = set(['type', 'description', 'short_name'])
    optional_keys = set(['example', 'onscreen_keyboard'])
    variant_count = 1
    for v in variants:
        missing_keys = obligatory_keys - set(v.keys())
        if len(missing_keys) > 0:
            print("Missing settings in `input_variants`:%d for lexicon <%s>" % (
                variant_count, repr(lexicon)), file=sys.stderr)
            print("    " + ','.join(missing_keys), file=sys.stderr)
            sys.exit()
        variant_count += 1

    return variants


class Config(Config):
    """ An object for exposing the settings in app.config.yaml in a nice
    objecty way, and validating some of the contents.
    """

    @property
    def configs_path(self):
        """ Path to the configs/ dir """
        return self.get('NDS_CONFDIR')

    @property
    def language_specific_rules_path(self):
        """ Path to the language_specific_rules/ dir """
        return os.path.join(
            self.get('NDS_CONFDIR'), 'language_specific_rules/')

    @property
    def language_configs_yaml(self):
        if hasattr(self, '_language_configs_yaml'):
            return self._language_configs_yaml

        language_configs_path = os.path.join(
            self.get('NDS_CONFDIR'), 'language_names.yaml')
        with open(language_configs_path, 'r') as F:
            config = yaml.load(F)

        self._language_configs_yaml = config
        return self._language_configs_yaml

    @property
    def NAMES(self):
        return self.language_configs_yaml.get('isos_to_names', {})

    @property
    def LOCALISATION_NAMES_BY_LANGUAGE(self):
        return self.language_configs_yaml.get('isos_to_demonym', {})

    @property
    def ISO_DISPLAY_RELABELS(self):
        return self.language_configs_yaml.get('iso_display_relabels', {})

    @property
    def ISO_TRANSFORMS(self):
        return self.language_configs_yaml.get('iso_transforms', {})

    @property
    def default_language_pair(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('default_pair', False)
        if _p:
            return _p
        else:
            raise RuntimeError(
                'Default language pair not specified in '
                'config file %s, in ApplicationSettings.' % self.filename)

    @property
    def paradigm_layouts(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('paradigm_layouts', False)
        if _p:
            return _p

    # @property
    # def onscreen_keyboard(self):
    #     _p = self.yaml.get('ApplicationSettings', {})\
    #                   .get('onscreen_keyboard', False)
    #     return _p

    @property
    def locales_available(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('locales_available', False)
        if len(list(set(map(type, _p)))) > 1:
            err_str = "Type error in locales_available. If <no> is listed, make sure it is quoted."
            raise RuntimeError(
                err_str +
                'See config file %s, in ApplicationSettings.' % self.filename)

        if _p:
            return _p
        else:
            raise RuntimeError(
                'locales_available not specified in '
                'config file %s, in ApplicationSettings.' % self.filename)

    @property
    def hidden_locales(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('hidden_locales', [])
        if len(list(set(map(type, _p)))) > 1:
            err_str = "Type error in hidden_locales. If <no> is listed, make sure it is quoted."
            raise RuntimeError(
                err_str +
                'See config file %s, in ApplicationSettings.' % self.filename)

        return _p

    @property
    def app_name(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('app_name', u"Neahttadigisánit")
        if _p:
            return _p
        else:
            raise RuntimeError(
                'app_name not specified in '
                'config file %s, in ApplicationSettings.' % self.filename)

    @property
    def admins(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('admins_to_email', False)
        if _p:
            return _p
        else:
            return []

    @property
    def geoip_logging_enabled(self):
        """ Return our best guess assuming someone has followed the
        makefile otherwise allow override.
        """
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('GEOIP_LOGGING_ENABLED', False)

        if _p:
            try:
                with open(self.geoip_library_path, 'r') as F:
                    pass
            except IOError:
                print("Could not find GeoIP library, but geoip logging is enabled.", file=sys.stderr)
                print("Check that it is compiled at the following path:", file=sys.stderr)
                print("", file=sys.stderr)
                print("     %s" % self.geoip_library_path, file=sys.stderr)
                print("", file=sys.stderr)
                print("  ... or supply a different path with ApplicationSettings/GEOIP_LIBRARY_PATH", file=sys.stderr)
                print("  setting in relevant project .yaml file.", file=sys.stderr)
                print("", file=sys.stderr)
                print("See also: geo/README.md", file=sys.stderr)
                print("", file=sys.stderr)
                sys.exit()
        if _p:
            return _p
        else:
            return []

    @property
    def geoip_path(self):
        """ Return our best guess assuming someone has followed the
        makefile otherwise allow override.
        """
        default = os.path.join(os.path.dirname(__file__), 'geo/data')
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('GEOIP_PATH', default)
        if _p:
            return _p
        else:
            return []

    @property
    def geoip_library_path(self):
        """ Return our best guess assuming someone has followed the
        makefile otherwise allow override.
        """
        default = os.path.join(
            os.path.dirname(__file__), 'geoip/lib/libGeoIP.so')
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('GEOIP_LIBRARY_PATH', default)
        if _p:
            return _p
        else:
            return []

    @property
    def new_style_templates(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('new_style_templates', True)
        return _p

    @property
    def short_name(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('short_name', False)
        if _p:
            return _p
        else:
            raise RuntimeError(
                'short_name not specified in '
                'config file %s, in ApplicationSettings.' % self.filename)

    @property
    def default_locale(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('default_locale', False)
        if _p:
            return _p
        else:
            raise RuntimeError(
                'default_locale not specified in '
                'config file %s, in ApplicationSettings.' % self.filename)

    @property
    def meta_keywords(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('meta_keywords', False)
        if _p:
            return _p
        else:
            raise RuntimeError(
                'meta_keywords not specified in '
                'config file %s, in ApplicationSettings.' % self.filename)

    @property
    def has_project_css(self):
        if not hasattr(self, '_has_project_css'):
            project_css_path = False
            path = 'static/css/%s.css' % self.short_name
            try:
                open(os.path.join(os.path.dirname(__file__), path), 'r')
                project_css_path = path
            except:
                pass
            self._has_project_css = project_css_path
        return self._has_project_css

    @property
    def meta_description(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('meta_description', False)
        if _p:
            return _p
        else:
            raise RuntimeError(
                'meta_description not specified in '
                'config file %s, in ApplicationSettings.' % self.filename)

    @property
    def grouped_nav(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('grouped_nav', False)
        return _p

    @property
    def new_mobile_nav(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('new_mobile_nav', False)
        return _p

    @property
    def app_meta_title(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('app_meta_title', False)
        if _p:
            return _p
        else:
            raise RuntimeError(
                'app_meta_title not specified in '
                'config file %s, in ApplicationSettings.' % self.filename)

    @property
    def fcgi_script_path(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('fcgi_script_path', '')
        return _p

    @property
    def menu_flags(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('menu_flags', True)
        return _p

    @property
    def render_template_errors(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('render_template_errors', False)
        return _p

    @property
    def strip_spaces(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('strip_spaces', False)
        return _p

    @property
    def app_mobile_bookmark_name(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('mobile_bookmark_name', False)
        if _p:
            return _p
        else:
            return self.app_meta_title

    @property
    def polyglot_lookup(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('polyglot_lookup', False)
        return _p

    @property
    def mobile_redirect_pair(self):
        _p = self.yaml.get('ApplicationSettings', {})\
                      .get('mobile_default_pair', None)
        if _p is not None:
            return _p
        else:
            raise RuntimeError('Mobile redirect pair not specified in '
                               'config file %s, in ApplicationSettings.'
                               ' If none, specify with false.' % self.filename)

    @property
    def paradigms(self):
        if self._paradigms:
            return self._paradigms

        lang_paradigms = self.yaml.get('Paradigms', {})

        self._paradigms = lang_paradigms
        return self._paradigms

    @property
    def paradigm_contexts(self):
        """ This reads the `paradigms` directory and loads all of the
        paradigm files for languages active in dictionary set.
        """
        from collections import defaultdict

        if hasattr(self, '_paradigm_contexts'):
            return self._paradigm_contexts

        paradigm_path = os.path.join(self.language_specific_rules_path,
                                     'paradigms/')

        available_langs = self.languages

        lang_directories = [
            p for p in os.listdir(paradigm_path) if p in available_langs
        ]

        self._paradigm_contexts = defaultdict(dict)

        _lang_files = {}
        for lang in lang_directories:
            _lang_path = os.path.join(paradigm_path, lang)
            _lang_paradigm_files = []

            for _p, dirs, files in os.walk(_lang_path):
                for f in files:
                    if f.endswith('.context'):
                        _lang_paradigm_files.append(os.path.join(_p, f))

            _lang_files[lang] = _lang_paradigm_files

        jinja_env = self.get('jinja_env')

        def reformat_context_set(filepath, _sets):
            parsed_sets = {}
            if _sets is None:
                return {}

            for s in _sets:
                entry_c = s.get('entry_context', None)
                if entry_c == 'None':
                    entry_c = None

                tag_c = s.get('tag_context', None)
                if tag_c == 'None':
                    tag_c = None

                template = s.get('template')

                if tag_c is None:
                    print("Missing tag context in <%s>" % filepath, file=sys.stderr)

                parsed_sets[(entry_c, tag_c)] = jinja_env.from_string(template)
            return parsed_sets

        for language, files in iteritems(_lang_files):
            for f in files:
                tagset_path = os.path.join(_p, f)
                if os.path.exists(tagset_path):
                    try:
                        file_context_set = yaml.load(open(tagset_path, 'r').read())
                    except Exception as e:
                        print(" * YAML parsing error in <%s>\n\n" % tagset_path)
                        print(e)
                        sys.exit()
                    self._paradigm_contexts[language].update(
                        reformat_context_set(tagset_path, file_context_set))

        return self._paradigm_contexts

    @property
    def reversable_dictionaries(self):
        if self._reversable_dictionaries:
            return self._reversable_dictionaries

        def isReversable(d):
            if d.get('reversable', False):
                return d

        dicts = filter(isReversable, self.yaml.get('Dictionaries'))
        language_pairs = {}
        for item in dicts:
            source = item.get('source')
            target = item.get('target')
            path = item.get('path')
            language_pairs[(source, target)] = path

        self._reversable_dictionaries = language_pairs
        return language_pairs

    @property
    def languages(self):
        if not self._languages:
            self._languages = {}
            for lang in self.yaml.get('Languages'):
                self._languages[lang.get('iso')] = lang.get('name', {})

            # Add variants to languages if they're missing.
            for iso in self.yaml.get('Morphology').keys():
                if iso not in self._languages.keys():
                    self._languages[iso] = {'iso': iso}
        return self._languages

    @property
    def minority_languages(self):
        if not hasattr(self, '_minority_languages'):
            self._minority_languages = {}
            for lang in self.yaml.get('Languages'):
                if lang.get('minority_lang', False):
                    self._minority_languages[lang.get('iso')] = lang.get(
                        'name', {})
        return self._minority_languages

    @property
    def unittests(self):
        if not hasattr(self, '_unittests'):
            self._unittests = []
            for t in self.yaml.get('UnitTests', []):
                self._unittests.append(t)
        return self._unittests

    @property
    def variant_dictionaries(self):
        from collections import OrderedDict
        if hasattr(self, '_variant_dictionaries'):
            return self._variant_dictionaries

        dicts = self.yaml.get('Dictionaries')
        language_pairs = OrderedDict()
        for item in dicts:
            source = item.get('source')
            target = item.get('target')
            path = item.get('path')
            variants = item.get('input_variants')
            if variants:
                for v in variants:
                    path = v.get('path', item.get('path'))
                    target_variant = v.get('display_variant', False)
                    if not target_variant:
                        if v.get('short_name') != source:
                            language_pairs[(v.get('short_name'), target)] = {
                                'orig_pair': (source, target),
                                'path': path,
                            }
                    else:
                        if v.get('short_name') != target:
                            language_pairs[(source, v.get('short_name'))] = {
                                'orig_pair': (source, target),
                                'path': path,
                            }

        self._variant_dictionaries = language_pairs
        return language_pairs

    @property
    def input_variants(self):
        from collections import OrderedDict
        if self._input_variants:
            return self._input_variants

        dicts = self.yaml.get('Dictionaries')
        language_pairs = OrderedDict()
        for item in dicts:
            source = item.get('source')
            target = item.get('target')
            input_variants = item.get('input_variants', False)
            if input_variants:
                language_pairs[(source, target)] = input_variants

        self._input_variants = language_pairs
        return language_pairs

    @property
    def search_variants(self):
        from collections import OrderedDict
        if hasattr(self, '_search_variants'):
            return self._search_variants

        dicts = self.yaml.get('Dictionaries')
        language_pairs = OrderedDict()
        for item in dicts:
            source = item.get('source')
            target = item.get('target')
            input_variants = item.get('search_variants', False)
            if input_variants:
                language_pairs[(source, target)] = input_variants

        self._search_variants = language_pairs
        return language_pairs

    @property
    def dictionaries(self):
        from collections import OrderedDict
        if self._dictionaries:
            return self._dictionaries

        dicts = self.yaml.get('Dictionaries')
        language_pairs = OrderedDict()
        for item in dicts:
            source = item.get('source')
            target = item.get('target')
            path = item.get('path')
            language_pairs[(source, target)] = path

        self._dictionaries = language_pairs
        return language_pairs

    @property
    def dictionary_options(self):
        from collections import defaultdict
        if hasattr(self, '_dictionary_options'):
            return self._dictionary_options

        dicts = self.yaml.get('Dictionaries')
        opts = defaultdict(dict)
        for item in dicts:
            source = item.get('source')
            target = item.get('target')
            lexicon_options = DEFAULT_XPATHS.copy()
            lexicon_options.update(**item.get('options', {}))
            opts[(source, target)] = lexicon_options

        self._dictionary_options = opts
        return opts

    @property
    def tag_filters(self):
        """ Reads the `tagsets` directory for tagsets active in the
        dictionary set.
        """
        if hasattr(self, '_tag_filters'):
            return self._tag_filters

        _path = os.path.join(self.language_specific_rules_path,
                             'user_friendly_tags/')

        available_langs = self.languages

        filter_sets = {}

        def format_yaml(_yaml):
            _yaml_sets = {}
            for _set in _yaml.get('Relabel'):
                source = _set.get('source_morphology')
                target = _set.get('target_ui_language')

                _set.pop('source_morphology')
                _set.pop('target_ui_language')

                # TODO: raise error if missing 'tags'?

                # iterate through sets and set them.
                for set_name, set_tags in iteritems(_set):
                    if source in self.languages.keys(
                    ) and target in self.languages.keys():
                        if set_name == 'generation_tags':
                            _yaml_sets[(source, target,
                                        'generation')] = set_tags
                        elif set_name == 'tags':
                            _yaml_sets[(source, target)] = set_tags
                        else:
                            _yaml_sets[(source, target, set_name)] = set_tags
            return _yaml_sets

        for _p, dirs, files in os.walk(_path):
            for f in files:
                if f.endswith('.relabel'):
                    print(" * Reading tagset in <%s> " % f)
                    relabel_path = os.path.join(_p, f)
                    try:
                        relabel_yaml = format_yaml(
                            yaml.load(open(relabel_path, 'r').read()))
                    except Exception as e:
                        print(" * YAML parsing error in <%s>\n\n" % relabel_path)
                        print(e)
                        sys.exit()
                    filter_sets.update(relabel_yaml)
                    print("   - found: " + ', '.join(
                        [k[0] + ' -> ' + k[1] for k in relabel_yaml.keys()]))

        self._tag_filters = filter_sets
        return self._tag_filters

    @property
    def tagset_definitions(self):
        """ Reads the `tagsets` directory for tagsets active in the
        dictionary set.
        """
        if self._tagset_definitions:
            return self._tagset_definitions

        tagset_path = os.path.join(self.language_specific_rules_path,
                                   'tagsets/')

        available_langs = self.languages

        sets = {}

        for _p, dirs, files in os.walk(tagset_path):
            for f in files:
                if f.endswith('.tagset'):
                    language = f.partition('.')[0]
                    tagset_path = os.path.join(_p, f)
                    try:
                        tagset_yaml = yaml.load(open(tagset_path, 'r').read())
                    except Exception as e:
                        print(" * YAML parsing error in <%s>\n\n" % tagset_path)
                        print(e)
                        sys.exit()
                    sets[language] = tagset_yaml

        self._tagset_definitions = sets
        return sets

    @property
    def pair_definitions(self):
        from collections import OrderedDict

        if not self._pair_definitions:
            self._pair_definitions = OrderedDict()
            _par_defs = {}
            for dict_def in self.yaml.get('Dictionaries'):
                _from, _to = dict_def.get('source'), dict_def.get('target')
                key = (_from, _to)
                _from_langs = self.languages[_from]
                _to_langs = self.languages[_to]
                _lang_isos = set(_from_langs.keys()) & set(_to_langs.keys())

                _missing = set(_from_langs.keys()) ^ set(_to_langs.keys())
                if _missing:
                    print("Missing some name translations for", file=sys.stderr)
                    print(', '.join(list(_missing)), file=sys.stderr)
                    print("Check Languages in app.config.yaml", file=sys.stderr)
                    sys.exit()

                _default_korp = {
                    'lemma_search_path':
                    '/?mode=TARGET_LANG_ISO#page=0&search-tab=2&search=SEARCH_QUERY',
                    'lemma_search_path_default_lang':
                    '/#page=0&search-tab=2&search=SEARCH_QUERY',
                    'lemma_search_query':
                    'cqp|[lemma = "INPUT_LEMMA"]',
                    'wordform_search_path':
                    '/?mode=TARGET_LANG_ISO#search=word|USER_INPUT&page=0',
                    'wordform_search_path_default_lang':
                    '/#search=word|USER_INPUT&page=0',
                    'bilingual_wordform_search_path':
                    '/?mode=parallel#parallel_corpora=TARGET_LANG_ISO&page=0&search=SEARCH_QUERY',
                    'bilingual_wordform_search_query':
                    'cqp|[(word = "USER_INPUT")]',
                    'lemma_search_delimiter':
                    '] [lemma = ',
                    'is_korp_default_lang':
                    dict_def.get('is_korp_default_lang', False),
                    'korp_parallel':
                    dict_def.get('korp_parallel', False),
                    'corpora':
                    dict_def.get('corpora', False),
                    'start_query':
                    dict_def.get('start_query', False),
                }

                _pair_options = {
                    'langs': {},
                    'autocomplete':
                    dict_def.get('autocomplete', True),
                    'show_korp_search':
                    dict_def.get('show_korp_search', False),
                    'korp_search_host':
                    dict_def.get('korp_search_host', False),
                    'korp_options':
                    dict_def.get('korp_options', _default_korp),
                    'asynchronous_paradigms':
                    dict_def.get('asynchronous_paradigms', False),
                    'link_corpus_parameter':
                    dict_def.get('link_corpus_parameter', ''),
                }
                for iso in _lang_isos:
                    _pair_options['langs'][iso] = (_from_langs[iso],
                                                   _to_langs[iso])

                _pair_options['input_variants'] = validate_variants(
                    self.input_variants.get(key, False), key)
                _pair_options['search_variants'] = self.search_variants.get(
                    key, False)

                if _from == 'fin':
                    korp_opts = _pair_options.get('korp_options')
                    korp_opts['bilingual_wordform_search_path'] = korp_opts.get('bilingual_wordform_search_path').replace('mode=parallel', 'mode=parallel_fin').replace('parallel_corpora', 'parallel_fin_corpora')

                _par_defs[key] = _pair_options

            for k, v in iteritems(self.dictionaries):
                self._pair_definitions[k] = _par_defs[k]

        return self._pair_definitions

    def pair_definitions_grouped_source_locale(self):
        from itertools import groupby
        from collections import defaultdict, OrderedDict

        from flask_babel import get_locale
        locale = get_locale()

        NAMES = self.NAMES

        # TODO: cache list by locale

        def group_by_source_first(dict):
            """ Return the source and target.
            """
            ((source, target), pair_options) = dict
            return (source, target)

        def minority_langs_first(dict_a, dict_b):
            """ This is the cmp function, which accepts two ISO pairs
            and returns -1, 0, or 1 to sort the values depending on a few criteria:

                * are the source languages both marked as minority langs?
                * are the source languages both *not* marked as minority langs?

                 -> sort them as normal

                * is one of the source langs marked as a minority lang?

                 -> return the minority language first

            Then... Also sort by the target languages, so each grouping
            is still alphabetical. """
            ((a_source_iso, a_target_iso), pair_options) = dict_a
            ((b_source_iso, b_target_iso), pair_options) = dict_b
            a_min = a_source_iso in self.minority_languages
            b_min = b_source_iso in self.minority_languages

            def error_string(iso):
                return("The name corresponding to iso {} is missing from language_names.yaml".format(iso))

            # TODO: Also sort reverse pairs together somehow.
            reverse_pairs = ((a_source_iso, a_target_iso) == (b_target_iso, b_source_iso)) or \
                            ((a_target_iso, a_source_iso) == (b_source_iso, b_target_iso))

            a_source_name = NAMES.get(a_source_iso)
            if a_source_name is None:
                raise NameError(error_string(a_source_iso))
            b_source_name = NAMES.get(b_source_iso)
            if b_source_name is None:
                raise NameError(error_string(b_source_iso))

            a_target_name = NAMES.get(a_target_iso)
            if a_target_name is None:
                raise NameError(error_string(a_target_iso))
            b_target_name = NAMES.get(b_target_iso)
            if b_target_name is None:
                raise NameError(error_string(b_target_iso))

            def gt_return(a, b):
                if a > b: return -2
                elif a < b: return 2
                else: return 0

            def gt_return_reverse(a, b):
                if a > b: return 2
                elif a < b: return -2
                else: return 0

            if reverse_pairs:
                return 0

            if a_source_iso == b_source_iso:
                return gt_return_reverse(a_target_name, b_target_name)

            # cases of equal status
            if (a_min and b_min) or (not a_min and not b_min):
                return gt_return(a_source_name, b_source_name)

            # one is a minority lang, and one is not
            if a_min and not b_min:
                return -2
            if b_min and not a_min:
                return 2

        if not hasattr(self, '_pair_definitions_grouped_source'):

            pairs = sorted(
                self.pair_definitions.items(),
                key=group_by_source_first)
            pairs = sorted(
                pairs,
                key=cmp_to_key(minority_langs_first))

            grouped_pairs = defaultdict(list)
            for p in pairs:
                if p[0][0] in self.minority_languages:
                    grouped_pairs[p[0][0]].append(p)
                if p[0][1] in self.minority_languages:
                    grouped_pairs[p[0][1]].append(p)
                if (p[0][0] not in self.minority_languages) and (p[0][1] not in self.minority_languages):
                    grouped_pairs[p[0][0]].append(p)
                    grouped_pairs[p[0][1]].append(p)
            # sort by alphabetical order of language name

            def lang_name(n):
                return NAMES.get(n)

            grouped_pairs_name_order = OrderedDict()
            for k in sorted(grouped_pairs.keys(), key=lang_name):
                if not k == 'fin':
                    grouped_pairs_name_order[k] = grouped_pairs[k]

            self._pair_definitions_grouped_source = grouped_pairs_name_order

        return self._pair_definitions_grouped_source

    @property
    def morphologies(self):
        if self._morphologies:
            return self._morphologies

        self._morphologies = {}

        from morphology import XFST, OBT, Morphology, HFST
        morph_cache = self.get('cache', False)

        formats = {
            'xfst': XFST,
            'hfst': HFST,
            'obt': OBT,
        }

        for iso, _kwargs_in in iteritems(self.yaml.get('Morphology')):
            conf_format = _kwargs_in.get('format', False)
            kwargs = {}

            if not conf_format:
                print("No format specified")
                sys.exit()

            m_format = formats.get(conf_format, False)
            if not m_format:
                print("Undefined format")
                sys.exit()

            if 'tool' in _kwargs_in:
                if isinstance(_kwargs_in['tool'], list):
                    _kwt = ''.join(_kwargs_in['tool'])
                else:
                    _kwt = _kwargs_in['tool']
                kwargs['lookup_tool'] = _kwt
            else:
                print("Lookup tool missing")
                sys.exit()

            if 'file' in _kwargs_in:
                if isinstance(_kwargs_in['file'], list):
                    _kwf = ''.join(_kwargs_in['file'])
                else:
                    _kwf = _kwargs_in['file']
                kwargs['fst_file'] = _kwf

            if 'inverse_file' in _kwargs_in:
                if isinstance(_kwargs_in['inverse_file'], list):
                    _kwfi = ''.join(_kwargs_in['inverse_file'])
                else:
                    _kwfi = _kwargs_in['inverse_file']
                kwargs['ifst_file'] = _kwfi

            if 'options' in _kwargs_in:
                kwargs['options'] = _kwargs_in['options']

            tagsets = self.tagset_definitions.get(iso, {})

            self._morphologies[iso] = \
                m_format(**kwargs).applyMorph(Morphology( iso
                                                        , cache=morph_cache
                                                        , tagsets=tagsets
                                                        )
                                             )

        return self._morphologies

    def test(self, silent=False):
        for item in dir(self):
            if not item.startswith('_') and item != 'test':
                if silent:
                    self.__getattribute__(item)
                else:
                    print(item)
                    print(self.__getattribute__(item))

    def from_envvar(self, variable_name, silent=False):
        """Loads a configuration from an environment variable pointing to
        a configuration file. This is basically just a shortcut with nicer
        error messages for this line of code::

        app.config.from_pyfile(os.environ['YOURAPPLICATION_SETTINGS'])

        :param variable_name: name of the environment variable
        :param silent: set to `True` if you want silent failure for missing
        files.
        :return: bool. `True` if able to load config, `False` otherwise.
        """
        import os
        rv = os.environ.get(variable_name)
        if not rv:
            raise RuntimeError('The environment variable %r is not set '
                               'and as such configuration could not be '
                               'loaded. Set this variable and make it '
                               'point to a configuration file' % variable_name)
        return self.from_yamlfile(rv, silent=silent)

    def read_multiword_list(self, path):
        """ Read the user-specified MWE list.
        """

        try:
            with open(os.path.join(os.path.dirname(__file__), path), 'r') as F:
                lines = F.readlines()
        except Exception as e:
            print(" * Unable to find multiword_list <%s>" % path)
            print(e)
            sys.exit()

        def drop_line_comment(l):
            if not l.startswith('#'):
                return True
            return False

        def strip_line_end_comment(l):
            line, _, comment = l.partition('#')
            return line

        def clean_line(l):
            _l = l.strip()
            if _l:
                return _l

        multiword_list = [l.strip() for l in lines if l.strip()]

        # Couldn't help myself.
        return list(map(strip_line_end_comment,
                   list(filter(drop_line_comment, list(map(clean_line, multiword_list))))))

    @property
    def reader_options(self):
        # TODO: apply defaults if nonexistent.

        if not hasattr(self, '_reader_options'):
            self._reader_options = self.yaml.get('ReaderConfig', {})

            try:
                self.reader_settings = self._reader_options.pop('Settings')
            except KeyError:
                self.reader_settings = {}

            reader_defaults = {
                'word_regex': DEFAULT_WORD_REGEX,
                'word_regex_opts': DEFAULT_WORD_REGEX_OPTS,
                'multiword_lookups': False,
            }

            for l, conf in iteritems(self._reader_options):
                wr = conf.get('word_regex', False)
                wro = conf.get('word_regex_opts', False)
                if wr:
                    self._reader_options[l]['word_regex'] = wr.strip()
                else:
                    self._reader_options[l][
                        'word_regex_opts'] = DEFAULT_WORD_REGEX
                if wro:
                    self._reader_options[l]['word_regex_opts'] = wro.strip()
                else:
                    self._reader_options[l][
                        'word_regex_opts'] = DEFAULT_WORD_REGEX_OPTS
                mwe = conf.get('multiword_lookups', False)
                mwe_range = conf.get('multiword_range', False)
                if mwe_range:
                    _min, _, _max = mwe_range.partition(',')
                    try:
                        _min = int(_min.strip().replace('-', ''))
                    except Exception as e:
                        _min = False

                    try:
                        _max = int(_max.strip().replace('+', ''))
                    except Exception as e:
                        _max = False

                    if _min and _max:
                        self._reader_options[l]['multiword_range'] = (_min,
                                                                      _max)
                    else:
                        print(" * Multiword range must specify min _and_ max. If there is no min or max, specify 0")
                        print("   got: " + mwe_range)
                        print("   expecting:")
                        print('    multiword_range: "-2,+2"')
                        print('  or ')
                        print('    multiword_range: "0,+2"')
                        print(e)
                        sys.exit()
                # mwe_l = conf.get('multiword_list', False)
                # if mwe and mwe_l:
                #     is_file = mwe_l.get('file', False)
                #     if is_file:
                #         self._reader_options[l]['multiwords'] = self.read_multiword_list(is_file)

            all_isos = list(
                set(list(self.languages.keys()) +
                    list(self.yaml.get('Morphology').keys())))
            missing_isos = [
                a for a in all_isos if a not in self._reader_options.keys()
            ]

            for l in missing_isos:
                self._reader_options[l] = reader_defaults

        return self._reader_options

    def from_yamlfile(self, filename, silent=False):
        self._languages = False
        self._pair_definitions = False
        self._dictionaries = False
        self._input_variants = False
        self._tagset_definitions = False
        self._reversable_dictionaries = False
        self._paradigms = False
        self._baseforms = False
        self._morphologies = False

        with open(filename, 'r') as F:
            config = yaml.load(F)
        self.yaml = config
        self.filename = filename
        self.test(silent=True)
        # Prepare lexica

        return True

    def add_optional_routes(self):
        from nds_lexicon import lexicon_overrides as lexicon

        # add korp_routes
        korp_pairs = [
            pair for pair, conf in iteritems(self.pair_definitions)
            if conf.get('show_korp_search', False)
        ]

        searches = [tuple(['korp_wordform'] + list(p)) for p in korp_pairs]

        lexicon.external_search(*searches)(external_korp_url)

    def prepare_lexica(self):
        from nds_lexicon import Lexicon
        self.lexicon = Lexicon(self)
        self.tag_filters

    def resolve_original_pair(self, _from, _to):
        """ For a language pair alternate, return the original language pair
        that is the parent to the alternate.

        TODO: write tests.
        """
        from flask import request

        # mobile test for most common browsers
        mobile = False
        if request.user_agent.platform in ['iphone', 'android']:
            mobile = True

        iphone = False
        if request.user_agent.platform == 'iphone':
            iphone = True

        # Variables to control presentation based on variants present
        current_pair = self.pair_definitions.get((_from, _to), {})
        reverse_pair = self.pair_definitions.get((_to, _from), {})

        swap_from, swap_to = (_to, _from)

        current_pair_variants = current_pair.get('input_variants', False)
        has_variant = bool(current_pair_variants)
        has_mobile_variant = False

        if has_variant:
            _mobile_variants = list(filter(lambda x: x.get('type', '') == 'mobile',
                                      current_pair_variants))
            if len(_mobile_variants) > 0:
                has_mobile_variant = _mobile_variants[0]

        variant_dictionaries = self.variant_dictionaries
        is_variant, orig_pair = False, ()

        if variant_dictionaries:
            variant = variant_dictionaries.get((_from, _to), False)
            is_variant = bool(variant)
            if is_variant:
                orig_pair = variant.get('orig_pair')

        # Now we check if the reverse has variants for swapping
        # If there is a reverse pair with variants, get the mobile one as a
        # preference for swapping if the user is a mobile user, otherwise
        # just the default.

        reverse_has_variant = False
        if is_variant:
            _reverse_is_variant = self.variant_dictionaries.get(
                orig_pair, False)
            pair_settings = self.pair_definitions[orig_pair]
        else:
            _reverse_is_variant = self.variant_dictionaries.get((_to, _from),
                                                                False)
            pair_settings = self.pair_definitions.get((_from, _to), False)

        _reverse_variants = reverse_pair.get('input_variants', False)

        if _reverse_variants:
            _mobile_variants = list(filter(lambda x: x.get('type', '') == 'mobile',
                                      _reverse_variants))
            _standard_variants = list(filter(
                lambda x: x.get('type', '') == 'standard', _reverse_variants))
            if mobile and len(_mobile_variants) > 0:
                _preferred_swap = _mobile_variants[0]
                _short_name = _preferred_swap.get('short_name')
                swap_from = _short_name
        else:
            if is_variant:
                swap_to, swap_from = orig_pair

        # Get the description and such for the variaint in the
        # original definition

        variant_options = False
        if is_variant:
            orig_pair_variants = pair_settings.get('input_variants')
            variant_opts = list(filter( lambda x: x.get('short_name') == _from and not x.get('display_variant', False)
                                 , orig_pair_variants
                                 ))
            if len(variant_opts) > 0:
                variant_options = variant_opts[0]

            d_variant_opts = list(filter( lambda x: x.get('short_name') == _to and x.get('display_variant', False)
                                   , orig_pair_variants
                                   ))
            if len(d_variant_opts) > 0:
                variant_options = d_variant_opts[0]

        else:
            if pair_settings:
                orig_pair_variants = pair_settings.get('input_variants')
                if orig_pair_variants:
                    variant_opts = list(filter(
                        lambda x: x.get('short_name') == _from,
                        orig_pair_variants))
                    if len(variant_opts) > 0:
                        variant_options = variant_opts[0]

        pair_opts = {
            'has_mobile_variant': has_mobile_variant,
            'has_variant': has_variant,
            'is_variant': is_variant,
            'variant_options': variant_options,
            'orig_pair': orig_pair,
            'swap_to': swap_to,
            'swap_from': swap_from
        }
        return pair_settings, pair_opts
