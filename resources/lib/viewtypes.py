# -*- coding: utf-8 -*-
# Module: default
# Author: jurialmunkey
# License: GPL v.3 https://www.gnu.org/copyleft/gpl.html
import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
from json import loads, dumps
import resources.lib.utils as utils


ADDON = xbmcaddon.Addon()
ADDON_DATA = 'special://profile/addon_data/script.skinvariables/'


class ViewTypes(object):
    def __init__(self):
        self.content = utils.load_filecontent('special://skin/shortcuts/skinviewtypes.json')
        self.meta = loads(self.content) or []
        if not xbmcvfs.exists(ADDON_DATA):
            xbmcvfs.mkdir(ADDON_DATA)
        self.addon_datafile = ADDON_DATA + xbmc.getSkinDir() + '-viewtypes.json'
        self.addon_content = utils.load_filecontent(self.addon_datafile)
        self.addon_meta = loads(self.addon_content) or {} if self.addon_content else {}
        self.prefix = self.meta.get('prefix', 'Exp_View') + '_'
        self.skinfolders = utils.get_skinfolders()

    def make_defaultjson(self, overwrite=True):
        addon_meta = {'library': {}, 'plugins': {}}
        for k, v in self.meta.get('rules', {}).items():
            # TODO: Add checks that file is properly configured and warn user otherwise
            addon_meta['library'][k] = v.get('library')
            addon_meta['plugins'][k] = v.get('plugins') or v.get('library')
        if overwrite:
            utils.write_file(filepath=self.addon_datafile, content=dumps(addon_meta))
        return addon_meta

    def make_xmltree(self):
        """
        Build the default viewtype expressions based on json file
        """
        xmltree = []
        expressions = {}
        viewtypes = {}

        for v in self.meta.get('viewtypes', {}):
            expressions[v] = ''  # Construct our expressions dictionary
            viewtypes[v] = {}  # Construct our viewtypes dictionary

        # Build the definitions for each viewid
        for base_k, base_v in self.addon_meta.items():
            for contentid, viewid in base_v.items():
                if base_k == 'library':
                    viewtypes[viewid].setdefault(contentid, {}).setdefault('library', True)
                    continue
                if base_k == 'plugins':
                    viewtypes[viewid].setdefault(contentid, {}).setdefault('plugins', True)
                    continue
                for i in viewtypes:
                    listtype = 'whitelist' if i == viewid else 'blacklist'
                    viewtypes[i].setdefault(contentid, {}).setdefault(listtype, [])
                    viewtypes[i][contentid][listtype].append(base_k)

        # Construct the visibility expression
        for viewid, base_v in viewtypes.items():
            for contentid, child_v in base_v.items():
                rule = self.meta.get('rules', {}).get(contentid, {}).get('rule')  # Container.Content()

                whitelist = ''
                if child_v.get('library'):
                    whitelist = 'String.IsEmpty(Container.PluginName)'
                for i in child_v.get('whitelist', []):
                    whitelist = utils.join_conditions(whitelist, 'String.IsEqual(Container.PluginName,{})'.format(i))

                blacklist = ''
                if child_v.get('plugins'):
                    blacklist = '!String.IsEmpty(Container.PluginName)'
                    for i in child_v.get('blacklist', []):
                        blacklist = utils.join_conditions(blacklist, '!String.IsEqual(Container.PluginName,{})'.format(i), operator=' + ')

                affix = '[{}] | [{}]'.format(whitelist, blacklist) if whitelist and blacklist else whitelist or blacklist

                if affix:
                    expression = '[{} + [{}]]'.format(rule, affix)
                    expressions[viewid] = utils.join_conditions(expressions.get(viewid), expression)

        # Construct XMLTree
        for exp_name, exp_content in expressions.items():
            xmltree.append({
                'tag': 'expression',
                'attrib': {'name': self.prefix + exp_name},
                'content': '[{}]'.format(exp_content)})

        return xmltree

    def add_pluginview(self, contentid=None, pluginname=None, viewid=None):
        if not contentid or not pluginname or not self.meta.get('rules', {}).get(contentid):
            return
        if not viewid:
            items, ids = [], []
            for i in self.meta.get('rules', {}).get(contentid, {}).get('viewtypes', []):
                ids.append(i)
                items.append(self.meta.get('viewtypes', {}).get(i))
            header = '{} {} ({})'.format(ADDON.getLocalizedString(32004), pluginname, contentid)
            choice = xbmcgui.Dialog().select(header, items)
            viewid = ids[choice] if choice != -1 else None
        if not viewid:
            return  # No viewtype chosen
        self.addon_meta.setdefault(pluginname, {})
        self.addon_meta[pluginname][contentid] = viewid
        return viewid

    def make_xmlfile(self, skinfolder=None, hashvalue=None):
        xmltree = self.make_xmltree()

        # # Get folder to save to
        folders = [skinfolder] if skinfolder else self.skinfolders
        if folders:
            utils.write_skinfile(
                folders=folders, filename='script-skinviewtypes-includes.xml',
                content=utils.make_xml_includes(xmltree),
                hashname='script-skinviewtypes-hash', hashvalue=hashvalue)

        utils.write_file(filepath=self.addon_datafile, content=dumps(self.addon_meta))

    def add_newplugin(self):
        """
        Get list of available plugins and allow user to choose which to views to add
        """
        method = "Addons.GetAddons"
        properties = ["name", "thumbnail"]
        params_a = {"type": "xbmc.addon.video", "properties": properties}
        params_b = {"type": "xbmc.addon.audio", "properties": properties}
        params_c = {"type": "xbmc.addon.image", "properties": properties}
        response_a = utils.get_jsonrpc(method, params_a).get('result', {}).get('addons') or []
        response_b = utils.get_jsonrpc(method, params_b).get('result', {}).get('addons') or []
        response_c = utils.get_jsonrpc(method, params_c).get('result', {}).get('addons') or []
        response = response_a + response_b + response_c
        dialog_list, dialog_ids = [], []
        for i in response:
            dialog_item = xbmcgui.ListItem(label=i.get('name'), label2='{}'.format(i.get('addonid')))
            dialog_item.setArt({'icon': i.get('thumbnail'), 'thumb': i.get('thumbnail')})
            dialog_list.append(dialog_item)
            dialog_ids.append(i.get('addonid'))
        idx = xbmcgui.Dialog().select('Choose plugin to customise', dialog_list, useDetails=True)
        if idx == -1:
            return
        pluginname = dialog_ids[idx]
        contentids = [i for i in sorted(self.meta.get('rules', {}))]
        idx = xbmcgui.Dialog().select('Choose content to customise', contentids)
        if idx == -1:
            return self.add_newplugin()  # Go back to previous dialog
        contentid = contentids[idx]
        return self.add_pluginview(pluginname=pluginname, contentid=contentid)

    def get_addondetails(self, addonid=None, prop=None):
        """
        Get details of a plugin
        """
        if not addonid or not prop:
            return
        method = "Addons.GetAddonDetails"
        params = {"addonid": addonid, "properties": [prop]}
        return utils.get_jsonrpc(method, params).get('result', {}).get('addon', {}).get(prop)

    def dc_listcomp(self, listitems, listprefix='', idprefix='', contentid=''):
        return [
            ('{}{} ({})'.format(listprefix, k.capitalize(), self.meta.get('viewtypes', {}).get(v)), (idprefix, k))
            for k, v in listitems if not contentid or contentid == k]

    def dialog_configure(self, contentid=None, pluginname=None, viewid=None, force=False):
        dialog_list = []

        if not pluginname or pluginname == 'library':
            dialog_list += self.dc_listcomp(
                sorted(self.addon_meta.get('library', {}).items()), listprefix='Library - ', idprefix='library', contentid=contentid)

        if not pluginname or pluginname == 'plugins':
            dialog_list += self.dc_listcomp(
                sorted(self.addon_meta.get('plugins', {}).items()), listprefix='Plugins - ', idprefix='plugins', contentid=contentid)

        if not pluginname or pluginname != 'library':
            for k, v in self.addon_meta.items():
                if k in ['library', 'plugins']:
                    continue
                if pluginname and pluginname != 'plugins' and pluginname != k:
                    continue  # Only add the named plugin if not just doing generic plugins
                name = self.get_addondetails(addonid=k, prop='name')
                dialog_list += self.dc_listcomp(
                    sorted(v.items()), listprefix=name + ' - ', idprefix=k, contentid=contentid)
                dialog_list.append(('Reset all {} views...'.format(name), (k, 'default')))

        if not contentid:
            if not pluginname or pluginname == 'plugins':
                dialog_list.append(('Reset all {} views...'.format('plugin'), ('plugins', 'default')))
            if not pluginname or pluginname == 'library':
                dialog_list.append(('Reset all {} views...'.format('library'), ('library', 'default')))
            if not pluginname or pluginname != 'library':
                dialog_list.append(('Add plugin view...', (None, 'add_pluginview')))

        idx = xbmcgui.Dialog().select('Customise viewtypes', [i[0] for i in dialog_list])
        if idx == -1:
            return force  # User cancelled

        usr_pluginname, usr_contentid = dialog_list[idx][1]
        if usr_contentid == 'default':
            choice = xbmcgui.Dialog().yesno(
                'Reset {} Views'.format(usr_pluginname),
                'Do you wish to reset all {} views to default'.format(usr_pluginname))

            if choice and usr_pluginname == 'plugins':
                self.addon_meta[usr_pluginname] = self.make_defaultjson(overwrite=False).get(usr_pluginname, {})
                for i in self.addon_meta:  # Also clean all custom plugin setups
                    self.addon_meta.pop(i) if i != 'library' else None
            elif choice and usr_pluginname == 'library':
                self.addon_meta[usr_pluginname] = self.make_defaultjson(overwrite=False).get(usr_pluginname, {})
            elif choice and usr_pluginname:  # Specific plugin so just remove the whole entry
                self.addon_meta.pop(usr_pluginname)

            force = force or choice
        elif usr_contentid == 'add_pluginview':
            choice = self.add_newplugin()
            force = force or choice
        else:
            choice = self.add_pluginview(contentid=usr_contentid.lower(), pluginname=usr_pluginname.lower())
            force = force or choice

        return self.dialog_configure(contentid=contentid, pluginname=pluginname, viewid=viewid, force=force)

    def xmlfile_exists(self, skinfolder=None):
        folders = [skinfolder] if skinfolder else self.skinfolders

        for folder in folders:
            if not xbmcvfs.exists('special://skin/{}/script-skinviewtypes-includes.xml'.format(folder)):
                return False
        return True

    def update_xml(self, force=False, skinfolder=None, contentid=None, viewid=None, pluginname=None, configure=False):
        if not self.meta:
            return

        # Make these strings for simplicity
        contentid = contentid or ''
        pluginname = pluginname or ''

        # Simple hash value based on character size of file
        hashvalue = 'hash-{}'.format(len(self.content))

        with utils.busy_dialog():
            if not force:
                last_version = xbmc.getInfoLabel('Skin.String(script-skinviewtypes-hash)')
                if not last_version or hashvalue != last_version:
                    force = True
            if force or not self.addon_meta:
                self.addon_meta = self.make_defaultjson()

        if configure:  # Configure kwparam so open gui
            force = self.dialog_configure(contentid=contentid.lower(), pluginname=pluginname.lower(), viewid=viewid)
        elif contentid:  # If contentid defined but no configure kwparam then just select a view
            pluginname = pluginname or 'library'
            force = self.add_pluginview(contentid=contentid.lower(), pluginname=pluginname.lower(), viewid=viewid)

        if not force and self.xmlfile_exists():
            return

        with utils.busy_dialog():
            self.make_xmlfile(skinfolder=skinfolder, hashvalue=hashvalue)
