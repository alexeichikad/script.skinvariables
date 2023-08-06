# -*- coding: utf-8 -*-
# Module: default
# Author: jurialmunkey
# License: GPL v.3 https://www.gnu.org/copyleft/gpl.html
import xbmc
import xbmcgui
import xbmcaddon
from json import loads
from jurialmunkey.futils import load_filecontent, write_skinfile, make_hash

ADDON = xbmcaddon.Addon()


class SkinShortcutsTemplate(object):
    def __init__(self, template: str = None):
        self.template = f'skinvariables-generator-{template}' if template else 'skinvariables-generator'
        self.hashname = f'script-{self.template}-hash'
        self.folders = ['shortcuts']
        self.content = load_filecontent(f'special://skin/shortcuts/{self.template}.json')
        self.meta = loads(self.content) or {}
        self.filename = self.meta['output']

    @staticmethod
    def create_xml(meta, header=None, footer=None):

        def _make_template(i):
            template = load_filecontent(f'special://skin/shortcuts/{i.pop("template")}')
            template = template.format(**i)
            return template

        cheader = [header] if header else []
        cfooter = [footer] if footer else []
        content = cheader + [_make_template(i) for i in meta] + cfooter

        return '\n'.join(content)

    def update_xml(self, force=False, no_reload=False, **kwargs):
        if not self.meta:
            return

        hashvalue = make_hash(self.content)

        if not force:  # Allow overriding over built check
            last_version = xbmc.getInfoLabel(f'Skin.String({self.hashname})')
            if hashvalue and last_version and hashvalue == last_version:
                return  # Already updated

        p_dialog = xbmcgui.DialogProgressBG()
        p_dialog.create(ADDON.getLocalizedString(32001), ADDON.getLocalizedString(32000))

        content = self.create_xml(self.meta['genxml'], header=self.meta.get('header'), footer=self.meta.get('footer'))

        # Save to folder
        write_skinfile(folders=self.folders, filename=self.filename, content=content, hashvalue=hashvalue, hashname=self.hashname)

        p_dialog.close()
        xbmc.executebuiltin('ReloadSkin()') if not no_reload else None