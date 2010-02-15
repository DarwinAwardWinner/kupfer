# -*- coding: UTF-8 -*-
__kupfer_name__ = _("Google Mail")
__kupfer_sources__ = ("GoogleContactsSource", )
__kupfer_actions__ = ('NewMailAction', )
__description__ = _("Load contacts and compose new email in Google Mail")
__version__ = "2010-02-04"
__author__ = "Karol Będkowski <karol.bedkowski@gmail.com>"

import urllib
import time

import gdata.service
import gdata.contacts.service

from kupfer.objects import Action, TextLeaf, UrlLeaf
from kupfer.obj.special import PleaseConfigureLeaf, InvalidCredentialsLeaf
from kupfer.obj.grouping import ToplevelGroupingSource
from kupfer.obj.contacts import ContactLeaf, EmailContact, email_from_leaf
from kupfer import plugin_support, pretty, utils, icons, kupferstring
from kupfer.obj.helplib import background_loader

__kupfer_settings__ = plugin_support.PluginSettings(
	{
		'key': 'userpass',
		'label': '',
		'type': plugin_support.UserNamePassword,
		'value': '',
	},
	{
		'key': 'loadicons',
		'label': _('Load contacts icons'),
		'type': bool,
		'value': True,
	}
)

UPDATE_STARTU_DELAY_S = 5
UPDATE_INTERVAL_S = 15*60 # 15 min
GMAIL_NEW_MAIL_URL = \
	"https://mail.google.com/mail/?view=cm&ui=2&tf=0&to=%(emails)s&fs=1"


def is_plugin_configured():
	''' Chec is plugin is configuret (user name and password is configured) '''
	upass = __kupfer_settings__['userpass']
	return bool(upass and upass.username and upass.password)


class NewMailAction(Action):
	''' Create new mail to selected leaf'''
	def __init__(self):
		Action.__init__(self, _('Compose Email in GMail'))

	def activate(self, obj):
		self.activate_multiple((obj, ))

	def activate_multiple(self, objects):
		recipients = ",".join(urllib.quote(email_from_leaf(L)) for L in objects)
		url = GMAIL_NEW_MAIL_URL % dict(emails=recipients)
		utils.show_url(url)

	def get_gicon(self):
		return icons.ComposedIcon("mail-message-new", "gmail")

	def item_types(self):
		yield ContactLeaf
		# we can enter email
		yield TextLeaf
		yield UrlLeaf

	def valid_for_item(self, item):
		return bool(email_from_leaf(item))

	def get_description(self):
		return _("Open web browser and compose new email in GMail")


def get_gclient():
	''' create gdata client object and login do google service '''
	if not is_plugin_configured():
		return None
	upass = __kupfer_settings__['userpass']
	gd_client = gdata.contacts.service.ContactsService()
	gd_client.email = upass.username
	gd_client.password = upass.password
	gd_client.source = 'kupfer-google_mail'
	gd_client.ProgrammaticLogin()
	return gd_client


# background loader
@background_loader(interval=UPDATE_INTERVAL_S, delay=UPDATE_STARTU_DELAY_S,
		name='google-contacts')
def get_contacts():
	''' load all contacts '''
	pretty.print_debug(__name__, 'get_contacts start')
	contacts = None
	start_time = time.time()
	try:
		gd_client = get_gclient()
		if gd_client is None:
			return None

		contacts = []
		query = gdata.contacts.service.ContactsQuery()
		query.max_results = 9999 # load all contacts
		for entry in gd_client.GetContactsFeed(query.ToUri()).entry:
			common_name = kupferstring.tounicode(entry.title.text)
			for email in entry.email:
				if email.address:
					image = None
					if __kupfer_settings__['loadicons']:
						image = gd_client.GetPhoto(entry)
					email = email.address
					contacts.append(GoogleContact(email, common_name or email,
							image))

	except (gdata.service.BadAuthentication, gdata.service.CaptchaRequired), err:
		pretty.print_error(__name__, 'get_contacts error',
				'authentication error', err)
		contacts = [InvalidCredentialsLeaf(__name__, __kupfer_name__)]

	except gdata.service.Error, err:
		pretty.print_error(__name__, 'get_contacts error', err)

	else:
		pretty.print_debug(__name__, 'get_contacts finished; load contacts:',
				len(contacts), 'in:', time.time()-start_time, 'load_icons:',
				__kupfer_settings__['loadicons'])

	return contacts


class GoogleContact(EmailContact):
	def __init__(self, email, name, image):
		EmailContact.__init__(self, email, name)
		self.image = image

	def get_thumbnail(self, width, height):
		if self.image:
			return icons.get_pixbuf_from_data(self.image, width, height)
		return EmailContact.get_thumbnail(self, width, height)


class GoogleContactsSource(ToplevelGroupingSource):
	def __init__(self, name=_("Google Mail")):
		super(GoogleContactsSource, self).__init__(name, "Contacts")
		self._version = 3

	def initialize(self):
		ToplevelGroupingSource.initialize(self)
		# fill loader cache by source cache
		get_contacts.fill_cache(self.cached_items)
		# start background job
		get_contacts.bind_and_start(self.mark_for_update)

	def get_items(self):
		if is_plugin_configured():
			return get_contacts() or []
		return [PleaseConfigureLeaf(__name__, __kupfer_name__)]

	def should_sort_lexically(self):
		return True

	def provides(self):
		yield ContactLeaf
		yield PleaseConfigureLeaf

	def get_description(self):
		return _("Contacts from Google services (Google Mail)")

	def get_icon_name(self):
		return "gmail"
