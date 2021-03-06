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


from google.appengine.api import users
import hashlib

import app
import app.model


class User:
    def refresh (self):
        guser = users.get_current_user()
        self.db_user = None
        self.id = None
        self.is_google_admin = False
        self.is_logged_in = False
        self.url = ""

        if guser:
            self.google_id = guser.user_id()
            self.google_email = guser.email()
            self.gravatar_id = hashlib.md5(self.google_email).hexdigest()
            self.is_logged_in_google = True
            self.is_google_admin = users.is_current_user_admin()
        else:
            self.google_id = ""
            self.google_email = ""
            self.gravatar_id = ""
            self.is_logged_in_google = False

        if self.google_id != "":
            qry_user = app.model.User.all()
            qry_user.filter("google_id =", self.google_id)
            self.db_user = qry_user.get()
            if self.db_user:
                self.is_logged_in = True
                self.id = self.db_user.id
                self.paste_count = self.db_user.paste_count
                self.url = app.url("users/%s", self.id)



_user = User()

def get_current_user ():
    return _user
