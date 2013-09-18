
from lexicon import lexicon_overrides
from morphology.utils import tagfilter
from utils.data import flatten
from flask import current_app

class EntryNodeIterator(object):
    """ A class for iterating through the result of an LXML XPath query,
    while cleaning the nodes into a more usable format.

    .clean() is where most of the magic happens, so if new formats are
    needed, just override this.

    """

    def l_node(self, entry):
        l = entry.find('lg/l')
        lemma = l.text
        pos = l.get('pos')
        context = l.get('context')
        type = l.get('type')
        hid = l.get('hid')
        if context == None:
            context = False
        if type == None:
            type = False
        if hid == None:
            hid = False

        return lemma, pos, context, type, hid

    def tg_nodes(self, entry):
        """ Select <tg /> nodes. If an entry has <tg /> nodes marked
        with xml:lang attributes, then return only the entries matching
        the target_lang, otherwise, if there are no xml:lang attributes
        on any of the <tg /> nodes, then return all entries unfiltered.
        """
        # how to detect multi-format? problem is that behavior between
        # pair format may be disrupted by disallowing fallback?
        target_lang = self.query_kwargs.get('target_lang', False)

        if not target_lang:
            multi = False
        else:
            multi = len(entry.xpath("mg/tg/@xml:lang")) > 0 and True or False

        if multi:
            ts = entry.xpath("mg/tg[@xml:lang='%s']/t" % target_lang)
            tgs = entry.xpath("mg/tg[@xml:lang='%s']" % target_lang)
        else:
            ts = entry.findall('mg/tg/t')
            tgs = entry.findall('mg/tg')

        return tgs, ts

    def examples(self, tg):
        _ex = []

        possible_errors = False
        for xg in tg.findall('xg'):
            _x = xg.find('x')
            _xt = xg.find('xt')

            if _x is not None and hasattr(_x, 'text'):
                _x_tx = _x.text
            else:
                _x_tx = ''
                possible_errors = True

            if _xt is not None and hasattr(_xt, 'text'):
                _xt_tx = _xt.text
            else:
                _xt_tx = ''
                possible_errors = True

            _ex.append((_x_tx, _xt_tx))

        if possible_errors:
            from lxml import etree
            error_xml = etree.tostring(tg, pretty_print=True, encoding="utf-8")
            current_app.logger.error(
                "Potential XML formatting problem on <xg /> node\n\n%s" % error_xml.strip()
            )

        if len(_ex) == 0:
            return False
        else:
            return _ex

    def find_translation_text(self, tg):
        """ This parses a <tg /> node and returns text, annotations, xml:lang.

        Annotations means here: tg/re, tg/te, or tg/tf. If there is no
        <t /> node, we try to fall back to using one of these,
        otherwise, pick the <t /> node and use the annotations as
        definition.
        """

        def orFalse(l):
            if len(l) > 0:
                return l[0]
            else:
                return False

        text = False
        re = tg.find('re')
        te = tg.find('te')
        tf = tg.find('tf')

        te_text = ''
        re_text = ''
        tf_text = ''

        if te is not None:      te_text = te.text
        if re is not None:      re_text = re.text
        if tf is not None:      tf_text = tf.text

        tx = tg.findall('t')

        link = True

        if not tx:
            if te_text:
                text, te_text = [te_text], ''
            elif re_text:
                text, re_text = [re_text], ''
            elif tf_text:
                text, tf_text = [tf_text], ''
        else:
            text = [_tx.text for _tx in tx if _tx.text is not None]

        lang = tg.xpath('@xml:lang')

        annotations = []
        for a in [te_text, re_text, tf_text]:
            if a is not None:
                if a.strip():
                    annotations.append(a)

        return text, annotations, lang

    def __init__(self, nodes, *query_args, **query_kwargs):
        if not nodes or len(nodes) == 0:
            self.nodes = []
        else:
            self.nodes = nodes
        self.query_args = query_args
        self.query_kwargs = query_kwargs

    def __iter__(self):
        from lxml import etree
        for node in self.nodes:
            try:
                yield self.clean(node)
            except Exception, e:
                import traceback
                import sys
                exc_type, exc_value, exc_traceback = sys.exc_info()
                tb_str = traceback.format_exception(exc_type, exc_value, exc_traceback)
                error_xml = etree.tostring(node, pretty_print=True, encoding="utf-8")
                current_app.logger.error(
                    "Potential XML formatting problem somewhere in... \n\n%s\n\n%s" % (error_xml.strip(), ''.join(tb_str))
                )
                continue


class SimpleJSON(EntryNodeIterator):
    """ A simple JSON-ready format for /lookups/
    """

    def clean(self, e):
        lemma, lemma_pos, lemma_context, _, lemma_hid = self.l_node(e)
        tgs, ts = self.tg_nodes(e)

        # TODO: format source in JSON view
        target_formatteds = []
        right_langs = []
        translations = []
        for tg in tgs:
            default_text, default_annotations, default_lang = self.find_translation_text(tg)
            tf_text = lexicon_overrides.format_target(
                self.query_kwargs.get('source_lang'), self.query_kwargs.get('target_lang'),
                self.query_kwargs.get('ui_lang'), e, tg, False
            )
            if tf_text:
                default_lang.append(default_lang)
                target_formatteds.append(tf_text)
            else:
                translations.append((default_text, default_annotations, default_lang))

        if len(target_formatteds) > 0:
            right_text = target_formatteds
        else:
            right_text = flatten([a for a, b, c in translations])
            right_langs = flatten([c for a, b, c in translations])

        return { 'left': lemma
               , 'context': lemma_context
               , 'pos': lemma_pos
               , 'right': right_text
               , 'lang': right_langs
               , 'hid': lemma_hid
               }


class DetailedFormat(EntryNodeIterator):
    def clean(self, e):
        lemma, lemma_pos, lemma_context, lemma_type, lemma_hid = self.l_node(e)
        tgs, ts = self.tg_nodes(e)

        source_lang = self.query_kwargs.get('source_lang')
        target_lang = self.query_kwargs.get('target_lang')
        ui_lang = self.query_kwargs.get('ui_lang')

        meaningGroups = []
        for tg in tgs:
            text, annotations, lang = self.find_translation_text(tg)
            if isinstance(text, list):
                text = ', '.join(text)
            if isinstance(annotations, list):
                annotations = ', '.join(annotations)

            target_formatted = lexicon_overrides.format_target(
                source_lang, target_lang,
                ui_lang, e, tg, text
            )

            meaningGroups.append(
                { 'annotations': annotations
                , 'translations': target_formatted
                , 'examples': self.examples(tg)
                , 'language': lang
                }
            )

        # Make our own hash, 'cause lxml won't
        entry_hash = [ unicode(lemma)
                     , unicode(lemma_context)
                     , unicode(lemma_pos)
                     , ','.join(sorted([t['translations'] for t in meaningGroups]))
                     ]
        entry_hash = str('-'.join(entry_hash).__hash__())

        # node, and default format for if a formatter doesn't exist for
        # iso


        if lemma and lemma_pos:
            default_format = "%s (%s)" % ( lemma
                                         , tagfilter( lemma_pos
                                                    , source_lang
                                                    , target_lang
                                                    )
                                         )
        elif lemma and not lemma_pos:
            default_format = lemma

        source_formatted = lexicon_overrides.format_source(
            source_lang, ui_lang, e, target_lang, default_format
        )


        return { 'lemma': lemma
               , 'lemma_context': lemma_context
               , 'pos': lemma_pos
               , 'hid': lemma_hid
               , 'meaningGroups': meaningGroups
               , 'type': lemma_type
               , 'node': e
               , 'entry_hash': entry_hash
               , 'source_formatted': source_formatted
               }

class FrontPageFormat(EntryNodeIterator):

    def clean_tg_node(self, e, tg):
        from functools import partial

        ui_lang = self.query_kwargs.get('ui_lang')

        texts, annotations, lang = self.find_translation_text(tg)

        link = True

        if texts:
            if not isinstance(texts, list):
                texts = [texts]
        else:
            from lxml import etree
            error_xml = etree.tostring(e, pretty_print=True, encoding="utf-8")
            current_app.logger.error(
                "Potential XML formatting problem while processing <tg /> nodes.\n\n" + \
                error_xml.strip()
            )

            texts = []

        # e node, tg node, default text for when formatter doesn't
        # exist for current iso

        # Apply to each translation text separately 
        target_formatter = partial( lexicon_overrides.format_target
                                  , self.query_kwargs.get('source_lang')
                                  , self.query_kwargs.get('target_lang')
                                  , ui_lang
                                  , e
                                  , tg
                                  )
        target_formatted = map(target_formatter, texts)

        right_node = { 'tx': ', '.join(texts)
                     , 're': annotations
                     , 'examples': self.examples(tg)
                     , 'target_formatted': target_formatted
                     }

        return right_node, lang

    def clean(self, e):
        lemma, lemma_pos, lemma_context, lemma_type, lemma_hid = self.l_node(e)
        tgs, ts = self.tg_nodes(e)

        ui_lang = self.query_kwargs.get('ui_lang')

        _right = map( lambda tg: self.clean_tg_node(e, tg)
                    , tgs
                    )

        right_langs = [lang for _, lang in _right]
        right_nodes = [fmt_node for fmt_node, _ in _right]

        # Make our own hash, 'cause lxml won't
        entry_hash = [ unicode(lemma)
                     , unicode(lemma_context)
                     , unicode(lemma_pos)
                     , ','.join(sorted([t['tx'] for t in right_nodes]))
                     ]
        entry_hash = str('-'.join(entry_hash).__hash__())

        # node, and default format for if a formatter doesn't exist for
        # iso

        source_lang = self.query_kwargs.get('source_lang')
        target_lang = self.query_kwargs.get('target_lang')

        if lemma and lemma_pos:
            default_format = "%s (%s)" % ( lemma
                                         , tagfilter( lemma_pos
                                                    , source_lang
                                                    , target_lang
                                                    )
                                         )
        elif lemma and not lemma_pos:
            default_format = lemma

        source_formatted = lexicon_overrides.format_source(
            source_lang, ui_lang, e, target_lang, default_format
        )

        return { 'left': lemma
               , 'source_formatted': source_formatted
               , 'context': lemma_context
               , 'pos': lemma_pos
               , 'right': right_nodes
               , 'lang': right_langs
               , 'hid': lemma_hid
               , 'entry_hash': entry_hash
               }
