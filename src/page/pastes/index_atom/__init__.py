# Copyright 2008 Thomas Quemard
#
# Paste-It is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published
# by the Free Software Foundation; either version 3.0, or (at your option)
# any later version.
#
# Paste-It is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
# License for more details.


import cgi

import app
import app.model
import app.util
import app.web
import app.web.ui
import settings
import smoid.languages


class IndexAtom (app.web.RequestHandler):
    """
    A listing of the pastes as an atom feed.
    """

    def __init__ (self):
        app.web.RequestHandler.__init__(self)
        self.set_module(__name__ + ".__init__")
        self.paste_count = 0

    def get (self):
        self.paste_count = self.get_paste_count()

        self.content["u_pastes"] = app.url("pastes/")
        self.content["u_self"] = app.url("pastes.atom")
        self.content["paste_count"] = self.paste_count
        self.content["pastes"] = self.get_pastes()

        self.set_header("Content-Type", "application/atom+xml")
        self.write_out("./200.html")

    def get_paste_count (self):
        """
        Retrieve the total paste count from the datastore.
        """

        count = 0
        stats = app.model.PasteStats.all()
        stats.id = 1
        stat = stats.get()
        if stat != None:
            count = stat.paste_count
        return count

    def get_pastes (self):
        """
        Retrieve the pastes for the current page.
        """

        pastes = []

        db = app.model.Pasty.all()
        db.order("-posted_at")
        dbpastes = db.fetch(10, 0)

        if dbpastes != None:
            for opaste in dbpastes:
                dpaste = {}
                dpaste["title"] = opaste.get_title()
                dpaste["u"] = opaste.get_url()
                dpaste["snippet"] = opaste.get_snippet()

                if opaste.user:
                    dpaste["user_name"] = opaste.user.id
                else:
                    dpaste["user_name"] = opaste.posted_by_user_name

                if opaste.user:
                    dpaste["u_gravatar"] = opaste.user.get_gravatar(16)

                dpaste["u_language_icon"] = opaste.get_icon_url()

                if opaste.forks > 0:
                    dpaste["forks"] = opaste.forks

                if opaste.posted_at != None:
                    dpaste["posted_at"] = opaste.posted_at.strftime(settings.ATOM_DATETIME_FORMAT)
                else:
                    dpaste["posted_at"] = ""

                if opaste.characters:
                    dpaste["size"] = app.util.make_filesize_readable(opaste.characters)
                dpaste["lines"] = opaste.lines
                dpaste["language"] = opaste.get_language_name()

                pastes.append(dpaste)
        return pastes
