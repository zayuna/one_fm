# Copyright (c) 2021, omar jaber and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, add_to_date, cstr, cint, getdate, get_link_to_form


class RosterPostActions(Document):
	def after_insert(self):
		# send notification to supervisor
		user_id = frappe.db.get_value("Employee", self.supervisor, ["user_id"])
		if user_id:
			link = get_link_to_form(self.doctype, self.name)
			subject = _("New Action to {action_type}.".format(action_type=self.action_type))
			message = _("""
				You have been issued a Roster Post Action.<br>
				Please review the Post Type for the specified date in the roster, take necessary actions and update the status.<br>
				Link: {link}""".format(link=link))
			frappe.sendmail([user_id], subject=subject, message=message, reference_doctype=self.doctype, reference_name=self.name)