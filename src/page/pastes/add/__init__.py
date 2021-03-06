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
import datetime
from google.appengine.api import users
from google.appengine.api.labs.taskqueue import Task
import logging
import pygments.lexers
import pygments.formatters

import app
import app.form
import app.model
import app.pasty
import app.syhili
import app.tag
import app.web
import recaptcha.client.captcha
import settings
import smoid

app.form.make_token()

class Add (app.web.RequestHandler):

    def __init__ (self):
        app.web.RequestHandler.__init__(self)
        self.set_module(__name__ + ".__init__")
        self.form_code = ""
        self.form_title = ""
        self.form_tags = ""
        self.form_parent_slug = ""
        self.form_token = ""
        self.url_parent_slug = ""
        self.paste = None
        self.parent_paste = None
        self.parent_paste_slug = ""

    def delete_old_forms (self):
        qforms = app.model.Form.all()
        qforms.filter("expired_at <", datetime.datetime.now())
        forms = qforms.fetch(10)
        for form in forms:
            form.delete()

    def display_form (self):
        self.write_out("./form.html")

    def get(self, parent_paste_slug=""):
        self.parent_paste_slug = parent_paste_slug
        self.on_load()

    def get_form_data (self):
        self.form_code = self.request.get("pasty_code")
        self.form_title = self.request.get("pasty_title")
        self.form_tags = self.request.get("pasty_tags")
        self.form_parent_slug = self.request.get("pasty_parent_slug")
        self.form_tags = self.request.get("pasty_tags")
        self.form_token = self.request.get("pasty_token")
        #self.url_parent_slug = self.request.get("fork")
        self.parent_slug = ""

    def get_parent_paste (self):
        parent = None
        self.parent_slug = ""
        if self.parent_paste_slug != "":
            self.parent_slug = self.parent_paste_slug
        elif self.form_parent_slug != "":
            self.parent_slug = self.form_parent_slug

        if self.parent_slug != "":
            pasties = app.model.Pasty.all()
            pasties.filter("slug =", self.parent_slug)
            parent = pasties.get()

        return parent

    def increment_paste_counter (self):
        stats = app.model.PasteStats.all()
        stats.id = 1
        stat = stats.get()
        if stat != None:
            dbnew = app.model.PasteStats(key_name=stat.key().name())
            dbnew.paste_count = stat.paste_count + 1
            dbnew.put()
        else:
            dbnew = app.model.PasteStats(key_name="c1")
            dbnew.paste_count = 1
            dbnew.put()

    def increment_fork_count (self):
        if self.parent_paste != None:
            # Increment direct fork count :
            # children of a paste
            if self.parent_paste.forks != None:
                self.parent_paste.forks += 1
            else:
                self.parent_paste.forks = 1
            self.parent_paste.put()

            # Increment indirect fork count:
            # Going up, from parent to parent
            parent_slug = self.parent_paste.slug
            while parent_slug != "":
                pastes = app.model.Pasty.all()
                pastes.filter("slug =", parent_slug)
                fork = pastes.get()
                if fork:
                    #logging.info("FORK [" + fork.slug + "] ++indirect_forks to [" + parent_slug + "] NEXT WILL BE: " + fork.parent_paste)
                    fork.indirect_forks += 1
                    fork.put()
                    parent_slug = fork.parent_paste
                else:
                    break

    def on_load (self):
        self.get_form_data()
        self.parent_paste = self.get_parent_paste()

        if self.parent_paste:
            self.content["is_fork"] = True
            self.content["u_parent_paste"] = app.url("%s", self.parent_paste.slug)
            self.content["pasty_parent_slug"] = self.parent_paste.slug

            self.path.add("Pastes", app.url("pastes/"))
            self.path.add(self.parent_paste.title, app.url("%s", self.parent_paste.slug))
            self.path.add("Fork", app.url("%s/fork", self.parent_paste_slug))

        if not self.parent_paste or self.parent_paste.is_forkable():
            if self.form_token == "":
                self.on_form_not_sent()
            else:
                self.on_form_sent()

        elif self.parent_paste:
            self.content["is_private"] = self.parent_paste.is_private()
            self.content["is_moderated"] = self.parent_paste.is_moderated()
            self.content["is_awaiting_approval"] = self.parent_paste.is_waiting_for_approval()

            self.write_out("./unforkable.html")

    def on_form_not_sent (self):
        if not self.user.is_logged_in_google:
            self.content["recaptcha"] = recaptcha.client.captcha.displayhtml(settings.RECAPTCHA_PUBLIC_KEY)

        self.content["pasty_token"] = app.form.put_form_token(self.request.remote_addr)

        if self.parent_paste != None:
            self.content["pasty_code"] = cgi.escape(self.parent_paste.code)
            self.content["pasty_title"] = "Fork"
            if self.parent_paste.forks >= 1:
                self.content["pasty_title"] += str(self.parent_paste.forks + 1)
            self.content["pasty_title"] += ": " + cgi.escape(self.parent_paste.title)
            self.content["u_parent"] = app.url("%s", self.parent_paste.slug)
            self.content["parent_slug"] = self.parent_paste.slug
            self.content["u_form"] = app.url("%s/fork", self.parent_paste.slug)
        else:
            self.content["u_form"] = app.url("")

        if self.request.get("code") != "":
            self.content["pasty_code"] = cgi.escape(self.request.get("code"))

        if self.request.get("title") != "":
            self.content["pasty_title"] = cgi.escape(self.request.get("title"))

        self.display_form()

        self.delete_old_forms()

    def move_all_same_level_forks_down (self):
        qry = app.model.Pasty.all()
        qry.filter("thread =", self.parent_paste.thread)
        qry.filter("thread_position >", self.parent_paste.thread_position + self.parent_paste.indirect_forks)
        forks = qry.fetch(1000)

        for fork in forks:
            if fork.slug != self.paste.slug:
                fork.thread_position = fork.thread_position + 1
                fork.put()

    def on_form_sent (self):
        slug = app.pasty.make_unique_slug(8)

        self.content["pasty_code"] = self.form_code
        self.content["pasty_tags"] = self.form_tags
        self.content["pasty_title"] = self.form_title
        self.content["pasty_token"] = self.form_token
        self.content["pasty_slug"] = cgi.escape(slug)
        if self.parent_paste:
            self.content["u_diff"] = app.url("%s/diff/%s", self.parent_paste.slug, slug)

        if self.validate_form():
            self.put_paste(slug)
            self.increment_fork_count()
            if self.parent_paste:
                self.move_all_same_level_forks_down()
            self.increment_paste_counter()

            if self.paste.is_private():
                self.content["u_pasty"] = self.paste.get_private_url()
            else:
                self.content["u_pasty"] = self.paste.get_url()

            self.content["is_private"] = self.paste.is_private()
            self.content["u_pasty_encoded"] = cgi.escape(self.content["u_pasty"])
            self.content["u_fork"] = app.url("%s/fork", slug)
            self.content["u_add"] = app.url("")

            self.write_out("./added.html")

            app.form.delete_token(self.form_token, self.request.remote_addr)
        else:
            self.content["recaptcha"] = recaptcha.client.captcha.displayhtml(settings.RECAPTCHA_PUBLIC_KEY)
            self.display_form()

    def post (self, parent_paste_slug=""):
        self.parent_paste_slug = parent_paste_slug
        self.on_load()

    def put_log (self, db_paste):
        """
        Puts a log entry to the datastore.
        """
        log = app.model.Log()
        log.user = db_paste.user

        if db_paste.slug == db_paste.thread:
            log.type = "paste_add"
        else:
            log.type = "paste_fork"
            log.item2_slug = db_paste.thread
            log.item2_name = db_paste.thread

        log.item1_slug = db_paste.slug
        log.item1_name = db_paste.title

        return log.put()

    def put_paste (self, slug):
        """
        Puts the paste to the datastore.
        """

        is_reply = self.form_parent_slug != ""

        self.paste = app.model.Pasty()
        paste_is_private = self.request.get("submit") == "privately"

        self.paste.set_code(self.form_code)
        self.paste.edited_at = datetime.datetime.now()
        self.paste.edited_by_ip = self.request.remote_addr
        self.paste.forks = 0
        self.paste.indirect_forks = 0
        self.paste.parent_paste = ""
        self.paste.posted_at = datetime.datetime.now()
        self.paste.posted_by_ip = self.request.remote_addr
        self.paste.replies = 0
        self.paste.slug = slug

        if not is_reply and paste_is_private:
            self.paste.status = app.model.kPASTE_STATUS_PRIVATE
            self.paste.secret_key = app.model.Pasty.make_secret_key()
        else:
            self.paste.status = app.model.kPASTE_STATUS_PUBLIC
            self.paste.secret_key = ""

        self.paste.title = app.pasty.filter_title(self.form_title, slug)
        self.paste.user = self.user.db_user

        if self.user.is_logged_in:
            self.paste.posted_by_user_name = self.user.id
        else:
            self.paste.posted_by_user_name = settings.DEFAULT_USER_NAME

        if is_reply:
            is_first_of_thread = False
            self.paste.parent_paste = self.form_parent_slug
            self.paste.thread_level = self.parent_paste.thread_level + 1
            self.paste.thread_position = self.parent_paste.thread_position \
                                         + self.parent_paste.indirect_forks + 1

            if self.parent_paste.thread == None:
                self.paste.thread = slug
            else:
                self.paste.thread = self.parent_paste.thread
        else:
            self.paste.thread_level = 0
            self.paste.thread_position = 0

        pasty_key = self.paste.put()

        result = pasty_key != None

        if result == True:
            dbPaste = app.model.Pasty.get(pasty_key)
            # If the paste is not a reply, then it's starting its own thread.
            if not is_reply:
                if dbPaste != None:
                    dbPaste.thread = slug
                    dbPaste.put()

            if result == True:
                task = Task(name = self.paste.slug, method="GET", url = "/" + self.paste.slug + "/recount")
                task.add(queue_name="paste-recount")
                self.put_log(dbPaste)

        return result

    def validate_form (self):
        result = True

        code = self.form_code
        token = self.form_token

        if not self.user.is_logged_in_google:

            cap_challenge = self.request.get("recaptcha_challenge_field")
            cap_response = self.request.get("recaptcha_response_field")

            captcha_response = recaptcha.client.captcha.submit(cap_challenge,
                                                                 cap_response,
                                                                 settings.RECAPTCHA_PRIVATE_KEY,
                                                                 self.request.remote_addr
                                                                )
            if not captcha_response.is_valid:
                self.content["pasty_captcha_error"] = "Please try again."
                result = False

        if result == True and not app.form.has_valid_token(self.request.remote_addr, token):
            if token != "":
                self.content["pasty_error"] = "<strong>Your form has expired</strong>, you probably took too much time to fill it. <a href=\"" + app.url("") + "\"><strong>Refresh this page</strong></a>."
            result = False

        if result == True and len(code) == 0:
            self.content["pasty_code_error"] = "You must paste some code."
            result = False

        return result
